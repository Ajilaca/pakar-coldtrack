"""Unit tests for cargo limits, actions and driver explanations."""

import pandas as pd
from app.explain import compute_feature_drivers
from app.rules import evaluate_cargo_limits, generate_recommended_actions


def test_evaluate_cargo_limits():
    limits = evaluate_cargo_limits("vaksin_2_8C")
    assert limits["min_temp_c"] == 2.0
    assert limits["max_temp_c"] == 8.0
    assert limits["critical_temp_c"] == 10.0


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
