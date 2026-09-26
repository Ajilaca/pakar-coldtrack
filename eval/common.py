"""Shared loading + inference helpers for the ColdTrack AI evaluation suite.

The suite evaluates the system AS DEPLOYED (backend/models/*.onnx + backend rule
engine), on the held-out TEST split of dataset v4, split by trip_id.
"""

import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from ml.preprocess.build_windows import (  # noqa: E402
    HORIZONS, MODE_MAPPING, WINDOW_SIZE, FAILURE_CLASSES, CLASS_TO_IDX,
    hitung_ulang_reefer_duration,
)
from ml.tests.test_data_contract import FEATURE_COLUMNS  # noqa: E402

DATA_PATH = ROOT / "data/processed/v4_seed1000_700trips.parquet"
GRU_PATH = ROOT / "backend/models/coldtrack.onnx"
TTB_PATH = ROOT / "backend/models/coldtrack_ttb.onnx"
SENTINEL = 999.0
TTB_CAP = 30.0          # backend/config.yaml -> model.ttb_display_cap_min
IDX_TEMP = FEATURE_COLUMNS.index("temp_c")
IDX_DTEMP = FEATURE_COLUMNS.index("delta_temp")
IDX_AMB = FEATURE_COLUMNS.index("ambient_c")
IDX_DAMB = FEATURE_COLUMNS.index("delta_ambient")
IDX_HOUR = FEATURE_COLUMNS.index("hour_of_day")

# parquet cargo_type -> backend/config.yaml cargo_profiles key
CARGO_TO_PROFILE = {
    "vaksin_2_8C": "vaksin_2_8C",
    "daging_beku": "daging_beku_-18C",
    "sayur_buah": "buah_segar_2_4C",
    "ikan_segar": "ikan_segar_0_5C",
    "produk_susu": "produk_susu_2_4C",
}


def load_test_windows(stride: int = 1) -> dict:
    """Sliding 60-min windows of the TEST split, with metadata for slicing."""
    df = pd.read_parquet(DATA_PATH)
    df = df[df["split"] == "test"]
    X, yf, ym, yt, meta = [], [], [], [], []
    ts_rows = []
    for trip_id, g in df.groupby("trip_id"):
        g = g.sort_values("minute").reset_index(drop=True)
        n, max_h = len(g), max(HORIZONS)
        if n - WINDOW_SIZE - max_h < 0:
            continue
        feats = g[FEATURE_COLUMNS].values.astype(np.float32)
        temp = g["temp_c"].values.astype(np.float32)
        modes = g["failure_mode"].values
        onset = g["onset_minute"].values
        ttb = g["time_to_breach"].values.astype(np.float32)
        hours = g["hour_of_day"].values
        flips = np.flatnonzero(np.diff(hours) != 0)
        phase0 = (flips[0] + 1) if len(flips) else 0          # first row of a new hour
        day = np.concatenate([[0], np.cumsum(np.diff(hours) < 0)])
        for start in range(0, n - WINDOW_SIZE - max_h + 1, stride):
            end = start + WINDOW_SIZE
            t = end - 1
            w = hitung_ulang_reefer_duration(feats[start:end])
            tg = [temp[t + h] for h in HORIZONS]
            if np.isnan(w).any() or np.isnan(tg).any():
                continue
            X.append(w)
            yf.append(tg)
            ym.append(CLASS_TO_IDX[MODE_MAPPING[modes[t]]])
            yt.append(ttb[t])
            since = t - onset[t] if modes[t] != "A0" and not np.isnan(onset[t]) else np.nan
            meta.append((trip_id, g["cargo_type"].iloc[0], modes[t], since, t))
            ts_rows.append((day[start:end], hours[start:end], (np.arange(start, end) - phase0) % 60))
    m = pd.DataFrame(meta, columns=["trip_id", "cargo_type", "raw_mode", "min_since_onset", "t"])
    return {
        "X": np.stack(X).astype(np.float32), "y_forecast": np.array(yf, np.float32),
        "y_mode": np.array(ym), "y_ttb": np.array(yt, np.float32), "meta": m, "_ts": ts_rows,
    }


def make_payload(D: dict, i: int, cargo_profile: str) -> dict:
    """Window i -> /api/v1/analyze JSON body (ts rebuilt so ts.hour == hour_of_day)."""
    w = D["X"][i]
    day, hours, mins = D["_ts"][i]
    base = pd.Timestamp("2026-03-01")
    readings = []
    for k in range(WINDOW_SIZE):
        ts = base + pd.Timedelta(days=int(day[k]), hours=int(hours[k]), minutes=int(mins[k]))
        r = dict(zip(FEATURE_COLUMNS, w[k].tolist()))
        readings.append({
            "ts": ts.isoformat(), "temp_c": r["temp_c"], "humidity": r["humidity"],
            "ambient_c": r["ambient_c"], "door_open": bool(r["door_open"] >= 0.5),
            "reefer_on": bool(r["reefer_on"] >= 0.5), "speed_kmh": r["speed_kmh"],
            "harsh_events": int(round(r["harsh_events"])), "solar_radiation": r["solar_radiation"],
        })
    return {"shipment_id": f"EVAL-{i}", "cargo_profile": cargo_profile, "readings": readings}


class Models:
    def __init__(self):
        self.gru = ort.InferenceSession(str(GRU_PATH), providers=["CPUExecutionProvider"])
        self.ttb = ort.InferenceSession(str(TTB_PATH), providers=["CPUExecutionProvider"])

    def run(self, X: np.ndarray, chunk: int = 2048):
        f, p, t = [], [], []
        for s in range(0, len(X), chunk):
            xb = np.ascontiguousarray(X[s:s + chunk], dtype=np.float32)
            o = self.gru.run(None, {"window": xb})
            f.append(o[0]); p.append(o[1])
            t.append(np.ravel(self.ttb.run(None, {"window": xb})[0]))
        return np.concatenate(f), np.concatenate(p), np.concatenate(t)


def deployed_ttb(probs: np.ndarray, ttb_raw: np.ndarray) -> np.ndarray:
    """Mirror of backend/app/inference.py + main.py gating: NaN where nothing is shown."""
    pred = probs.argmax(1)
    shown = np.where((pred != 0) & (ttb_raw < TTB_CAP), ttb_raw, np.nan)
    sensor = pred == CLASS_TO_IDX["masalah_sensor"]
    shown[sensor] = np.nan
    return shown
