"""Investigasi G1: mengapa acuan XGBoost (ml/reports/baseline_metrics.json) tidak tereproduksi.

XGBoost dengan XGB_PARAMS deterministik (tanpa subsample/colsample, seed tidak berpengaruh), jadi
SD 5 seed = 0 dan aturan "acuan dalam mean +/- 2 SD" berubah menjadi "harus sama persis".

Riwayat git: baseline_metrics.json terakhir diubah 2026-08-06, SEBELUM 55a30fe (2026-08-13) yang
mengubah build_windows (hitung ulang reefer_duration_min per jendela). Saat commit baseline
(350cb41) DATA_PATH builder masih v3. Skrip ini menguji 2 builder x 2 dataset dengan XGBoost yang
terpasang. Builder lama dimuat langsung dari git (tidak disalin ke repo).

  python -m bench.g1_investigasi --tag g16-cpu

Hasil: bench/results/<tag>/B1/G1_investigasi.json
"""

import argparse
import json
import subprocess
import types

import numpy as np
import pandas as pd

from bench.common import RESULTS_DIR, ROOT, _git_exe, git_info, now_iso, write_json

COMMIT_BUILDER_LAMA = "350cb41"


def builder_lama():
    src = subprocess.run([_git_exe(), "-C", str(ROOT), "show", f"{COMMIT_BUILDER_LAMA}:ml/preprocess/build_windows.py"],
                         check=True, capture_output=True, text=True).stdout
    mod = types.ModuleType("build_windows_lama")
    exec(compile(src, f"{COMMIT_BUILDER_LAMA}:build_windows.py", "exec"), mod.__dict__)  # noqa: S102 -- kode repo sendiri
    return mod


def windows(builder, path):
    df = pd.read_parquet(path)
    out = {"train": [], "val": []}
    for _, g in df.groupby("trip_id"):
        s = g["split"].iloc[0]
        if s in out and (r := builder.build_windows_for_trip(g)) is not None:
            out[s].append(r)
    return {s: {k: np.concatenate([c[k] for c in v]) for k in v[0]} for s, v in out.items()}


def evaluasi(w):
    import xgboost as xgb
    from sklearn.metrics import average_precision_score, f1_score

    from ml.baselines import SENTINEL, XGB_PARAMS, aggregate

    tr, va = w["train"], w["val"]
    Xtr, Xva = aggregate(tr["X"]), aggregate(va["X"])
    mt, mv = tr["y_ttb"] != SENTINEL, va["y_ttb"] != SENTINEL
    params = {**XGB_PARAMS, "device": "cpu"}
    # persis ml/baselines.py: expm1 tanpa clip
    reg = xgb.XGBRegressor(**params).fit(Xtr[mt], np.log1p(tr["y_ttb"][mt]))
    ttb = float(np.abs(np.expm1(reg.predict(Xva[mv])) - va["y_ttb"][mv]).mean())
    clf = xgb.XGBClassifier(objective="multi:softprob", num_class=7, disable_default_eval_metric=True,
                            **params).fit(Xtr, tr["y_mode"])
    pr = clf.predict_proba(Xva)
    y = va["y_mode"]
    return {"n_val": len(Xva), "ttb_mae_menit": ttb,
            "macro_f1": float(f1_score(y, pr.argmax(1), average="macro")),
            "akurasi": float((pr.argmax(1) == y).mean()),
            "anomali_pr_auc": float(average_precision_score((y != 0).astype(int), 1 - pr[:, 0]))}


def main(argv=None):
    import xgboost as xgb

    from ml.preprocess import build_windows as builder_baru

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", required=True)
    a = ap.parse_args(argv)

    base = json.loads((ROOT / "ml/reports/baseline_metrics.json").read_text(encoding="utf-8"))
    acuan = {"ttb_mae_menit": base["ttb_mae_menit"]["xgboost"],
             "macro_f1": base["failure_mode"]["xgboost_macro_f1"],
             "akurasi": base["failure_mode"]["xgboost_akurasi"],
             "anomali_pr_auc": base["anomali_pr_auc"]["xgboost"]}
    hasil = {"waktu_utc": now_iso(), "git": git_info(), "xgboost": xgb.__version__, "acuan": acuan, "kombinasi": {}}
    lama = builder_lama()
    for nama_b, b in [("builder_lama_350cb41", lama), ("builder_sekarang", builder_baru)]:
        for ver in ["v3", "v4"]:
            m = evaluasi(windows(b, ROOT / f"data/processed/{ver}_seed1000_700trips.parquet"))
            m["selisih_vs_acuan"] = {k: m[k] - v for k, v in acuan.items()}
            hasil["kombinasi"][f"{nama_b}+{ver}"] = m
            print(f"{nama_b:22s} {ver}: " + " ".join(f"{k}={m[k]:.4f}" for k in acuan))
    print("acuan                     : " + " ".join(f"{k}={v:.4f}" for k, v in acuan.items()))
    print("Tersimpan:", write_json(RESULTS_DIR / a.tag / "B1" / "G1_investigasi.json", hasil))


if __name__ == "__main__":
    main()
