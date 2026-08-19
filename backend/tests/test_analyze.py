"""Integration tests for POST /api/v1/analyze core endpoint."""

from datetime import datetime, timedelta, timezone

import pytest
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

TZ = timezone(timedelta(hours=7))


def make_readings(
    count: int = 60,
    base_temp: float = 4.2,
    ambient: float = 31.4,
    door_open: bool = False,
    reefer_on: bool = True,
    speed: float = 24.0,
    base_ts: datetime | None = None,
) -> list[dict]:
    """Generate synthetic telemetry readings for testing."""
    start = base_ts or datetime(2026, 8, 20, 7, 0, 0, tzinfo=TZ)
    return [
        {
            "ts": (start + timedelta(minutes=i)).isoformat(),
            "temp_c": round(base_temp + i * 0.02, 2),
            "humidity": 70.0,
            "ambient_c": ambient,
            "door_open": door_open,
            "reefer_on": reefer_on,
            "lat": -6.2118,
            "lon": 106.8456,
            "speed_kmh": speed,
            "harsh_events": 0,
            "solar_radiation": 200.0,
        }
        for i in range(count)
    ]


def test_analyze_endpoint_success():
    payload = {
        "shipment_id": "TRK-JKT-0417",
        "cargo_profile": "vaksin_2_8C",
        "readings": make_readings(60),
    }

    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code == 200
    res_data = response.json()

    assert "status" in res_data
    assert res_data["status"] in ["AMAN", "WASPADA", "KRITIS"]
    assert "risk_index" in res_data
    assert 0.0 <= res_data["risk_index"] <= 1.0
    assert "failure_mode" in res_data
    assert "label" in res_data["failure_mode"]
    assert "confidence" in res_data["failure_mode"]
    assert "forecast" in res_data
    assert "t15" in res_data["forecast"]
    assert "t30" in res_data["forecast"]
    assert "t60" in res_data["forecast"]
    assert "drivers" in res_data
    assert len(res_data["drivers"]) == 3
    assert "actions" in res_data
    assert len(res_data["actions"]) == 3
    assert "model_version" in res_data
    assert res_data["model_version"] == "coldtrack-gru-v2-fusion-v4"
    assert "inference_ms" in res_data
    assert res_data["inference_ms"] < 1000  # Latency target < 1000ms


def test_analyze_all_scenarios():
    """Smoke-test all demo scenarios via the analyze endpoint.

    Note: scenario JSON files have fewer than 60 readings (they are display
    datasets, not inference inputs). The scenario endpoint is tested via GET;
    the analyze endpoint requires 60-reading payloads (enforced by validation).
    """
    scenario_ids = [
        "scenario_1_normal",
        "scenario_2_door_open",
        "scenario_3_compressor_degradation",
        "scenario_4_sensor_stuck",
        "scenario_5_extreme_ambient",
    ]
    for s_id in scenario_ids:
        scen_resp = client.get(f"/api/v1/scenarios/{s_id}")
        assert scen_resp.status_code == 200
        scen_data = scen_resp.json()

        # Pad to 60 readings for inference
        raw_readings = scen_data["readings"]
        while len(raw_readings) < 60:
            raw_readings = [raw_readings[0]] + raw_readings

        payload = {
            "shipment_id": scen_data.get("shipment_id", s_id),
            "cargo_profile": scen_data.get("cargo_profile", "vaksin_2_8C"),
            "readings": raw_readings,
        }
        res = client.post("/api/v1/analyze", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ["AMAN", "WASPADA", "KRITIS"]


def test_analyze_invalid_payload_returns_422():
    invalid_payload = {
        "shipment_id": "TRK-ERR-000",
        "cargo_profile": "vaksin_2_8C",
        "readings": "invalid_not_a_list",
    }
    response = client.post("/api/v1/analyze", json=invalid_payload)
    assert response.status_code == 422


def test_analyze_rejects_under_60_readings():
    """Spec: reject payloads with fewer than 60 readings with HTTP 400.

    GRU fusion model computes internal summary stats over the window;
    padded windows silently produce incorrect std/trend values.
    """
    payload = {
        "shipment_id": "TRK-SHORT-001",
        "cargo_profile": "vaksin_2_8C",
        "readings": make_readings(5),
    }
    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code == 400
    assert "60" in response.json()["detail"]


def test_broken_payload_single_reading_returns_400():
    """Spec: single reading with extreme values must be rejected (not silently padded)."""
    payload = {
        "shipment_id": "TRK-EDGE-001",
        "cargo_profile": "vaksin_2_8C",
        "readings": [
            {
                "ts": "2026-08-20T07:00:00+07:00",
                "temp_c": -99.0,
                "humidity": 0.0,
                "ambient_c": 0.0,
                "door_open": True,
                "reefer_on": False,
                "lat": 0.0,
                "lon": 0.0,
                "speed_kmh": 0.0,
                "harsh_events": 999,
            }
        ],
    }
    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code == 400


def test_latency_under_1000ms():
    """Spec requirement: dual-model inference (coldtrack.onnx + coldtrack_ttb.onnx)
    must complete well under 1000ms (combined latency ~1.2ms).
    """
    payload = {
        "shipment_id": "TRK-PERF-001",
        "cargo_profile": "vaksin_2_8C",
        "readings": make_readings(60, base_temp=5.0, ambient=30.0, speed=30.0),
    }
    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["inference_ms"] < 1000


def test_ttb_null_for_healthy_truck():
    """Bug 1 fix: healthy trucks (A0 class) must always return time_to_breach_min=null.

    The TTB model is trained on failure windows only; its output for healthy
    trucks is undefined — not a sentinel 999. Gate must use failure_prob, not raw TTB.
    """
    # Stable temp, reefer on, door closed — strong signal for healthy prediction
    payload = {
        "shipment_id": "TRK-HEALTHY-001",
        "cargo_profile": "vaksin_2_8C",
        "readings": make_readings(60, base_temp=4.5, ambient=31.0, door_open=False, reefer_on=True),
    }
    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    if data["failure_mode"]["label"] == "normal_sehat":
        assert data["time_to_breach_min"] is None, (
            "Healthy truck should never expose a TTB value (Bug 1 regression)"
        )


@pytest.mark.parametrize("cargo_profile", ["ikan_segar_0_5C", "produk_susu_2_4C"])
def test_new_cargo_profiles_accepted(cargo_profile: str):
    """Bug 3 fix: two new cargo profiles must be accepted without 422."""
    payload = {
        "shipment_id": f"TRK-{cargo_profile.upper()}",
        "cargo_profile": cargo_profile,
        "readings": make_readings(60),
    }
    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] in ["AMAN", "WASPADA", "KRITIS"]
