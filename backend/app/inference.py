"""Hybrid inference for ColdTrack AI.

- core.engine (physics + sensor rules): status AMAN/WASPADA/KRITIS, physics TTB, reason. Always.
- Diagnosis provider (forecast + failure_mode + informational ML TTB), chosen by one config flag
  `model.diagnosis_provider` in config.yaml:
    v3          (default) ml/reports/coldtrack_b3.onnx: GRU 3x128, 7 failure classes, window [n, 60, 12]
                 + coldtrack_ttb_window.onnx (XGBoost TTB, same window contract).
    checkpoint2  the previous model (ml/CHECKPOINT2_CONTEXT.md): 3 events + cargo-temp forecast
                 + its own XGBoost TTB. Kept for rollback.
Status and displayed TTB come from the engine alone with either provider, matching how they were
validated. Comparison and limitations: docs/model_card.md, bench/results/g16-cpu/B7/.
"""

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
import pandas as pd

from app.config import settings
from app.core import engine, observer, prep_windows, ttb_features
from app.preprocess import ONNX_FEATURE_COLUMNS, features_per_minute
from app.schemas import TelemetryReading

logger = logging.getLogger("coldtrack.inference")

BACKEND_DIR = Path(__file__).resolve().parent.parent
WINDOW = prep_windows.W
TTB_MAX = 240.0
RISK_BAND = {"AMAN": (0.0, 0.34), "WASPADA": (0.45, 0.69), "KRITIS": (0.85, 1.0)}
SENSOR_RISK_BAND = (0.45, 0.60)
PROVIDERS = ("v3", "checkpoint2")
DEFAULT_PROVIDER = "v3"

# Kelengkapan data (keputusan 2026-10-11, opsi 2). Model jendela dilatih HANYA pada jendela 60 menit
# tanpa bacaan hilang (ml/preprocess/build_windows membuang jendela ber-NaN); jendela berlubang
# adalah masukan di luar distribusi latih (selisih prob v3 median 0,021, maks 0,56 di val v4:
# bench/results/g16-cpu/B7). Bila ada jeda > GAP_DETIK antar bacaan di 60 bacaan terakhir,
# diagnosis ditandai kurang andal dan keyakinannya DIBATASI (pilihan tampilan konservatif, bukan
# nilai terkalibrasi). Status dari mesin fisika tidak berubah.
GAP_DETIK = 90
KEYAKINAN_MAKS_DATA_TIDAK_LENGKAP = 0.5


def kelengkapan_data(readings: list[TelemetryReading], window: int = 60) -> dict[str, Any]:
    ts = pd.to_datetime(sorted(r.ts for r in readings)[-window:])
    jeda = np.diff(ts.values).astype("timedelta64[s]").astype(float)
    n_gap = int((jeda > GAP_DETIK).sum())
    menit_hilang = int(np.clip(np.round(jeda / 60.0) - 1, 0, None).sum())
    if n_gap == 0:
        return {"data_lengkap": True, "catatan_data": None}
    return {"data_lengkap": False,
            "catatan_data": f"{menit_hilang} menit data hilang ({n_gap} jeda) dalam 60 bacaan terakhir; "
                            "diagnosis model kurang andal. Status tetap dari mesin fisika."}

# checkpoint-2: three independent events
EVENT_LABELS = ["pintu_terbuka_lama", "kejutan_ambien_ekstrem", "masalah_sensor"]

# v3: model class -> API label. Labels shared with checkpoint-2 keep their meaning (and the
# substring matching in app/rules.py: "pintu", "reefer", "sensor", "degradasi").
V3_API_LABEL = {
    "A0": "normal_sehat",
    "A1": "pintu_terbuka_lama",
    "A3": "reefer_mati_total",
    "A7": "kejutan_ambien_ekstrem",
    "A8": "prapendinginan_buruk",
    "degradasi_bertahap": "degradasi_bertahap",
    "masalah_sensor": "masalah_sensor",
}


def _session(rel_path: str) -> ort.InferenceSession | None:
    path = (BACKEND_DIR / rel_path).resolve()
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


