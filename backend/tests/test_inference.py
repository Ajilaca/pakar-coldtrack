"""Unit tests for ONNX Runtime inference engine."""

import numpy as np
import pytest

from app.inference import ONNXInferenceEngine, inference_engine


def test_inference_engine_initialization():
    assert isinstance(inference_engine, ONNXInferenceEngine)


def test_inference_engine_prediction_if_ready():
    if inference_engine.is_ready:
        dummy_tensor = np.zeros((1, 60, 12), dtype=np.float32)
        forecast_c, failure_mode, _ttb = inference_engine.predict(dummy_tensor)

        assert "t15" in forecast_c
        assert "t30" in forecast_c
        assert "t60" in forecast_c
        assert "label" in failure_mode
        assert "confidence" in failure_mode
        assert 0.0 <= failure_mode["confidence"] <= 1.0
    else:
        pytest.skip("ONNX model file not found; skipping ONNX forward pass test")
