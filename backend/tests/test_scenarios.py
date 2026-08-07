"""Integration tests for scenario endpoints."""

from fastapi.testclient import TestClient

from app.main import app

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
    assert "scenario_4_reefer_failure" in scenario_ids
    assert "scenario_5_extreme_ambient" in scenario_ids


def test_get_single_scenario():
    response = client.get("/api/v1/scenarios/scenario_1_normal")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "scenario_1_normal"
    assert "readings" in data
    assert len(data["readings"]) > 0


def test_get_nonexistent_scenario():
    response = client.get("/api/v1/scenarios/scenario_non_existent")
    assert response.status_code == 404
