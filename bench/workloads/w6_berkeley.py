"""W6 -- model sensor-health Berkeley: pembangunan fitur (CPU) + latih XGBoost CPU hist vs cuda.

Parameter XGBoost dibekukan = parameter terbaik varian "kesehatan" dari B4
(bench/results/g16-gpu/B4/val_kesehatan.json), sehingga semua device melatih model yang sama.
Kualitas: PR-AUC mote val (cek paritas antar-device). Butuh data/berkeley/data.txt (lihat
bench/D0_OLD.md); tanpa data, config dicatat "tidak berlaku".
"""

import json
import time

import numpy as np

from bench.common import RESULTS_DIR
from bench.harness import run_config, tidak_berlaku

SUMBER_PARAMS = RESULTS_DIR / "g16-gpu" / "B4" / "val_kesehatan.json"


def _satu(dev, quick):
    import xgboost as xgb

    from ml.sensor_health import evaluate as ev
    from ml.sensor_health import features as sf

    t0 = time.perf_counter()
    df, info = sf.bangun()
    t_fitur = time.perf_counter() - t0
    src = json.loads(SUMBER_PARAMS.read_text(encoding="utf-8"))
    cols, params = src["fitur"], dict(src["sweep"]["params"])
    if quick:
        params["n_estimators"] = 20
    tr, va = df[df["split"] == "train"], df[df["split"] == "val"]
    m = xgb.XGBClassifier(
        objective="binary:logistic", tree_method="hist", device=dev, random_state=0, n_jobs=-1, **params
    )
    t1 = time.perf_counter()
    m.fit(tr[cols].to_numpy(np.float32), tr["y_24j"].to_numpy())
    t_latih = time.perf_counter() - t1
    t2 = time.perf_counter()
    s = m.predict_proba(va[cols].to_numpy(np.float32))[:, 1]
    t_pred = time.perf_counter() - t2
    return {
        "waktu": {
            "muat_s": info["muat_s"],
            "fitur_s": info["fitur_s"],
            "bangun_total_s": t_fitur,
            "latih_s": t_latih,
            "prediksi_s": t_pred,
        },
        "n_jendela": info["n_jendela"],
        "metrik_val": {"pr_auc": ev.ringkas(va, s, 0.5)["pr_auc"]},
    }


def run(ctx):
    from ml.sensor_health.data import DATA_DIR

    files = []
    for cid, dev in [("cpu_hist", "cpu"), ("cuda_hist", "cuda")]:
        if ctx.configs and cid not in ctx.configs:
            continue
        cfg = {"device": dev, "params_dari": str(SUMBER_PARAMS.name)}
        if not (DATA_DIR / "data.txt").exists():
            files += tidak_berlaku(ctx, "W6", cid, cfg, "data/berkeley/data.txt belum diunduh")
            continue
        if dev == "cuda" and ctx.device != "cuda":
            files += tidak_berlaku(ctx, "W6", cid, cfg, "XGBoost device=cuda butuh GPU NVIDIA")
            continue
        if dev == "cpu" and ctx.device == "cuda":
            print(f"  {cid}: diukur di tag *-cpu")
            continue
        files += run_config(ctx, "W6", cid, cfg, lambda seed, pemanasan, dev=dev: _satu(dev, ctx.quick))
    return files
