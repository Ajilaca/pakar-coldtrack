"""Unit tests for rule engine and risk scorer."""

import pandas as pd

from app.rules import (
    compute_feature_drivers,
    compute_risk_index,
    evaluate_cargo_limits,
    generate_recommended_actions,
)


def test_evaluate_cargo_limits():
    limits = evaluate_cargo_limits("vaksin_2_8C")
    assert limits["min_temp_c"] == 2.0
    assert limits["max_temp_c"] == 8.0
    assert limits["critical_temp_c"] == 10.0


def test_compute_risk_index_normal():
    df_feat = pd.DataFrame(
        {
            "temp_c": [4.0, 4.1, 4.2],
            "delta_temp": [0.0, 0.1, 0.1],
            "reefer_on": [1, 1, 1],
            "door_open": [0, 0, 0],
            "ambient_c": [30.0, 30.0, 30.0],
            "reefer_duration_min": [10.0, 11.0, 12.0],
        }
    )
    forecast = {"t15": 4.5, "t30": 4.8, "t60": 5.0}

    risk_idx, status = compute_risk_index(
        current_temp=4.2,
        forecast=forecast,
        cargo_profile="vaksin_2_8C",
        df_features=df_feat,
    )
    assert status == "AMAN"
    assert risk_idx < 0.35


def test_compute_risk_index_critical():
    df_feat = pd.DataFrame(
        {
            "temp_c": [8.0, 9.5, 11.0],
            "delta_temp": [0.5, 1.5, 1.5],
            "reefer_on": [1, 1, 0],
            "door_open": [0, 1, 1],
            "ambient_c": [32.0, 33.0, 34.0],
            "reefer_duration_min": [0.0, 0.0, 0.0],
        }
    )
    forecast = {"t15": 12.5, "t30": 14.0, "t60": 16.0}

    risk_idx, status = compute_risk_index(
        current_temp=11.0,
        forecast=forecast,
        cargo_profile="vaksin_2_8C",
        df_features=df_feat,
    )
    assert status == "KRITIS"
    assert risk_idx >= 0.70


def test_generate_recommended_actions():
    actions = generate_recommended_actions(
        status="KRITIS",
        failure_label="degradasi_kompresor",
        cargo_profile="vaksin_2_8C",
    )
    assert len(actions) == 3
    assert actions[0].priority == 1
    assert actions[0].text is not None


def test_compute_feature_drivers():
    df_feat = pd.DataFrame(
        {
            "delta_temp": [0.13],
            "ambient_c": [31.4],
            "reefer_duration_min": [196.0],
        }
    )
    drivers = compute_feature_drivers(df_feat)
    assert len(drivers) == 3
    assert drivers[0].feature == "laju_kenaikan_suhu"
