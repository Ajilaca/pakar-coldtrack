"""Kecocokan golden fitur+pohon bilangan bulat (hw/golden/trees.py) dengan XGBoost float, split VAL.

Untuk kedua model beku B10 (#7 tanpa duty, #8 dengan duty sintetis): kelas argmax golden vs
XGBoost.predict pada fitur float bench/b10_test_once.fitur, Macro F1 label v5, dan selisih margin.

  python -m hw.golden.check_trees            -> hw/results/parity_trees.json
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bench import b8_lib as b8
from bench import b9_lib as b9
from bench.b8_label_konteks import metrik_kelas
from bench.b10_test_once import fitur as fitur_float
from hw.golden import trees as ph

MODEL = {"b8_xgb_chip_v5_konteks": False, "b9_xgb_chip_v5_konteks_duty_sintetis": True}


def duty_trip(g, tid):
    mode = next((m for m in pd.unique(g["failure_mode"]) if m != "A0"), "A0")
    onset = 0 if pd.isna(g["onset_minute"].iloc[0]) else int(g["onset_minute"].iloc[0])
    return b9.sinyal_trip(g, mode, onset, np.random.default_rng(9000 + int(tid)))[0]


def main():
    import xgboost as xgb

    t0 = time.perf_counter()
    d = b8.muat("val")
    df = pd.read_parquet(ROOT / "data/processed/v4_seed1000_700trips.parquet")
    trips = {int(t): g.sort_values("minute").reset_index(drop=True) for t, g in df[df.split == "val"].groupby("trip_id")}
    hasil = {}
    for nama, duty in MODEL.items():
        path = ROOT / f"bench/results/lokal-cpu/B10/{nama}.json"
        Xf, _ = fitur_float("val", duty)
        clf = xgb.XGBClassifier()
        clf.load_model(path)
        p_float = clf.predict_proba(Xf)
        margin_float = clf.predict(Xf, output_margin=True)
        m = ph.muat_model(path, duty)
        cache, kelas, margin = {}, [], []
        for tid, t in zip(d["trip"], d["menit"]):
            if tid not in cache:
                g = trips[int(tid)]
                cache = {tid: ph.ffill_temp(ph.kuantisasi_trip(g, duty_trip(g, tid) if duty else None))}
            f = ph.fitur_bulat(cache[tid], int(t), duty)
            s = ph.skor_bulat(m, f)
            margin.append(s)
            kelas.append(max(range(len(s)), key=lambda k: (s[k], -k)))
        kelas = np.array(kelas)
        margin = np.array(margin, dtype=float) / (1 << ph.FRAK_DAUN)
        pred_float = p_float.argmax(1)
        onehot = np.eye(7)[kelas]
        hasil[nama] = {
            "jendela": len(kelas),
            "kelas_sama_dengan_xgboost": float((kelas == pred_float).mean()),
            "jumlah_beda": int((kelas != pred_float).sum()),
            "margin_selisih_median": float(np.median(np.abs(margin - margin_float))),
            "margin_selisih_p99": float(np.percentile(np.abs(margin - margin_float), 99)),
            "macro_f1_float": metrik_kelas(d["y_baru"], p_float)["macro_f1"],
            "macro_f1_bulat": metrik_kelas(d["y_baru"], onehot)["macro_f1"],
            "jumlah_simpul": sum(len(p["simpul"]) for p in m["pohon"]),
            "jumlah_pohon": len(m["pohon"]),
        }
        print(nama, json.dumps(hasil[nama], indent=1), flush=True)
    hasil["detik"] = time.perf_counter() - t0
    out = ROOT / "hw/results/parity_trees.json"
    out.write_text(json.dumps(hasil, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
