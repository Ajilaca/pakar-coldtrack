"""Unit tests for preprocessing and feature engineering module."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.preprocess import (
    ONNX_FEATURE_COLUMNS,
    compute_derived_features,
    prepare_onnx_input_tensor,
    readings_to_dataframe,
)
from app.schemas import TelemetryReading


@pytest.fixture
def sample_readings():
    base_time = datetime(2026, 8, 20, 8, 0, 0, tzinfo=timezone.utc)
    readings = []
    for i in range(10):
        readings.append(
            TelemetryReading(
                ts=base_time + timedelta(minutes=i),
                temp_c=4.0 + (i * 0.2),
                humidity=70.0,
                ambient_c=30.0 + (i * 0.1),
                door_open=(i >= 8),
                reefer_on=True,
                lat=-6.2,
                lon=106.8,
                speed_kmh=40.0,
                harsh_events=0,
                solar_radiation=500.0,
            )
        )
    return readings


def test_readings_to_dataframe(sample_readings):
    df = readings_to_dataframe(sample_readings)
    assert len(df) == 10
    assert "temp_c" in df.columns
    assert df["temp_c"].iloc[0] == 4.0
    assert df["temp_c"].iloc[-1] == pytest.approx(5.8)


def test_compute_derived_features(sample_readings):
    df = readings_to_dataframe(sample_readings)
    df_feat = compute_derived_features(df)

    assert "delta_temp" in df_feat.columns
    assert "delta_ambient" in df_feat.columns
    assert "hour_of_day" in df_feat.columns
    assert "reefer_duration_min" in df_feat.columns

    assert df_feat["delta_temp"].iloc[1] == pytest.approx(0.2)
    assert df_feat["hour_of_day"].iloc[0] == 8
    assert df_feat["reefer_duration_min"].iloc[-1] == 10.0


def test_prepare_onnx_input_tensor(sample_readings):
    tensor, df_features = prepare_onnx_input_tensor(sample_readings, sequence_length=60)
    assert isinstance(tensor, np.ndarray)
    assert tensor.shape == (1, 60, 12)
    assert tensor.dtype == np.float32

    # Check exact feature ordering match
    assert len(ONNX_FEATURE_COLUMNS) == 12
    assert list(df_features[ONNX_FEATURE_COLUMNS].columns) == ONNX_FEATURE_COLUMNS