def _guard_label(label: str, confidence: float, sensor_status: int, status: str, door_open_now: bool) -> dict[str, Any]:
    """Rules shared by both providers.

    Sensor faults come from the rule layer first (0 false flags in 1,004 trips; checkpoint-2's GRU
    false-flagged healthy sensors). The label never says normal while the engine status is
    WASPADA/KRITIS. Rule-derived labels report confidence 1.0 (0.6 for a suspected sensor)."""
    if sensor_status >= 1:
        return {"label": "masalah_sensor", "confidence": 1.0 if sensor_status == 2 else 0.6}
    if label == "normal_sehat" and status != "AMAN":
        return {"label": "pintu_terbuka" if door_open_now else "suhu_muatan_mendekati_batas", "confidence": 1.0}
    return {"label": label, "confidence": float(round(confidence, 3))}


def pilih_label_v3(prob: np.ndarray, api_labels: list[str]) -> tuple[str, float]:
    """Kelas teratas v3, KECUALI masalah_sensor: kerusakan sensor hanya boleh datang dari lapisan
    aturan (sama dengan prinsip checkpoint-2; keputusan user 2026-10-11). Masukan sintetis yang terlalu
    mulus (mis. form isian manual) menyerupai sensor macet bagi v3 meski sensornya sehat. Bila aturan
    menandai sensor, _guard_label menimpa label ini dengan masalah_sensor.

    Saat kelas teratas adalah masalah_sensor (dibuang), sisa kelas biasanya berpeluang kecil; aturan
    checkpoint-2 dipakai persis: kelas gangguan lain hanya dipakai bila peluangnya >= 0,5, selain itu
    normal_sehat dengan keyakinan 1 - maks(peluang kelas gangguan lain). Status bukan AMAN tetap
    diganti label aturan oleh _guard_label."""
    top = int(np.argmax(prob))
    if api_labels[top] != "masalah_sensor":
        return api_labels[top], float(prob[top])
    lain = [i for i, lab in enumerate(api_labels) if lab not in ("masalah_sensor", "normal_sehat")]
    j = max(lain, key=lambda i: prob[i])
    if prob[j] >= 0.5:
        return api_labels[j], float(prob[j])
    return "normal_sehat", 1.0 - float(prob[j])


def _risk_index(status: str, ttb_phys: float, sensor_bad: bool) -> float:
    lo, hi = SENSOR_RISK_BAND if sensor_bad else RISK_BAND[status]
    raw = 1.0 - min(max(ttb_phys, 0.0), TTB_MAX) / TTB_MAX
    return float(round(min(max(raw, lo), hi), 2))


class Checkpoint2Provider:
    """Previous diagnosis model, unchanged behaviour (rollback target)."""

    name = "checkpoint2"

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.gru = _session(cfg.get("gru_onnx_path", "models/coldtrack_gru.onnx"))
        self.ttb = _session(cfg.get("ttb_onnx_path", "models/coldtrack_ttb.onnx"))

    @property
    def is_ready(self) -> bool:
        return self.gru is not None

    def run(self, trip: pd.DataFrame, out: pd.DataFrame, feats: pd.DataFrame | None) -> None:
        clean = prep_windows.clean_trip(trip)
        x_feats = clean[prep_windows.FEATS].to_numpy(np.float32)
        ends = np.arange(WINDOW - 1, len(clean))
        x = x_feats[ends[:, None] - np.arange(WINDOW - 1, -1, -1)[None, :]]
        s = np.repeat(clean[prep_windows.STATIC].iloc[:1].to_numpy(np.float32), len(ends), axis=0)
        ev, temp = self.gru.run(None, {"x": x, "s": s})
        n = len(out)                                   # predict_last: hanya baris terakhir yang dipakai
        ev, temp, ends = ev[-n:], temp[-n:], ends[-n:]
        out[["ev_door", "ev_shock", "ev_sensor"]] = ev
        out[["t15", "t30", "t60"]] = temp.round(2)

        door_now = trip.door_open.to_numpy()[ends] > 0.5
        diag = []
        for e, ss, st, d in zip(ev, out.sensor_status, out.status, door_now):
            learned = e[:2]  # A1 door open long, A2 ambient shock; the sensor head is not trusted
            if learned.max() >= 0.5:
                i = int(learned.argmax())
                label, conf = EVENT_LABELS[i], float(learned[i])
            else:
                label, conf = "normal_sehat", 1.0 - float(learned.max())
            diag.append(_guard_label(label, conf, ss, st, d))
        out["label"] = [d["label"] for d in diag]
        out["confidence"] = [d["confidence"] for d in diag]

        if self.ttb is not None:
            # Same feature assembly as ml/run_train_xgb.py, one window per minute.
            f1, _ = ttb_features.build(x, s)
            f2, _ = observer.windows_extra(trip, [0], W=WINDOW, stride=1)
            f3, _ = observer.projection_features(trip, [0], W=WINDOW, stride=1)
            xgb = self.ttb.run(None, {"features": np.hstack([f1, f2, f3]).astype(np.float32)})[0]
            out["ttb_model"] = np.clip(np.ravel(xgb)[-n:], 0.0, TTB_MAX).round(1)

    def probabilities(self, row: pd.Series) -> dict[str, float] | None:
        return None


