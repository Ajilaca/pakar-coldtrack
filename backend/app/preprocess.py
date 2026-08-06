"""Telemetry data preprocessing and derived feature engineering module.

Calculates derived features and constructs 3D window arrays matching the exact
ONNX input contract specified in labels.json and docs/feature_schema.md.
"""


import numpy as np
import pandas as pd

from app.schemas import TelemetryReading

# Feature list in EXACT order required by ONNX model (labels.json)
ONNX_FEATURE_COLUMNS: list[str] = [
    "temp_c",
    "delta_temp",
    "ambient_c",
    "delta_ambient",
    "solar_radiation",
    "humidity",
    "door_open",
    "reefer_on",
    "reefer_duration_min",
    "speed_kmh",
    "harsh_events",
    "hour_of_day",
]

FORBIDDEN_COLUMNS: list[str] = [
    "is_anomaly",
    "failure_mode",
    "time_to_breach",
    "time_to_breach_min",
]


def readings_to_dataframe(readings: list[TelemetryReading]) -> pd.DataFrame:
    """Convert list of TelemetryReading Pydantic objects to pandas DataFrame."""
    data = []
    for r in readings:
        data.append(
            {
                "ts": r.ts,
                "temp_c": float(r.temp_c),
                "humidity": float(r.humidity),
                "ambient_c": float(r.ambient_c),
                "door_open": 1 if r.door_open else 0,
                "reefer_on": 1 if r.reefer_on else 0,
                "lat": float(r.lat),
                "lon": float(r.lon),
                "speed_kmh": float(r.speed_kmh),
                "harsh_events": int(r.harsh_events),
                "solar_radiation": float(r.solar_radiation or 0.0),
            }
        )
    df = pd.DataFrame(data)
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").reset_index(drop=True)
    return df


def compute_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute derived features per docs/feature_schema.md.

    - delta_temp[t] = temp_c[t] - temp_c[t-1]
    - delta_ambient[t] = temp_c[t] - ambient_c[t]
    - reefer_duration_min = continuous minutes with reefer_on == 1
    - hour_of_day = ts.dt.hour (0-23)
    """
    df = df.copy()

    # 1. delta_temp
    df["delta_temp"] = df["temp_c"].diff().fillna(0.0)

    # 2. delta_ambient
    df["delta_ambient"] = df["temp_c"] - df["ambient_c"]

    # 3. hour_of_day
    df["hour_of_day"] = df["ts"].dt.hour

    # 4. reefer_duration_min
    reefer_durations = []
    current_duration = 0.0
    for reefer_state in df["reefer_on"]:
        if reefer_state == 1:
            current_duration += 1.0
        else:
            current_duration = 0.0
        reefer_durations.append(current_duration)
    df["reefer_duration_min"] = reefer_durations

    return df


def prepare_onnx_input_tensor(
    readings: list[TelemetryReading], sequence_length: int = 60
) -> tuple[np.ndarray, pd.DataFrame]:
    """Prepare raw readings into [1, 60, 12] float32 tensor for ONNX inference.

    If readings count < sequence_length, backfills/pads the front by repeating
    the earliest reading to ensure length == sequence_length.
    """
    df = readings_to_dataframe(readings)

    # Validate forbidden columns guard
    for col in df.columns:
        if col in FORBIDDEN_COLUMNS:
            raise ValueError(f"Forbidden column detected in feature matrix: {col}")

    # Interpolate numeric gaps if any missing values
    numeric_cols = [
        "temp_c",
        "humidity",
        "ambient_c",
        "speed_kmh",
        "solar_radiation",
    ]
    df[numeric_cols] = df[numeric_cols].interpolate(method="linear").bfill().ffill()

    # Compute derived features
    df_features = compute_derived_features(df)

    # Padding if less than sequence_length
    if len(df_features) < sequence_length:
        first_row = df_features.iloc[[0]]
        pad_count = sequence_length - len(df_features)
        pad_df = pd.concat([first_row] * pad_count, ignore_index=True)
        df_features = pd.concat([pad_df, df_features], ignore_index=True)
    elif len(df_features) > sequence_length:
        df_features = df_features.iloc[-sequence_length:].reset_index(drop=True)

    # Extract required feature columns in exact ONNX order
    feature_matrix = df_features[ONNX_FEATURE_COLUMNS].to_numpy(dtype=np.float32)

    # Reshape to [1, sequence_length, 12]
    tensor_3d = np.expand_dims(feature_matrix, axis=0)
    return tensor_3d, df_features
