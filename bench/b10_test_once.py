"""B10 -- evaluasi split TEST, SEKALI per model, untuk kandidat B8/B9 (XGBoost ukuran chip, label v5).

Urutan mengikuti bench/b3_test_once.py: model dilatih ulang di train lalu DIBEKUKAN (disimpan + sha256),
angka val dicek ulang terhadap angka saat seleksi (tolak bila beda), akses dicatat DULU di
bench/results/test_access_log.json, baru split test dibangun dan dinilai. Bila --id sudah tercatat,
skrip menolak berjalan.

  python -m bench.b10_test_once --id b8_xgb_chip_v5_konteks
  python -m bench.b10_test_once --id b9_xgb_chip_v5_konteks_duty_sintetis

Hasil: bench/results/test/<id>.json; artefak model: bench/results/lokal-cpu/B10/<id>.json
"""

import argparse
import json
import sys

import numpy as np

from bench.common import (
    RESULTS_DIR,
    git_info,
    now_iso,
    rel,
    sha256_file,
    write_json,
)

LOG = RESULTS_DIR / "test_access_log.json"
KANDIDAT = {
    "b8_xgb_chip_v5_konteks": {
        "duty": False, "val_seleksi": 0.852,
        "sumber": "bench/results/lokal-cpu/B9/arus_sintetis.json (tanpa sinyal kompresor)"},
    "b9_xgb_chip_v5_konteks_duty_sintetis": {
        "duty": True, "val_seleksi": 0.933,
        "sumber": "bench/results/lokal-cpu/B9/arus_sintetis.json (duty saja, isolasi sedang)"},
}


def fitur(split, duty, izinkan_test=False):
    from bench import b8_lib as b8
    from bench import b9_lib as b9
    from bench.b9_arus_sintetis import KONTEKS_TANPA_SUHU_AWAL
    from ml.baselines import aggregate

    d = b8.bangun(split, izinkan_test=izinkan_test)[0] if split == "test" else b8.muat(split)
    ix = [b8.KONTEKS.index(k) for k in KONTEKS_TANPA_SUHU_AWAL]
    X = np.c_[aggregate(np.load(b8.path_npz(split, izinkan_test))["X"]), d["ctx"][:, ix]]
    if duty:
        sig = b9.jendela(split, izinkan_test=izinkan_test)
        X = np.c_[X, aggregate(sig)[:, [k * 2 for k in range(6)]]]
    return X, d


def main(argv=None):
    import xgboost as xgb

    from bench.b8_label_konteks import UKURAN, metrik_kelas
    from ml.baselines import XGB_PARAMS

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--id", required=True, choices=list(KANDIDAT))
    a = ap.parse_args(argv)
    k = KANDIDAT[a.id]

    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else []
    if any(e["id"] == a.id for e in log):
        sys.exit(f"DITOLAK: model '{a.id}' sudah pernah dievaluasi di split test ({LOG.name}).")

    Xtr, dtr = fitur("train", k["duty"])
    Xva, dva = fitur("val", k["duty"])
    clf = xgb.XGBClassifier(objective="multi:softprob", num_class=7, disable_default_eval_metric=True,
                            **{**XGB_PARAMS, **UKURAN["chip"], "n_jobs": 4, "random_state": 1000})
    clf.fit(Xtr, dtr["y_baru"])
    model = RESULTS_DIR / "lokal-cpu" / "B10" / f"{a.id}.json"
    model.parent.mkdir(parents=True, exist_ok=True)
    clf.save_model(model)
    val = metrik_kelas(dva["y_baru"], clf.predict_proba(Xva))
    if abs(val["macro_f1"] - k["val_seleksi"]) > 0.002:
        sys.exit(f"DIBATALKAN sebelum akses test: val {val['macro_f1']:.4f} != angka seleksi {k['val_seleksi']}")

    entri = {"id": a.id, "model": rel(model), "sha256_model": sha256_file(model), "waktu_utc": now_iso(),
             "git": git_info()}
    LOG.write_text(json.dumps(log + [entri], indent=2, ensure_ascii=False), encoding="utf-8")  # catat DULU

    Xte, dte = fitur("test", k["duty"], izinkan_test=True)
    proba = clf.predict_proba(Xte)
    hasil = entri | {
        "split": "test", "label": "v5 (bench/b8_lib.py)", "model_jenis": "XGBoost multi:softprob, 60 ronde, kedalaman 4",
        "fitur": "72 statistik jendela + konteks tanpa suhu saat muat"
                 + (" + 6 statistik siklus kerja kompresor SINTETIS (bench/b9_lib.py, isolasi sedang)" if k["duty"] else ""),
        "val_seleksi": {"macro_f1": k["val_seleksi"], "sumber": k["sumber"]},
        "val_artefak_beku": {kk: val[kk] for kk in ("macro_f1", "anomali_pr_auc", "akurasi")},
        "metrik_test_label_v5": metrik_kelas(dte["y_baru"], proba),
        "metrik_test_label_lama": metrik_kelas(dte["y_lama"], proba),
    }
    path = write_json(RESULTS_DIR / "test" / f"{a.id}.json", hasil)
    for lab in ("metrik_test_label_v5", "metrik_test_label_lama"):
        m = hasil[lab]
        print(f"{lab:24s} macro F1 {m['macro_f1']:.3f}  PR-AUC {m['anomali_pr_auc']:.3f}  akurasi {m['akurasi']:.3f} | "
              + " ".join(f"{c[:6]}:{v['f1']:.2f}" for c, v in m["per_kelas"].items()))
    print("Tersimpan:", rel(path))


if __name__ == "__main__":
    main()