class V3Provider:
    """GRU 3x128 + summary stats, 7 failure classes (G3 2026-10-11, docs/model_card.md)."""

    name = "v3"

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.gru = _session(cfg.get("gru_onnx_path", "models/coldtrack_v3.onnx"))
        self.ttb = _session(cfg.get("ttb_onnx_path", "models/coldtrack_ttb_window.onnx"))
        contract = json.loads((BACKEND_DIR / cfg.get("labels_path", "models/coldtrack_v3.labels.json"))
                              .read_text(encoding="utf-8"))
        self.classes: list[str] = contract["kontrak"]["outputs"]["failure_prob"]["classes"]
        self.api_labels = [V3_API_LABEL[c] for c in self.classes]

    @property
    def is_ready(self) -> bool:
        return self.gru is not None

    @staticmethod
    def windows(feats: pd.DataFrame, ends: np.ndarray) -> np.ndarray:
        """[n, 60, 12] raw windows ending at `ends`. reefer_duration_min is counted from the window
        start, as in training (ml/preprocess/build_windows.hitung_ulang_reefer_duration)."""
        f = feats[ONNX_FEATURE_COLUMNS].to_numpy(np.float32)
        idx = ends[:, None] - np.arange(WINDOW - 1, -1, -1)[None, :]
        x = f[idx]
        run = feats["reefer_duration_min"].to_numpy(np.float32)          # running count from trip start
        pos_in_window = np.arange(1, WINDOW + 1, dtype=np.float32)[None, :]
        x[:, :, ONNX_FEATURE_COLUMNS.index("reefer_duration_min")] = np.minimum(run[idx], pos_in_window)
        return x

    def run(self, trip: pd.DataFrame, out: pd.DataFrame, feats: pd.DataFrame | None) -> None:
        if feats is None:
            raise ValueError("v3 provider needs the 12 per-minute features (preprocess.features_per_minute)")
        ends = np.arange(len(feats) - len(out), len(feats))   # len(out) = 1 untuk predict_last
        x = self.windows(feats, ends)
        fc, prob, _ = self.gru.run(None, {"window": x})
        out[["t15", "t30", "t60"]] = fc.round(2)
        out[[f"p_{lab}" for lab in self.api_labels]] = prob
        door_now = feats["door_open"].to_numpy()[ends] > 0.5
        diag = [_guard_label(*pilih_label_v3(p, self.api_labels), ss, st, d)
                for p, ss, st, d in zip(prob, out.sensor_status, out.status, door_now)]
        out["label"] = [d["label"] for d in diag]
        out["confidence"] = [d["confidence"] for d in diag]
        if self.ttb is not None:
            ttb = self.ttb.run(None, {"window": x})[0]
            out["ttb_model"] = np.clip(np.ravel(ttb), 0.0, TTB_MAX).round(1)

    def probabilities(self, row: pd.Series) -> dict[str, float] | None:
        """Peluang per kelas, HANYA bila label = kelas teratas model. Label dari aturan atau dari
        penyaringan sensor akan bertentangan dengan peringkat model, jadi dikirim null."""
        p = {lab: float(round(row[f"p_{lab}"], 4)) for lab in self.api_labels}
        return p if row.label == max(p, key=p.get) else None


