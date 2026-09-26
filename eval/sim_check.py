"""Regression check on the NEW simulator's held-out test trips, complementing run_eval.py (dataset v4).

Rule changes are tuned while looking at v4; this guards against them just fitting v4's quirks.
Uses the test split of ml/dataset_v3.parquet (prep_windows.split_trips, seed 0: the trips the GRU and
XGBoost never trained on) and mirrors the developers' engine test in ml/CHECKPOINT2_CONTEXT.md, per trip:
breaching trips warned before the breach (and lead time), healthy trips with any warning,
non-breaching door trips with warnings, sensor-fault trips flagged.

dataset_v3.parquet is not in git (~80 MB); get it from the model owner or regenerate it
(coldtrack_sim.generate_dataset, see ml/CHECKPOINT2_CONTEXT.md).

Usage: python -m eval.sim_check [--data ml/dataset_v3.parquet]
"""

import argparse
import json

import numpy as np
import pandas as pd

from eval.common import ROOT
from app.core import prep_windows
from app.inference import inference_engine

TRIP_COLS = ["T_sensor", "T_amb", "RH_amb", "door_open", "moving", "hour_of_day",
             "mass_kg", "c_kj_kgc", "t_lo", "t_hi"]


def run(path):
    ds = pd.read_parquet(path)
    test = prep_windows.split_trips(ds)["test"]
    rows = []
    for tid, g in ds[ds.trip_id.isin(test)].groupby("trip_id"):
        g = g.sort_values("minute").reset_index(drop=True)
        t_lo, t_hi = g.t_lo[0], g.t_hi[0]
        prod = {"t_lo": t_lo, "t_hi": t_hi, "c": g.c_kj_kgc[0], "mass_kg": g.mass_kg[0],
                # trips start at the setpoint (generate_dataset: T_init = t_set)
                "t_set": float(g.T_cargo[0])}
        trip = g[TRIP_COLS].assign(trip_id=0, ev_A1=0.0)
        out = inference_engine.analyze_trip(trip, prod).set_index("minute")
        br = g.index[g.is_breach == 1]
        first = int(br.min()) if len(br) else None
        warn, krit = out.index[out.status != "AMAN"], out.index[out.status == "KRITIS"]
        rows.append({
            "scenario": g.scenario[0], "breach_minute": first,
            "warned": bool(first is not None and len(warn) and warn.min() <= first),
            "kritis": bool(first is not None and len(krit) and krit.min() <= first),
            "lead_warn": first - warn.min() if first is not None and len(warn) else np.nan,
            "lead_kritis": first - krit.min() if first is not None and len(krit) else np.nan,
            "any_warning": bool(len(warn)), "any_kritis": bool(len(krit)),
            "sensor_flag": bool((out.sensor_status >= 1).any()),
        })
    T = pd.DataFrame(rows)
    breach = T.breach_minute.notna()
    B = T[breach & (T.breach_minute >= 59)]          # outputs start at minute 59
    healthy = T[(T.scenario == "A0") & ~breach]
    door_ok = T[T.scenario.str.contains("A1") & ~T.scenario.str.contains("A3") & ~breach]
    a3 = T[T.scenario.str.contains("A3")]
    return {
        "n_test_trips": int(len(T)), "n_breach_scorable": int(len(B)),
        "breach_warned_before": float(B.warned.mean()),
        "breach_kritis_before": float(B.kritis.mean()),
        "median_lead_warn_min": float(B.lead_warn[B.warned].median()),
        "median_lead_kritis_min": float(B.lead_kritis[B.kritis].median()),
        "n_healthy": int(len(healthy)), "healthy_trips_any_warning": float(healthy.any_warning.mean()),
        "n_door_no_breach": int(len(door_ok)),
        "door_no_breach_any_warning": float(door_ok.any_warning.mean()),
        "door_no_breach_any_kritis": float(door_ok.any_kritis.mean()),
        "n_sensor_fault": int(len(a3)), "sensor_fault_trips_flagged": float(a3.sensor_flag.mean()),
        "non_sensor_trips_flagged": float(T[~T.scenario.str.contains("A3")].sensor_flag.mean()),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "ml/dataset_v3.parquet"))
    print(json.dumps(run(ap.parse_args().data), indent=2))
