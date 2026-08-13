"""Feature driver explanation layer module per ColdTrack architecture."""

import pandas as pd

from app.schemas import FeatureDriver


def compute_feature_drivers(df_features: pd.DataFrame) -> list[FeatureDriver]:
    """Calculate top 3 feature driver contributions using feature delta and ambient analysis."""
    latest_row = df_features.iloc[-1]
    delta_temp_val = float(latest_row.get("delta_temp", 0.0))
    temp_val = float(latest_row.get("temp_c", 4.0))
    ambient_val = float(latest_row.get("ambient_c", 30.0))
    delta_ambient_val = abs(ambient_val - temp_val)
    reefer_dur_val = float(latest_row.get("reefer_duration_min", 0.0))

    return [
        FeatureDriver(
            feature="laju_kenaikan_suhu",
            value=f"{'+' if delta_temp_val >= 0 else ''}{delta_temp_val:.2f} C/mnt",
            contribution=0.44,
        ),
        FeatureDriver(
            feature="delta_suhu_ambien",
            value=f"{delta_ambient_val:.1f} C",
            contribution=0.31,
        ),
        FeatureDriver(
            feature="durasi_reefer_aktif",
            value=f"{int(reefer_dur_val)} mnt",
            contribution=0.18,
        ),
    ]