class HybridInferenceEngine:
    def __init__(self, provider: str | None = None) -> None:
        cfg = settings.get("model", {})
        self.provider_name = provider or cfg.get("diagnosis_provider", DEFAULT_PROVIDER)
        if self.provider_name not in PROVIDERS:
            raise ValueError(f"model.diagnosis_provider must be one of {PROVIDERS}, got {self.provider_name!r}")
        pcfg = cfg.get("providers", {}).get(self.provider_name, {})
        self.version = pcfg.get("version", f"coldtrack-hybrid-{self.provider_name}")
        self.provider = (V3Provider if self.provider_name == "v3" else Checkpoint2Provider)(pcfg)

    @property
    def is_ready(self) -> bool:
        return self.provider.is_ready

    def analyze_trip(self, trip: pd.DataFrame, prod: dict[str, float], feats: pd.DataFrame | None = None,
                     last_only: bool = False, engine_out: pd.DataFrame | None = None) -> pd.DataFrame:
        """Every minute of a trip, causally (row t only uses data up to t). Rows start at minute W-1.

        `feats` = preprocess.features_per_minute(readings), aligned with `trip` (both sorted by ts);
        required by the v3 provider. predict() serves the last row; the eval suite scores all rows.
        last_only=True: the physics engine still runs over the whole history (the cargo observer needs
        it), but the GRU/XGB only run for the last window (worker-infer, /analyze). Causal, so the last
        row is identical to last_only=False (tests/test_fleet_infer.py).
        """
        if engine_out is None:
            engine_out = engine.run(trip, prod, prod["mass_kg"])
        eng = engine_out.iloc[WINDOW - 1:].reset_index(drop=True)
        if last_only:
            eng = eng.iloc[-1:].reset_index(drop=True)
        out = pd.DataFrame({
            "minute": eng.minute,
            "status": eng.status_txt,
            "reason": eng.reason,
            "ttb_show": eng.ttb_show.round(1),
            "ttb_phys": eng.ttb_phys,
            "sensor_status": eng.sensor_status.astype(int),
            "t_cargo_est": eng.T_cargo_est.round(2),
        })
        out["risk_index"] = [
            _risk_index(st, float(tp), ss >= 1) for st, tp, ss in zip(out.status, out.ttb_phys, out.sensor_status)
        ]
        if self.provider.is_ready:
            self.provider.run(trip, out, feats)
        return out

    def predict(
        self, readings: list[TelemetryReading], cargo_profile: str, mass_kg: float | None = None
    ) -> dict[str, Any]:
        """Needs >= 60 readings (validated in main.py). Uses the full history for the cargo observer."""
        return self.predict_last(readings, cargo_profile, mass_kg)[0]

    def predict_last(
        self, readings: list[TelemetryReading], cargo_profile: str, mass_kg: float | None = None
    ) -> tuple[dict[str, Any], pd.DataFrame]:
        """predict() plus the per-minute engine series (ts, sensor_status, T_cargo_est, status) over the
        whole history, used by worker-infer for sensor health and breach detection. Models run once."""
        prod = cargo_params(cargo_profile, mass_kg)
        trip = readings_to_trip(readings, prod)
        eng = engine.run(trip, prod, prod["mass_kg"])
        now = self.analyze_trip(trip, prod, features_per_minute(readings), last_only=True, engine_out=eng).iloc[-1]
        series = pd.DataFrame({"ts": trip.ts, "sensor_status": eng.sensor_status.astype(int),
                               "t_cargo_est": eng.T_cargo_est, "status": eng.status_txt})
        result: dict[str, Any] = {
            "status": now.status,
            "reason": now.reason,
            "time_to_breach_min": None if pd.isna(now.ttb_show) else float(now.ttb_show),
            "risk_index": float(now.risk_index),
            "sensor_status": int(now.sensor_status),
            "forecast": None,
            "failure_mode": None,
            "ttb_model_min": float(now.ttb_model) if "ttb_model" in now else None,
            "t_cargo_est": float(now.t_cargo_est),
            "t_hi": prod["t_hi"],
            **kelengkapan_data(readings),
        }
        if "label" in now:
            conf = float(now.confidence)
            if not result["data_lengkap"]:
                conf = min(conf, KEYAKINAN_MAKS_DATA_TIDAK_LENGKAP)
            result["forecast"] = {h: float(now[h]) for h in ("t15", "t30", "t60")}
            result["failure_mode"] = {"label": now.label, "confidence": conf,
                                      "probabilities": self.provider.probabilities(now)}
        return result, series


inference_engine = HybridInferenceEngine()
