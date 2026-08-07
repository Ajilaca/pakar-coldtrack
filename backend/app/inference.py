"""ONNX Runtime Inference Engine module for ColdTrack AI Backend."""

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort

from app.config import settings

logger = logging.getLogger("coldtrack.inference")


class ONNXInferenceEngine:
    """Wrapper around ONNXRuntime for executing coldtrack.onnx model.

    Runs two ONNX sessions:
    - ``coldtrack.onnx``: 3-head GRU (forecast + failure_prob; Head-3 TTB ignored)
    - ``coldtrack_ttb.onnx``: dedicated TTB model used for time_to_breach output
    """

    def __init__(
        self,
        onnx_path: str | None = None,
        labels_path: str | None = None,
        ttb_onnx_path: str | None = None,
    ):
        base_dir = Path(__file__).resolve().parent.parent
        model_cfg = settings.get("model", {})

        def _resolve_path(config_val: str, fallback_relative: str) -> Path:
            p = Path(config_val)
            if p.is_absolute() and p.exists():
                return p
            # Try relative to backend/ (base_dir)
            p1 = (base_dir / p).resolve()
            if p1.exists():
                return p1
            # Try fallback relative to base_dir
            p2 = (base_dir / fallback_relative).resolve()
            if p2.exists():
                return p2
            return p1

        onnx_cfg = onnx_path or model_cfg.get("onnx_path", "models/coldtrack.onnx")
        labels_cfg = labels_path or model_cfg.get("labels_path", "models/labels.json")
        ttb_cfg = ttb_onnx_path or model_cfg.get(
            "ttb_onnx_path", "models/coldtrack_ttb.onnx"
        )

        self.onnx_path = _resolve_path(onnx_cfg, "../ml/reports/coldtrack.onnx")
        self.labels_path = _resolve_path(labels_cfg, "../ml/reports/labels.json")
        self.ttb_onnx_path = _resolve_path(
            ttb_cfg, "../ml/reports/coldtrack_ttb.onnx"
        )
        self.session: ort.InferenceSession | None = None
        self.ttb_session: ort.InferenceSession | None = None
        self.labels_meta: dict[str, Any] = {}
        self.classes = [
            "A0",
            "A1",
            "A3",
            "A7",
            "A8",
            "degradasi_bertahap",
            "masalah_sensor",
        ]
        self._load_model()

    def _load_model(self) -> None:
        """Initialize ONNXRuntime sessions and load label metadata."""
        if self.labels_path.exists():
            try:
                with open(self.labels_path, "r", encoding="utf-8") as f:
                    self.labels_meta = json.load(f)
                self.classes = (
                    self.labels_meta.get("outputs", {})
                    .get("failure_prob", {})
                    .get("classes", self.classes)
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to read labels.json: {e}")

        if self.onnx_path.exists():
            try:
                self.session = ort.InferenceSession(
                    str(self.onnx_path),
                    providers=["CPUExecutionProvider"],
                )
                logger.info(f"Loaded ONNX model from {self.onnx_path}")
            except Exception as e:  # noqa: BLE001
                logger.error(f"Failed to initialize ONNX InferenceSession: {e}")
                self.session = None
        else:
            logger.warning(f"ONNX model file not found at {self.onnx_path}")

        if self.ttb_onnx_path.exists():
            try:
                self.ttb_session = ort.InferenceSession(
                    str(self.ttb_onnx_path),
                    providers=["CPUExecutionProvider"],
                )
                logger.info(f"Loaded TTB ONNX model from {self.ttb_onnx_path}")
            except Exception as e:  # noqa: BLE001
                logger.error(f"Failed to initialize TTB ONNX InferenceSession: {e}")
                self.ttb_session = None
        else:
            logger.warning(f"TTB ONNX model file not found at {self.ttb_onnx_path}")

    @property
    def is_ready(self) -> bool:
        """Check if main ONNX session is active."""
        return self.session is not None

    def _predict_ttb(self, tensor_3d: np.ndarray) -> float:
        """Run dedicated TTB ONNX model on the same input tensor.

        Returns raw minutes. Falls back to 999.0 if TTB session is unavailable,
        which the caller treats as undefined.
        """
        if self.ttb_session is None:
            return 999.0
        input_name = self.ttb_session.get_inputs()[0].name
        out = self.ttb_session.run(None, {input_name: tensor_3d})
        return float(out[0][0])

    def predict(
        self, tensor_3d: np.ndarray
    ) -> tuple[dict[str, float], dict[str, Any], float | None]:
        """Execute forward pass on [1, 60, 12] float32 tensor.

        Returns:
            forecast_c: {"t15": float, "t30": float, "t60": float}
            failure_mode: {"label": str, "confidence": float}
            time_to_breach_min: float or None

        TTB logic:
        - Only meaningful when failure_prob points to a non-A0 class.
          The TTB head is trained with healthy windows masked from loss,
          so its output is undefined for healthy trucks — not a sentinel 999.
        - When non-A0: uses dedicated coldtrack_ttb.onnx (MAE 3.5 min at <=10 min).
        - Capped at ttb_display_cap_min (default 30 min); values above cap
          return None as model precision degrades rapidly beyond that horizon.
        """
        if not self.is_ready or self.session is None:
            raise RuntimeError("ONNX Inference Engine is not initialized")

        input_name = self.session.get_inputs()[0].name
        outputs = self.session.run(None, {input_name: tensor_3d})

        # Output mapping: forecast_c [3], failure_prob [7]
        # GRU Head-3 (TTB) is intentionally ignored — replaced by coldtrack_ttb.onnx
        raw_forecast = outputs[0][0]  # shape [3]
        raw_probs = outputs[1][0]  # shape [7]

        forecast_c = {
            "t15": float(np.round(raw_forecast[0], 2)),
            "t30": float(np.round(raw_forecast[1], 2)),
            "t60": float(np.round(raw_forecast[2], 2)),
        }

        # Failure mode argmax
        max_idx = int(np.argmax(raw_probs))
        top_label = self.classes[max_idx] if max_idx < len(self.classes) else "A0"
        top_conf = float(np.round(raw_probs[max_idx], 3))

        # Bug 2 fix: corrected label names per R1 anomaly catalogue
        # A8 = prapendinginan_buruk (pre-cooling failure), not defrost
        # degradasi_bertahap = merged A2+A4 class (compressor + refrigerant leak)
        readable_label_map = {
            "A0": "normal_sehat",
            "A1": "pintu_terbuka_lama",
            "A3": "kegagalan_reefer_total",
            "A7": "fluktuasi_ambien_ekstrem",
            "A8": "prapendinginan_buruk",
            "degradasi_bertahap": "degradasi_pendinginan",
            "masalah_sensor": "masalah_sensor",
        }
        mapped_label = readable_label_map.get(top_label, top_label)

        failure_mode = {
            "label": mapped_label,
            "confidence": top_conf,
        }

        # Bug 1 fix: gate TTB on failure_prob (not raw TTB value).
        # The TTB head was trained with healthy windows masked from loss;
        # output for healthy trucks is undefined — it never produces sentinel 999.
        is_healthy = top_label == "A0"
        if is_healthy:
            time_to_breach = None
        else:
            raw_ttb = self._predict_ttb(tensor_3d)
            cap = settings.get("model", {}).get("ttb_display_cap_min", 30)
            # Suppress TTB beyond display cap: MAE degrades from 6 min (0-10 min)
            # to 44.5 min (30-90 min) — returning None avoids false precision.
            time_to_breach = float(np.round(raw_ttb, 1)) if raw_ttb < cap else None

        return forecast_c, failure_mode, time_to_breach


# Global inference engine singleton instance
inference_engine = ONNXInferenceEngine()
