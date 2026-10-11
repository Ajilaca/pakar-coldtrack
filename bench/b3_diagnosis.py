"""B3 langkah 1 -- diagnosis baseline di split VAL sebelum mencoba perbaikan apa pun.

- GRU konfigurasi asli (5 seed) dan XGBoost classifier (deterministik): F1/presisi/recall per kelas,
  matriks kebingungan.
- Kinerja vs menit sejak onset anomali: apakah kelas lemah lemah karena modelnya, atau karena
  label menyatakan anomali sejak menit onset padahal jendela belum memuat sinyalnya (label implisit).

  python -m bench.b3_diagnosis --tag g16-gpu

Hasil: bench/results/<tag>/B3/diagnosis.json
"""

import argparse

import numpy as np

from bench.common import RESULTS_DIR, SEEDS, git_info, now_iso, write_json

BUCKET = [(0, 10), (10, 30), (30, 60), (60, 120), (120, 10_000)]


def per_bucket(pred, y, onset_min):
    out = {}
    for lo, hi in BUCKET:
        sel = (onset_min >= lo) & (onset_min < hi)
        if not sel.any():
            continue
        out[f"{lo}-{hi if hi < 10_000 else 'inf'}"] = {
            "n": int(sel.sum()),
            "akurasi_mode": float((pred[sel] == y[sel]).mean()),
            "terdeteksi_anomali": float((pred[sel] != 0).mean()),   # recall biner anomali
        }
    return out


def main(argv=None):
    from bench.run import apply_device_env, check_cuda_or_die, resolve_tag

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", default="g16-gpu")
    a = ap.parse_args(argv)
    _, kind = resolve_tag(a.tag)
    apply_device_env(kind)
    check_cuda_or_die(kind)

    from bench import b3_lib as b3
    from bench import train_lib as tl

    tl.ensure_windows()
    onset = b3.menit_sejak_onset("val")
    data, _ = tl.prepare_gru_data()
    hasil = {"waktu_utc": now_iso(), "git": git_info(), "tag": a.tag, "split": "val",
             "bucket_menit_sejak_onset": [list(b) for b in BUCKET], "gru": {}, "xgb_clf": None}

    for seed in SEEDS:
        model, info = b3.train(data, b3.GruCfg(), seed, kind)
        (f, c, t), d = b3.predict(model, data, kind)
        m = b3.metrik_lengkap(f, c, t, d, data["mean"], data["std"])
        m["per_bucket_onset"] = per_bucket(c.argmax(1).numpy(), d["y_mode"], onset)
        m["latih"] = info
        hasil["gru"][str(seed)] = m
        print(f"GRU seed {seed}: F1 {m['macro_f1']:.4f} PR-AUC {m['anomali_pr_auc']:.4f} "
              f"t30 {m['forecast_t30_mae_c']:.4f} ({info['detik_latih']:.0f}s)", flush=True)

    xd, _ = tl.prepare_xgb_data()
    import xgboost as xgb
    from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

    from ml.preprocess.build_windows import FAILURE_CLASSES

    clf = xgb.XGBClassifier(objective="multi:softprob", num_class=len(FAILURE_CLASSES),
                            disable_default_eval_metric=True, **tl.xgb_params(SEEDS[0], kind))
    clf.fit(xd["Xtr"], xd["mode_tr"])
    pred = clf.predict_proba(xd["Xva"]).argmax(1)
    p, r, f1, s = precision_recall_fscore_support(xd["mode_va"], pred, labels=range(len(FAILURE_CLASSES)),
                                                  zero_division=0)
    hasil["xgb_clf"] = {
        "per_kelas": {cl: {"presisi": float(p[i]), "recall": float(r[i]), "f1": float(f1[i]), "n": int(s[i])}
                      for i, cl in enumerate(FAILURE_CLASSES)},
        "confusion": confusion_matrix(xd["mode_va"], pred, labels=range(len(FAILURE_CLASSES))).tolist(),
        "per_bucket_onset": per_bucket(pred, xd["mode_va"], onset),
    }

    # ringkasan: rata-rata per kelas & per bucket atas 5 seed GRU
    kelas = list(FAILURE_CLASSES)
    hasil["ringkas_gru"] = {
        "f1_per_kelas_mean": {k: float(np.mean([hasil["gru"][s]["per_kelas"][k]["f1"] for s in hasil["gru"]]))
                              for k in kelas},
        "akurasi_per_bucket_mean": {b: float(np.mean([hasil["gru"][s]["per_bucket_onset"][b]["akurasi_mode"]
                                                      for s in hasil["gru"]]))
                                    for b in next(iter(hasil["gru"].values()))["per_bucket_onset"]},
    }
    path = write_json(RESULTS_DIR / a.tag / "B3" / "diagnosis.json", hasil)
    print("\nF1 per kelas (GRU mean 5 seed | XGB):")
    for k in kelas:
        g, x = hasil["ringkas_gru"]["f1_per_kelas_mean"][k], hasil["xgb_clf"]["per_kelas"][k]
        print(f"  {k:20s} {g:.3f} | {x['f1']:.3f}  (n={x['n']})")
    print("Akurasi mode vs menit sejak onset (GRU mean | XGB):")
    for b, v in hasil["ringkas_gru"]["akurasi_per_bucket_mean"].items():
        print(f"  {b:10s} {v:.3f} | {hasil['xgb_clf']['per_bucket_onset'][b]['akurasi_mode']:.3f}")
    print("Tersimpan:", path)


if __name__ == "__main__":
    main()
