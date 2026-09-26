"""New-simulator data (coldtrack_sim v3, e.g. ml/dataset_v3.parquet) -> the per-trip layout eval/ reads.

Lets run_eval.py score the SAME 19 acceptance checks, with the SAME thresholds, on the data the new
model was trained for (in-distribution), next to the v4 run (out-of-distribution).
    python -m eval.run_eval --data ml/dataset_v3.parquet --tag sim_iter2
    EVAL_TAG=sim_iter2 pytest eval/test_baseline.py -q

Trips: test split of prep_windows.split_trips (seed 0) -- the trips the GRU and XGBoost never trained on,
the same ones eval/sim_check.py uses.

Mapping, and what it means for the checks
  temp_c <- T_sensor (cabin sensor, faults included)    ambient_c <- T_amb    humidity <- RH_amb
  door_open <- door_open    speed_kmh <- 60 * moving    reefer_on <- reefer_duty > 0
  solar_radiation, harsh_events <- 0   (not simulated; the new model does not read them)
  hour_of_day <- floor(hour_of_day)    (trip_readings rebuilds ts from whole hours, as for v4)
  time_to_breach <- minutes to the next is_breach row (0 in breach, 999 = no breach ahead)
  forecast target <- T_cargo           (the GRU forecasts cargo temperature; in v4 sensor == cargo)
  events <- ev_A1 door (open >= 20 min), ev_A2 ambient shock, ev_A3 sensor fault, per row = the training
            labels. Coded as v4 fault modes so the checks work unchanged: door -> A1, shock -> A7,
            sensor -> A5. Rows with two events at once take one code, priority sensor > door > shock
            (the order the deployed diagnosis uses); combo_events keeps the full set.
  cargo -> backend profile, as an operator would pick it: frozen -> daging_beku_-18C, ikan fresh ->
            ikan_segar_0_5C, sayur/buah fresh -> buah_segar_2_4C, susu_telur fresh -> produk_susu_2_4C.
            The profile's c_kj_kgc and t_set are used (as in production); the TRUE mass is sent.
  EXCLUDED: daging fresh (0-4 C): no backend profile has that range. Counted in the results JSON.
  NOT PRESENT: vaccine (2-8 C) is not in the new simulator, so the "every cargo profile" check
            cannot pass on this data by construction.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from app.core import prep_windows  # noqa: E402

SENTINEL = 999.0
EVENT_CODE = [("ev_A3", "A5"), ("ev_A1", "A1"), ("ev_A2", "A7")]  # priority order
EVENT_NAME = {"ev_A1": "door", "ev_A2": "shock", "ev_A3": "sensor"}


def cargo_type(category: str, state: str) -> str | None:
    """New-sim product -> eval cargo_type key (eval/common.CARGO_TO_PROFILE)."""
    if state == "frozen":
        return "daging_beku"
    return {"ikan": "ikan_segar", "sayur": "sayur_buah", "buah": "sayur_buah",
            "susu_telur": "produk_susu"}.get(category)  # daging fresh -> None (no profile)


def _ttb(is_breach: np.ndarray) -> np.ndarray:
    n = len(is_breach)
    out = np.full(n, SENTINEL)
    nxt = None
    for i in range(n - 1, -1, -1):
        if is_breach[i]:
            nxt = i
        if nxt is not None:
            out[i] = float(nxt - i)
    return out


def convert_trip(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("minute").reset_index(drop=True)
    ev = {c: g[c].to_numpy().astype(bool) for c, _ in EVENT_CODE}
    mode = np.full(len(g), "A0", dtype=object)
    for col, code in reversed(EVENT_CODE):  # lowest priority first, overwritten by higher
        mode[ev[col]] = code
    combo = ["+".join(EVENT_NAME[c] for c, _ in EVENT_CODE if ev[c][i]) for i in range(len(g))]
    onset = pd.Series(np.arange(len(g))).groupby(pd.Series(mode)).transform("min").to_numpy().astype(float)
    return pd.DataFrame({
        "minute": g.minute.to_numpy(),
        "temp_c": g.T_sensor.to_numpy(float),
        "humidity": g.RH_amb.to_numpy(float),
        "ambient_c": g.T_amb.to_numpy(float),
        "door_open": g.door_open.to_numpy(float) > 0.5,
        "reefer_on": g.reefer_duty.to_numpy(float) > 0,
        "speed_kmh": 60.0 * g.moving.to_numpy(float),
        "harsh_events": 0,
        "solar_radiation": 0.0,
        "hour_of_day": np.floor(g.hour_of_day.to_numpy(float)).astype(int) % 24,
        "cargo_type": cargo_type(g.category.iloc[0], g.state.iloc[0]),
        "mass_kg": float(g.mass_kg.iloc[0]),
        "failure_mode": mode,
        "combo_events": combo,
        "onset_minute": np.where(mode == "A0", np.nan, onset),
        "time_to_breach": _ttb(g.is_breach.to_numpy().astype(bool)),
        "temp_true_c": g.T_cargo.to_numpy(float),
        "forecast_target_c": g.T_cargo.to_numpy(float),
    })


def load_trips(path, split: str = "test") -> tuple[dict[int, pd.DataFrame], dict]:
    ds = pd.read_parquet(path)
    ids = prep_windows.split_trips(ds)[split] if split in ("train", "val", "test") else set(ds.trip_id)
    trips, excluded = {}, {}
    for tid, g in ds[ds.trip_id.isin(ids)].groupby("trip_id"):
        ct = cargo_type(g.category.iloc[0], g.state.iloc[0])
        if ct is None:
            key = f"{g.category.iloc[0]}/{g.state.iloc[0]}"
            excluded[key] = excluded.get(key, 0) + 1
            continue
        trips[tid] = convert_trip(g)
    info = {"data": Path(path).name, "kind": "new_simulator_v3", "split": split,
            "n_trips_used": len(trips), "excluded_trips_no_backend_profile": excluded}
    return trips, info


def is_new_sim(path) -> bool:
    import pyarrow.parquet as pq
    return "T_sensor" in pq.read_schema(path).names
