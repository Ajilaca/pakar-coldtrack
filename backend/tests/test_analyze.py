"""Integration tests for POST /api/v1/analyze core endpoint."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_analyze_endpoint_success():
    payload = {
        "shipment_id": "TRK-JKT-0417",
        "cargo_profile": "vaksin_2_8C",
        "readings": [
            {
                "ts": "2026-08-20T07:00:00+07:00",
                "temp_c": 4.2,
                "humidity": 71.5,
                "ambient_c": 31.4,
                "door_open": False,
                "reefer_on": True,
                "lat": -6.2118,
                "lon": 106.8456,
                "speed_kmh": 24.0,
                "harsh_events": 0,
            }
        ],
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
    scenario_ids = [
        "scenario_1_normal",
        "scenario_2_door_open",
        "scenario_3_compressor_degradation",
        "scenario_4_reefer_failure",
        "scenario_5_extreme_ambient",
    ]
    for s_id in scenario_ids:
        scen_resp = client.get(f"/api/v1/scenarios/{s_id}")
        assert scen_resp.status_code == 200
        scen_data = scen_resp.json()

        payload = {
            "shipment_id": scen_data.get("shipment_id", s_id),
            "cargo_profile": scen_data.get("cargo_profile", "vaksin_2_8C"),
            "readings": scen_data["readings"],
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


def test_broken_payload_single_reading_extreme_values():
    """Spec requirement: handle 'CSV/payload rusak' — single reading with edge-case extreme values."""
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
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["AMAN", "WASPADA", "KRITIS"]
    assert data["inference_ms"] > 0


def test_latency_under_1000ms():
    """Spec requirement: explicit target latency check < 1000ms."""
    payload = {
        "shipment_id": "TRK-PERF-001",
        "cargo_profile": "vaksin_2_8C",
        "readings": [
            {
                "ts": "2026-08-20T07:00:00+07:00",
                "temp_c": 5.0,
                "humidity": 70.0,
                "ambient_c": 30.0,
                "door_open": False,
                "reefer_on": True,
                "lat": -6.2,
                "lon": 106.8,
                "speed_kmh": 30.0,
                "harsh_events": 0,
            }
        ],
    }
    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["inference_ms"] < 1000
