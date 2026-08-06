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
    """Wrapper around ONNXRuntime for executing coldtrack.onnx model."""

    def __init__(
        self,
        onnx_path: str | None = None,
        labels_path: str | None = None,
    ):
        model_cfg = settings.get("model", {})
        base_dir = Path(__file__).resolve().parent.parent

        resolved_onnx_path = Path(
            onnx_path or model_cfg.get("onnx_path", "../ml/reports/coldtrack.onnx")
        )
        if not resolved_onnx_path.is_absolute():
            resolved_onnx_path = (base_dir / resolved_onnx_path).resolve()

        resolved_labels_path = Path(
            labels_path or model_cfg.get("labels_path", "../ml/reports/labels.json")
        )
        if not resolved_labels_path.is_absolute():
            resolved_labels_path = (base_dir / resolved_labels_path).resolve()

        self.onnx_path = resolved_onnx_path
        self.labels_path = resolved_labels_path
        self.session: ort.InferenceSession | None = None
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
        """Initialize ONNXRuntime session and load label metadata."""
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
                # Use CPU Execution Provider
                self.session = ort.InferenceSession(
                    str(self.onnx_path),
                    providers=["CPUExecutionProvider"],
                )
                logger.info(f"Loaded ONNX model successfully from {self.onnx_path}")
            except Exception as e:  # noqa: BLE001
                logger.error(f"Failed to initialize ONNX InferenceSession: {e}")
                self.session = None
        else:
            logger.warning(f"ONNX model file not found at {self.onnx_path}")

    @property
    def is_ready(self) -> bool:
        """Check if ONNX session is active."""
        return self.session is not None

    def predict(
        self, tensor_3d: np.ndarray
    ) -> tuple[dict[str, float], dict[str, Any], float | None]:
        """Execute forward pass on [1, 60, 12] float32 tensor.

        Returns:
            forecast_c: {"t15": float, "t30": float, "t60": float}
            failure_mode: {"label": str, "confidence": float}
            time_to_breach_min: float or None
        """
        if not self.is_ready or self.session is None:
            raise RuntimeError("ONNX Inference Engine is not initialized")

        input_name = self.session.get_inputs()[0].name
        outputs = self.session.run(None, {input_name: tensor_3d})

        # Output mapping based on labels.json / model export
        # Expected outputs: forecast_c, failure_prob, time_to_breach_min
        raw_forecast = outputs[0][0]  # shape [3]
        raw_probs = outputs[1][0]  # shape [7]
        raw_ttb = float(outputs[2][0]) if len(outputs) > 2 else 999.0

        forecast_c = {
            "t15": float(np.round(raw_forecast[0], 2)),
            "t30": float(np.round(raw_forecast[1], 2)),
            "t60": float(np.round(raw_forecast[2], 2)),
        }

        # Failure mode argmax
        max_idx = int(np.argmax(raw_probs))
        top_label = self.classes[max_idx] if max_idx < len(self.classes) else "A0"
        top_conf = float(np.round(raw_probs[max_idx], 3))

        # Map internal class codes to readable failure mode labels if needed
        readable_label_map = {
            "A0": "normal_sehat",
            "A1": "pintu_terbuka_lama",
            "A3": "kegagalan_reefer_total",
            "A7": "fluktuasi_ambien_ekstrem",
            "A8": "defrost_abnormal",
            "degradasi_bertahap": "degradasi_kompresor",
            "masalah_sensor": "masalah_sensor",
        }
        mapped_label = readable_label_map.get(top_label, top_label)

        failure_mode = {
            "label": mapped_label,
            "confidence": top_conf,
        }

        # Time to breach adjustment (sentinel 999 or negative means no imminent breach)
        time_to_breach = float(np.round(raw_ttb, 1)) if raw_ttb < 500 else None

        return forecast_c, failure_mode, time_to_breach


# Global inference engine singleton instance
inference_engine = ONNXInferenceEngine()
