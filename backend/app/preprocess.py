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
                "lat": float(r.lat or 0.0),
                "lon": float(r.lon or 0.0),
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

    # Padding raw readings if less than sequence_length
    if len(df) < sequence_length:
        pad_count = sequence_length - len(df)
        first_row = df.iloc[[0]].copy()
        pad_df = pd.concat([first_row] * pad_count, ignore_index=True)
        # Shift timestamps backwards by 1 minute for each padded step
        start_ts = first_row["ts"].iloc[0]
        pad_df["ts"] = [start_ts - pd.Timedelta(minutes=pad_count - i) for i in range(pad_count)]
        df = pd.concat([pad_df, df], ignore_index=True)
    elif len(df) > sequence_length:
        df = df.iloc[-sequence_length:].reset_index(drop=True)

    # Compute derived features over full sequence
    df_features = compute_derived_features(df)

    # Extract required feature columns in exact ONNX order
    feature_matrix = df_features[ONNX_FEATURE_COLUMNS].to_numpy(dtype=np.float32)

    # Reshape to [1, sequence_length, 12]
    tensor_3d = np.expand_dims(feature_matrix, axis=0)
    return tensor_3d, df_features


def features_per_minute(readings: list[TelemetryReading]) -> pd.DataFrame:
    """The 12 model features for EVERY reading (full history, sorted by ts), without padding or
    truncation. The v3 provider slices 60-minute windows from it and recounts reefer_duration_min
    from each window's start (app/inference.V3Provider.windows)."""
    df = readings_to_dataframe(readings)
    numeric_cols = ["temp_c", "humidity", "ambient_c", "speed_kmh", "solar_radiation"]
    df[numeric_cols] = df[numeric_cols].interpolate(method="linear").bfill().ffill()
    return compute_derived_features(df)


# Konteks trip untuk GRU v5 (bench/experiments/b8/b8_lib.py: KONTEKS, konteks_trip), urutan wajib sama.
KONTEKS_COLUMNS: list[str] = [
    "menit_trip", "suhu_awal_muat", "kini_minus_awal", "tren_240", "rata240_minus_rata60", "kemiringan_240",
]


def konteks_trip(feats: pd.DataFrame, ends: np.ndarray, mulai: pd.Timestamp | None = None,
                 suhu_awal: float | None = None) -> np.ndarray:
    """[n, 6] konteks untuk baris `ends` dari features_per_minute. Kausal, sama dengan b8_lib.konteks_trip.

    Menit trip dihitung dari `mulai` (bacaan pertama trip) dan suhu_awal = rata-rata 5 bacaan pertama trip.
    Keduanya perlu diisi bila `feats` hanya memuat riwayat terakhir (worker-infer membatasi 240 menit); tanpa
    keduanya `feats` dianggap dimulai dari awal trip. Menit tanpa bacaan diisi bacaan terakhir di grid 1 menit.
    """
    ts = pd.to_datetime(feats["ts"])
    m0 = 0 if mulai is None else round((ts.iloc[0] - pd.Timestamp(mulai)).total_seconds() / 60)
    menit = np.round((ts - ts.iloc[0]).dt.total_seconds().to_numpy() / 60).astype(int)
    y = pd.Series(feats["temp_c"].to_numpy(np.float64), index=menit)
    y = y[~y.index.duplicated(keep="last")].reindex(np.arange(menit[-1] + 1)).ffill().bfill().to_numpy()
    awal = float(np.mean(y[:5])) if suhu_awal is None else float(suhu_awal)
    out = np.zeros((len(ends), len(KONTEKS_COLUMNS)), np.float32)
    for k, j in enumerate(menit[ends]):
        t = m0 + j                                   # menit trip absolut
        a = max(0, max(0, t - 239) - m0)             # awal 240 menit (dipotong bila riwayat lebih pendek)
        a60 = max(0, max(0, t - 59) - m0)
        seg = y[a:j + 1]
        m = len(seg)
        x = np.arange(m, dtype=np.float64)
        den = m * (x * x).sum() - x.sum() ** 2
        slope = (m * (x * seg).sum() - x.sum() * seg.sum()) / den if den > 0 else 0.0
        out[k] = [t, awal, y[j] - awal, y[j] - y[a], seg.mean() - y[a60:j + 1].mean(), slope]
    return out
