"""Unit tests for the hybrid inference engine."""

import pytest
from app.inference import HybridInferenceEngine, inference_engine
from app.main import AnalyzeRequest
from tests.test_analyze import make_readings


def test_inference_engine_initialization():
    assert isinstance(inference_engine, HybridInferenceEngine)


def test_inference_engine_prediction_if_ready():
    if not inference_engine.is_ready:
        pytest.skip("GRU ONNX model not found; skipping forward pass test")
    req = AnalyzeRequest(shipment_id="T", cargo_profile="vaksin_2_8C", readings=make_readings(90))
    out = inference_engine.predict(req.readings, req.cargo_profile)

    assert out["status"] in ["AMAN", "WASPADA", "KRITIS"]
    assert set(out["forecast"]) == {"t15", "t30", "t60"}
    assert 0.0 <= out["failure_mode"]["confidence"] <= 1.0
    assert 0.0 <= out["risk_index"] <= 1.0
    assert out["ttb_model_min"] is None or 0.0 <= out["ttb_model_min"] <= 240.0


def test_mass_changes_physics_ttb():
    """Door open on a warm day: a lighter load warms faster, so TTB must be shorter."""
    readings = make_readings(90, base_temp=6.0, ambient=33.0, door_open=True, speed=0.0)
    req = AnalyzeRequest(shipment_id="T", cargo_profile="vaksin_2_8C", readings=readings)
    light = inference_engine.predict(req.readings, req.cargo_profile, mass_kg=200)
    heavy = inference_engine.predict(req.readings, req.cargo_profile, mass_kg=4000)
    assert light["time_to_breach_min"] is not None
    assert heavy["time_to_breach_min"] is None or heavy["time_to_breach_min"] > light["time_to_breach_min"]
