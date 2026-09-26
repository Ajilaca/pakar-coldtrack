"""Hybrid inference for ColdTrack AI (checkpoint-2 model, see ml/CHECKPOINT2_CONTEXT.md).

- core.engine (physics + sensor rules): status AMAN/WASPADA/KRITIS, physics TTB, reason.
- coldtrack_gru.onnx: event probabilities (door / ambient shock / sensor) + cargo temp +15/30/60.
- coldtrack_ttb.onnx: XGBoost TTB, informational only.
Status and displayed TTB come from the engine alone, matching how it was validated.
"""

import logging
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
import pandas as pd

from app.config import settings
from app.core import engine, observer, prep_windows, ttb_features
from app.schemas import TelemetryReading

logger = logging.getLogger("coldtrack.inference")

WINDOW = prep_windows.W
TTB_MAX = 240.0
EVENT_LABELS = ["pintu_terbuka_lama", "kejutan_ambien_ekstrem", "masalah_sensor"]
RISK_BAND = {"AMAN": (0.0, 0.34), "WASPADA": (0.45, 0.69), "KRITIS": (0.85, 1.0)}
SENSOR_RISK_BAND = (0.45, 0.60)


def _session(rel_path: str) -> ort.InferenceSession | None:
    path = (Path(__file__).resolve().parent.parent / rel_path).resolve()
    if not path.exists():
        logger.warning(f"ONNX model not found at {path}")
        return None
    try:
        return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to load {path}: {e}")
        return None


def cargo_params(cargo_profile: str, mass_kg: float | None) -> dict[str, float]:
    profiles = settings.get("cargo_profiles", {})
    p = profiles.get(cargo_profile, profiles.get("vaksin_2_8C", {}))
    lo, hi = float(p.get("min_temp_c", 2.0)), float(p.get("max_temp_c", 8.0))
    return {
        "t_lo": lo,
        "t_hi": hi,
        "t_set": float(p.get("t_set_c", lo + 0.4 * (hi - lo))),  # same default as coldtrack_sim.get_product
        "c": float(p.get("c_kj_kgc", 3.8)),
        "mass_kg": float(mass_kg or p.get("mass_kg_default", 1000.0)),
    }


def readings_to_trip(readings: list[TelemetryReading], prod: dict[str, float]) -> pd.DataFrame:
    """One trip in the column layout the ml/ pipeline was trained on."""
    ts = pd.to_datetime([r.ts for r in readings])
    df = pd.DataFrame(
        {
            "ts": ts,
            "T_sensor": [r.temp_c for r in readings],
            "T_amb": [r.ambient_c for r in readings],
            "RH_amb": [r.humidity for r in readings],
            "door_open": [float(r.door_open) for r in readings],
            "moving": [float(r.speed_kmh >= 1.0) for r in readings],
        }
    ).sort_values("ts").reset_index(drop=True)
    df["hour_of_day"] = df.ts.dt.hour + df.ts.dt.minute / 60.0
    df["trip_id"] = 0
    df["mass_kg"] = prod["mass_kg"]
    df["c_kj_kgc"] = prod["c"]
    df["t_lo"] = prod["t_lo"]
    df["t_hi"] = prod["t_hi"]
    df["ev_A1"] = 0.0  # label column clean_trip expects; unused at inference
    return df


def _diagnose(ev: np.ndarray, sensor_status: int, status: str, door_open_now: bool) -> dict[str, Any]:
    """Sensor faults come from the rule layer only: GRU A3 (AUC 0.85) false-flags healthy sensors,
    the rules had 0 false flags in 1,004 trips. Rule-derived labels report confidence 1.0.
    The label never says normal while the engine status is WASPADA/KRITIS."""
    if sensor_status >= 1:
        return {"label": "masalah_sensor", "confidence": 1.0 if sensor_status == 2 else 0.6}
    learned = ev[:2]  # A1 door open long, A2 ambient shock
    if learned.max() >= 0.5:
        i = int(learned.argmax())
        return {"label": EVENT_LABELS[i], "confidence": float(round(learned[i], 3))}
    if status != "AMAN":
        label = "pintu_terbuka" if door_open_now else "suhu_muatan_mendekati_batas"
        return {"label": label, "confidence": 1.0}
    return {"label": "normal_sehat", "confidence": float(round(1.0 - learned.max(), 3))}


def _risk_index(status: str, ttb_phys: float, sensor_bad: bool) -> float:
    lo, hi = SENSOR_RISK_BAND if sensor_bad else RISK_BAND[status]
    raw = 1.0 - min(max(ttb_phys, 0.0), TTB_MAX) / TTB_MAX
    return float(round(min(max(raw, lo), hi), 2))


class HybridInferenceEngine:
    def __init__(self) -> None:
        cfg = settings.get("model", {})
        self.gru = _session(cfg.get("gru_onnx_path", "models/coldtrack_gru.onnx"))
        self.ttb = _session(cfg.get("ttb_onnx_path", "models/coldtrack_ttb.onnx"))

    @property
    def is_ready(self) -> bool:
        return self.gru is not None

    def _gru(self, x: np.ndarray, s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        ev, temp = self.gru.run(None, {"x": x, "s": s})
        return ev[0], temp[0]

    def _xgb_ttb(self, trip: pd.DataFrame, x: np.ndarray, s: np.ndarray) -> float | None:
        if self.ttb is None:
            return None
        # Same feature assembly as ml/run_train_xgb.py; stride=1 so the last row is "now".
        f1, _ = ttb_features.build(x, s)
        f2, _ = observer.windows_extra(trip, [0], W=WINDOW, stride=1)
        f3, _ = observer.projection_features(trip, [0], W=WINDOW, stride=1)
        feats = np.hstack([f1, f2[-1:], f3[-1:]]).astype(np.float32)
        out = self.ttb.run(None, {"features": feats})[0]
        return float(round(np.clip(np.ravel(out)[0], 0.0, TTB_MAX), 1))

    def predict(
        self, readings: list[TelemetryReading], cargo_profile: str, mass_kg: float | None = None
    ) -> dict[str, Any]:
        """Needs >= 60 readings (validated in main.py). Uses the full history for the cargo observer."""
        prod = cargo_params(cargo_profile, mass_kg)
        trip = readings_to_trip(readings, prod)

        now = engine.run(trip, prod, prod["mass_kg"]).iloc[-1]
        sensor_status = int(now.sensor_status)
        ttb_show = None if pd.isna(now.ttb_show) else float(round(now.ttb_show, 1))

        result: dict[str, Any] = {
            "status": now.status_txt,
            "reason": now.reason,
            "time_to_breach_min": ttb_show,
            "risk_index": _risk_index(now.status_txt, float(now.ttb_phys), sensor_status >= 1),
            "sensor_status": sensor_status,
            "forecast": None,
            "failure_mode": None,
            "ttb_model_min": None,
        }

        if self.gru is None:
            return result

        clean = prep_windows.clean_trip(trip)
        x = clean[prep_windows.FEATS].to_numpy(np.float32)[-WINDOW:][None]
        s = clean[prep_windows.STATIC].iloc[:1].to_numpy(np.float32)
        ev, temp = self._gru(x, s)

        result["forecast"] = {
            "t15": float(round(temp[0], 2)),
            "t30": float(round(temp[1], 2)),
            "t60": float(round(temp[2], 2)),
        }
        result["failure_mode"] = _diagnose(ev, sensor_status, now.status_txt, bool(trip.door_open.iloc[-1]))
        result["ttb_model_min"] = self._xgb_ttb(trip, x, s)
        return result


inference_engine = HybridInferenceEngine()
