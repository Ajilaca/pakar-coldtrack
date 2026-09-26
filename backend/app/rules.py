"""Cargo limits and recommended actions. Status/risk now come from app.core.engine."""

from app.config import settings
from app.schemas import RecommendedAction


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
        # Sensor bermasalah butuh tindakan sendiri. Saran generik di bawah
        # menyuruh operator "memantau indikator suhu" — padahal indikator
        # itulah yang rusak. Yang benar: berhenti mempercayai sensornya dan
        # ukur manual.
        if "sensor" in failure_label.lower():
            return [
                RecommendedAction(
                    priority=1,
                    text="Verifikasi suhu kargo secara manual dengan termometer cadangan.",
                    eta_min=10,
                ),
                RecommendedAction(
                    priority=2,
                    text="Jangan ambil keputusan dari pembacaan sensor ini sampai terverifikasi.",
                    eta_min=None,
                ),
                RecommendedAction(
                    priority=3,
                    text="Jadwalkan kalibrasi ulang sensor setelah perjalanan selesai.",
                    eta_min=None,
                ),
            ]
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

