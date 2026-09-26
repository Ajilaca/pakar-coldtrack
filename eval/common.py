"""Shared loading + scoring helpers for the ColdTrack AI evaluation suite.

Scores the system AS DEPLOYED (backend/app/inference.py: core engine + coldtrack_gru.onnx +
coldtrack_ttb.onnx) on the held-out TEST split of dataset v4, split by trip_id -- the same trips
and the same window selection as the baseline, so before/after numbers are comparable.

v4 has no cargo mass; like production, the cargo profile's mass_kg_default is used.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.inference import WINDOW, cargo_params, inference_engine, readings_to_trip  # noqa: E402
from app.schemas import TelemetryReading  # noqa: E402

DATA_PATH = ROOT / "data/processed/v4_seed1000_700trips.parquet"   # run_eval --data overrides
DATA_INFO = {"data": DATA_PATH.name, "kind": "v4_old_generator", "split": "test"}
HORIZONS = [15, 30, 60]
SENTINEL = 999.0

# parquet cargo_type -> backend/config.yaml cargo_profiles key
CARGO_TO_PROFILE = {
    "vaksin_2_8C": "vaksin_2_8C",
    "daging_beku": "daging_beku_-18C",
    "sayur_buah": "buah_segar_2_4C",
    "ikan_segar": "ikan_segar_0_5C",
    "produk_susu": "produk_susu_2_4C",
}

# v4 fault modes -> the three events the new model detects. Others have no event of their own;
# they are only judged through status/TTB (docs/model_card.md, ml/CHECKPOINT2_CONTEXT.md).
EVENT_OF_MODE = {"A1": "door", "A7": "shock", "A5": "sensor", "A6": "sensor"}
EVENT_LABEL = {"door": "pintu_terbuka_lama", "shock": "kejutan_ambien_ekstrem", "sensor": "masalah_sensor"}
EVENTS = list(EVENT_LABEL)


def load_test_trips() -> dict[int, pd.DataFrame]:
    """v4 by default; a new-simulator parquet (eval/new_sim_data.py) when DATA_PATH points at one."""
    global DATA_INFO
    from eval import new_sim_data
    if new_sim_data.is_new_sim(DATA_PATH):
        trips, DATA_INFO = new_sim_data.load_trips(DATA_PATH)
        return trips
    DATA_INFO = {"data": Path(DATA_PATH).name, "kind": "v4_old_generator", "split": "test"}
    df = pd.read_parquet(DATA_PATH)
    df = df[df["split"] == "test"]
    return {tid: g.sort_values("minute").reset_index(drop=True) for tid, g in df.groupby("trip_id")}


def trip_readings(g: pd.DataFrame, temp: np.ndarray | None = None, hour_shift: int = 0) -> list[TelemetryReading]:
    """Rebuild timestamps so ts.hour == hour_of_day (trips don't start on the hour)."""
    hours = g["hour_of_day"].to_numpy()
    flips = np.flatnonzero(np.diff(hours) != 0)
    min_into_hour = (60 - (flips[0] + 1)) % 60 if len(flips) else 0
    start = pd.Timestamp("2026-03-01") + pd.Timedelta(hours=int(hours[0]) + hour_shift, minutes=int(min_into_hour))
    temp = g["temp_c"].to_numpy() if temp is None else temp
    # Lost packets (NaN) are not valid JSON; the gateway repeats the last value. Windows with a gap
    # in their last 60 minutes are excluded from scoring (eval_rows), as in the baseline.
    temp = pd.Series(temp).ffill().bfill().to_numpy()
    return [
        TelemetryReading(ts=start + pd.Timedelta(minutes=int(m)), temp_c=float(t), humidity=float(h),
                         ambient_c=float(a), door_open=bool(d), reefer_on=bool(r), speed_kmh=float(v),
                         harsh_events=int(e), solar_radiation=float(sr))
        for m, t, h, a, d, r, v, e, sr in zip(
            g.minute, temp, g.humidity, g.ambient_c, g.door_open, g.reefer_on, g.speed_kmh,
            g.harsh_events, g.solar_radiation)
    ]


def score_trip(g: pd.DataFrame, temp: np.ndarray | None = None, hour_shift: int = 0) -> pd.DataFrame:
    """Deployed output for every minute of one trip (inference_engine.analyze_trip)."""
    prof = CARGO_TO_PROFILE[g["cargo_type"].iloc[0]]
    prod = cargo_params(prof, float(g["mass_kg"].iloc[0]) if "mass_kg" in g else None)  # v4: no mass -> default
    return inference_engine.analyze_trip(readings_to_trip(trip_readings(g, temp, hour_shift), prod), prod)


def eval_rows(trips: dict[int, pd.DataFrame], **kw) -> pd.DataFrame:
    """One row per evaluated window: deployed outputs + ground truth.

    Window selection = baseline's: t in [W-1, n-1-60], dropping windows with a gap in the last
    60 readings or in the forecast targets.
    """
    rows = []
    for tid, g in trips.items():
        n = len(g)
        if n - WINDOW - max(HORIZONS) < 0:
            continue
        out = score_trip(g, **kw).set_index("minute")
        temp = g["temp_c"].to_numpy()
        # forecast target: cargo temperature. v4 has no separate one (sensor == cargo there).
        target = g["forecast_target_c"].to_numpy() if "forecast_target_c" in g else temp
        for t in range(WINDOW - 1, n - max(HORIZONS)):
            tg = [target[t + h] for h in HORIZONS]
            if np.isnan(temp[t - WINDOW + 1:t + 1]).any() or np.isnan(tg).any():
                continue
            r = out.loc[t].to_dict()
            mode = g["failure_mode"].iloc[t]
            onset = g["onset_minute"].iloc[t]
            r.update(
                trip_id=tid, t=t, cargo_type=g["cargo_type"].iloc[0], raw_mode=mode,
                event=EVENT_OF_MODE.get(mode), y_ttb=float(g["time_to_breach"].iloc[t]),
                y15=tg[0], y30=tg[1], y60=tg[2], y30_true=float(g["temp_true_c"].iloc[t + 30]),
                temp_now=temp[t], temp_now_5=temp[t - 5],
                min_since_onset=t - onset if mode != "A0" and not np.isnan(onset) else np.nan,
            )
            rows.append(r)
    return pd.DataFrame(rows)
