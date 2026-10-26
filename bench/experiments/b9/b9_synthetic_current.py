"""B9 -- apakah sinyal kompresor (sintetis) membantu diagnosis? Split VAL, label v5, XGBoost ukuran chip.

Fitur dasar = 72 statistik jendela + konteks trip TANPA suhu saat muat (angka acuan B8: Macro F1 0,852).
Ditambah 6 statistik jendela untuk tiap kolom kompresor (bench/b9_lib.KOLOM).

  S1  efek arus 100 / 50 / 25 %     (seberapa bergantung pada besaran yang dikarang)
  S2  sebaran isolasi sedang/lebar  (truk sehat berisolasi buruk juga ber-duty tinggi)
  S3  duty saja vs duty + arus      (reefer digerakkan mesin tidak punya arus kompresor)

  python -m bench.experiments.b9.b9_synthetic_current

Hasil: bench/results/local-cpu/B9/synthetic_current.json. Split test tidak disentuh.
"""

import time

import numpy as np

from bench.core.common import RESULTS_DIR, ROOT, git_info, now_iso, write_json

OUT = RESULTS_DIR / "local-cpu" / "B9"
KONTEKS_TANPA_SUHU_AWAL = ["menit_trip", "tren_240", "rata240_minus_rata60", "kemiringan_240"]
ISOLASI = {"sedang": (0.8, 1.4), "lebar": (0.6, 1.8)}


def main():
    import xgboost as xgb

    from bench.experiments.b8 import b8_lib as b8
    from bench.experiments.b8.b8_label_context import UKURAN, metrik_kelas
    from bench.experiments.b9 import b9_lib as b9
    from ml.evaluation.baselines import XGB_PARAMS, aggregate

    d = {s: b8.muat(s) for s in ("train", "val")}
    ix = [b8.KONTEKS.index(k) for k in KONTEKS_TANPA_SUHU_AWAL]
    dasar = {s: np.c_[aggregate(np.load(ROOT / f"data/processed/windows/windows_{s}.npz")["X"]), d[s]["ctx"][:, ix]]
             for s in d}

    def latih(X, nama, **meta):
        clf = xgb.XGBClassifier(objective="multi:softprob", num_class=7, disable_default_eval_metric=True,
                                **{**XGB_PARAMS, **UKURAN["chip"], "n_jobs": 4, "random_state": 1000})
        t0 = time.perf_counter()
        clf.fit(X["train"], d["train"]["y_baru"])
        m = metrik_kelas(d["val"]["y_baru"], clf.predict_proba(X["val"]))
        m.update(nama=nama, detik_latih=time.perf_counter() - t0, **meta)
        pk = m["per_kelas"]
        print(f"{nama:38s} F1 {m['macro_f1']:.3f} PR-AUC {m['anomali_pr_auc']:.3f} | degradasi "
              f"P {pk['degradasi_bertahap']['presisi']:.2f} R {pk['degradasi_bertahap']['recall']:.2f} "
              f"F1 {pk['degradasi_bertahap']['f1']:.2f} | A0 {pk['A0']['f1']:.2f}", flush=True)
        return m

    hasil = {"waktu_utc": now_iso(), "git": git_info(), "split": "val", "label": "v5", "model": "xgb chip",
             "cfg_sinyal": b9.CFG, "run": [latih(dasar, "tanpa sinyal kompresor")]}
    for nama_iso, iso in ISOLASI.items():
        for skala in (1.0, 0.5, 0.25):
            sig = {s: b9.jendela(s, skala_efek=skala, isolasi=iso) for s in d}
            agg = {s: aggregate(sig[s]) for s in d}            # 6 statistik x [duty, arus]
            duty_ix = [k * 2 for k in range(6)]
            if skala == 1.0:   # duty tidak bergantung pada skala efek arus
                hasil["run"].append(latih({s: np.c_[dasar[s], agg[s][:, duty_ix]] for s in d},
                                          f"duty saja, isolasi {nama_iso}", isolasi=nama_iso, fitur="duty"))
            hasil["run"].append(latih({s: np.c_[dasar[s], agg[s]] for s in d},
                                      f"duty + arus efek {int(skala * 100)}%, isolasi {nama_iso}",
                                      isolasi=nama_iso, fitur="duty+arus", skala_efek=skala))
    print("Tersimpan:", write_json(OUT / "synthetic_current.json", hasil))


if __name__ == "__main__":
    main()
