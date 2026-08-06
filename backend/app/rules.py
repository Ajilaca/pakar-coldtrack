"""Deterministic Rule Engine v1 and Cargo Risk Scorer module."""

import pandas as pd

from app.config import settings
from app.schemas import FeatureDriver, RecommendedAction


def evaluate_cargo_limits(
    cargo_profile: str,
) -> dict[str, float]:
    """Retrieve temperature limits for a cargo profile from configuration."""
    profiles = settings.get("cargo_profiles", {})
    profile = profiles.get(cargo_profile, profiles.get("vaksin_2_8C", {}))
    return {
        "min_temp_c": profile.get("min_temp_c", 2.0),
        "max_temp_c": profile.get("max_temp_c", 8.0),
        "critical_temp_c": profile.get("critical_temp_c", 10.0),
    }


def compute_risk_index(
    current_temp: float,
    forecast: dict[str, float],
    cargo_profile: str,
    df_features: pd.DataFrame,
) -> tuple[float, str]:
    """Compute Cargo Risk Index (0.0 to 1.0) and status classification."""
    limits = evaluate_cargo_limits(cargo_profile)
    max_limit = limits["max_temp_c"]
    crit_limit = limits["critical_temp_c"]
    min_limit = limits["min_temp_c"]

    # 1. Temperature Breach Risk Component (40%)
    latest_t = current_temp
    future_max = max(forecast.get("t15", latest_t), forecast.get("t30", latest_t), forecast.get("t60", latest_t))
    
    if future_max >= crit_limit:
        temp_risk = 1.0
    elif future_max > max_limit:
        temp_risk = (future_max - max_limit) / (crit_limit - max_limit)
    elif latest_t < min_limit:
        temp_risk = 0.8
    else:
        temp_risk = max(0.0, (latest_t - min_limit) / (max_limit - min_limit) * 0.3)

    # 2. Temperature Rate of Rise Risk Component (25%)
    latest_delta = df_features["delta_temp"].iloc[-5:].mean() if len(df_features) >= 5 else 0.0
    if latest_delta > 0.1:
        rate_risk = min(1.0, latest_delta * 5.0)
    else:
        rate_risk = 0.0

    # 3. Reefer State Risk Component (20%)
    reefer_on = df_features["reefer_on"].iloc[-1] if "reefer_on" in df_features else 1
    reefer_risk = 0.8 if reefer_on == 0 else 0.0

    # 4. Door State Risk Component (15%)
    door_open = df_features["door_open"].iloc[-1] if "door_open" in df_features else 0
    door_risk = 0.7 if door_open == 1 else 0.0

    weights = settings.get("risk_weights", {})
    w_temp = weights.get("temp_breach", 0.40)
    w_rate = weights.get("temp_rate_of_rise", 0.25)
    w_reefer = weights.get("reefer_off", 0.20)
    w_door = weights.get("door_open", 0.15)

    raw_risk = (
        temp_risk * w_temp
        + rate_risk * w_rate
        + reefer_risk * w_reefer
        + door_risk * w_door
    )
    risk_index = float(round(min(1.0, max(0.0, raw_risk)), 2))

    # Classify status
    if risk_index >= 0.70 or future_max >= crit_limit:
        status = "KRITIS"
        # Ensure risk index is elevated for critical breaches
        risk_index = max(risk_index, 0.85)
    elif risk_index >= 0.35 or future_max > max_limit:
        status = "WASPADA"
        risk_index = max(risk_index, 0.45)
    else:
        status = "AMAN"

    return risk_index, status


def generate_recommended_actions(
    status: str,
    failure_label: str,
    cargo_profile: str,
) -> list[RecommendedAction]:
    """Generate 3 prioritized actionable recommendations."""
    if status == "KRITIS":
        if "kompresor" in failure_label or "reefer" in failure_label:
            return [
                RecommendedAction(
                    priority=1,
                    text="Hubungi pengemudi: hentikan di titik teduh terdekat, periksa kondensor.",
                    eta_min=5,
                ),
                RecommendedAction(
                    priority=2,
                    text="Siapkan truk pengganti dari Depo Cakung (11 km, ~19 menit).",
                    eta_min=19,
                ),
                RecommendedAction(
                    priority=3,
                    text="Beri tahu penerima; siapkan berita acara ekskursi suhu sesuai CDOB.",
                    eta_min=10,
                ),
            ]
        elif "pintu" in failure_label:
            return [
                RecommendedAction(
                    priority=1,
                    text="Peringatan pengemudi: Pintu kargo terbuka! Tutup dan kunci pintu segera.",
                    eta_min=2,
                ),
                RecommendedAction(
                    priority=2,
                    text="Periksa sensor pintu dan segel fisik ruang kargo.",
                    eta_min=10,
                ),
                RecommendedAction(
                    priority=3,
                    text="Verifikasi integritas kargo termolabil.",
                    eta_min=15,
                ),
            ]
        else:
            return [
                RecommendedAction(
                    priority=1,
                    text="Instruksikan pengemudi untuk memeriksa unit reefer dan indikator panel.",
                    eta_min=5,
                ),
                RecommendedAction(
                    priority=2,
                    text="Koordinasikan pengalihan rute ke fasilitas pendingin darurat terdekat.",
                    eta_min=15,
                ),
                RecommendedAction(
                    priority=3,
                    text="Laporkan insiden suhu ke tim Quality Assurance.",
                    eta_min=20,
                ),
            ]
    elif status == "WASPADA":
        return [
            RecommendedAction(
                priority=1,
                text="Kirim notifikasi ke pengemudi untuk memantau indikator suhu reefer.",
                eta_min=5,
            ),
            RecommendedAction(
                priority=2,
                text="Hindari paparan sinar matahari langsung, prioritaskan jalur cepat.",
                eta_min=10,
            ),
            RecommendedAction(
                priority=3,
                text="Pantau grafik tren suhu di portal telemetri.",
                eta_min=15,
            ),
        ]
    else:  # AMAN
        return [
            RecommendedAction(
                priority=1,
                text="Sistem beroperasi normal. Lanjutkan pemantauan rutin rute pengiriman.",
                eta_min=None,
            ),
            RecommendedAction(
                priority=2,
                text="Pastikan unit reefer tetap aktif hingga titik tujuan.",
                eta_min=None,
            ),
            RecommendedAction(
                priority=3,
                text="Dokumentasikan log suhu otomatis saat kedatangan.",
                eta_min=None,
            ),
        ]


def compute_feature_drivers(df_features: pd.DataFrame) -> list[FeatureDriver]:
    """Calculate top 3 feature driver contributions."""
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
