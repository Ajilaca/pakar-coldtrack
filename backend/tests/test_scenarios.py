"""Integration tests for scenario endpoints."""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_list_scenarios():
    response = client.get("/api/v1/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5

    scenario_ids = [s["id"] for s in data]
    assert "scenario_1_normal" in scenario_ids
    assert "scenario_2_door_open" in scenario_ids
    assert "scenario_3_compressor_degradation" in scenario_ids
    assert "scenario_4_sensor_stuck" in scenario_ids
    assert "scenario_5_extreme_ambient" in scenario_ids


def test_get_single_scenario():
    response = client.get("/api/v1/scenarios/scenario_1_normal")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "scenario_1_normal"
    assert "readings" in data
    assert len(data["readings"]) > 0


def test_every_scenario_returns_expected_status():
    for meta in client.get("/api/v1/scenarios").json():
        s = client.get(f"/api/v1/scenarios/{meta['id']}").json()
        payload = {"shipment_id": s["id"], "cargo_profile": s["cargo_profile"], "readings": s["readings"]}
        res = client.post("/api/v1/analyze", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == s["expected_status"], s["id"]
        # diagnosis must agree with status: never "normal" on an alert, never "sensor" on a healthy sensor
        assert (body["failure_mode"]["label"] == "normal_sehat") == (body["status"] == "AMAN"), s["id"]
        assert ("sensor" in body["failure_mode"]["label"]) == ("sensor" in s["id"]), s["id"]


def test_get_nonexistent_scenario():
    response = client.get("/api/v1/scenarios/scenario_non_existent")
    assert response.status_code == 404
