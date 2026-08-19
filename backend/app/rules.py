"""Deterministic Rule Engine v1 and Cargo Risk Scorer module."""

import pandas as pd

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


# Urutan keparahan status — dipakai agar eskalasi TTB hanya bisa MENAIKKAN.
_SEVERITY: dict[str, int] = {"AMAN": 0, "WASPADA": 1, "KRITIS": 2}


def compute_risk_index(
    current_temp: float,
    forecast: dict[str, float],
    cargo_profile: str,
    df_features: pd.DataFrame,
    time_to_breach_min: float | None = None,
    failure_label: str | None = None,
) -> tuple[float, str]:
    """Compute Cargo Risk Index (0.0 to 1.0) and status classification.

    `time_to_breach_min` dan `failure_label` bersifat opsional supaya
    pemanggil lama tetap jalan; kalau diisi, keduanya dipakai sebagai lantai
    status (lihat blok eskalasi di bagian bawah fungsi ini).
    """
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

    # --- Eskalasi berbasis Time-to-Breach --------------------------------
    #
    # KENAPA INI PERLU:
    # Blok klasifikasi di atas hanya melihat `forecast`, sementara TTB
    # dihasilkan kepala model ONNX yang terpisah. Keduanya bisa tidak
    # sepakat. Contoh nyata dari skenario demo "kompresor melemah":
    #
    #     prediksi suhu maksimum = 3,73 °C   (batas profil = 4,0 °C)
    #     -> tidak melanggar -> risk 0,11 -> status AMAN
    #     TTB model            = 19,5 menit -> MELANGGAR, tapi diabaikan
    #
    # Hasilnya lampu hijau "AMAN" muncul tepat di sebelah tulisan
    # "19 menit lagi sebelum ambang terlampaui" — jelas keliru, dan
    # membuat rekomendasi tindakan ikut salah (menyarankan "pemantauan
    # rutin" pada muatan yang akan rusak dalam 20 menit).
    #
    # Karena itu TTB dipakai sebagai LANTAI status. Blok ini hanya bisa
    # MENAIKKAN keparahan, tidak pernah menurunkan, sehingga kasus yang
    # sudah benar sebelumnya tidak berubah sama sekali.
    if time_to_breach_min is not None and time_to_breach_min >= 0:
        ttb_cfg = settings.get("ttb_status_thresholds", {})
        crit_max = ttb_cfg.get("critical_max_min", 30)
        warn_max = ttb_cfg.get("warning_max_min", 60)

        if time_to_breach_min <= crit_max:
            escalated = "KRITIS"
        elif time_to_breach_min <= warn_max:
            escalated = "WASPADA"
        else:
            escalated = None

        if escalated and _SEVERITY[escalated] > _SEVERITY[status]:
            status = escalated
            risk_index = max(risk_index, 0.85 if status == "KRITIS" else 0.45)

    # --- Sensor bermasalah: KUNCI di WASPADA -----------------------------
    #
    # Kalau model mendiagnosis sensor macet/rusak, seluruh perhitungan di
    # atas berdiri di atas angka yang tidak bisa dipercaya: suhu terlihat
    # stabil justru KARENA sensornya beku, bukan karena muatannya aman.
    #
    # Blok ini sengaja bekerja DUA ARAH, bukan sekadar lantai:
    #
    #   - tidak boleh AMAN   -> jangan beri rasa aman palsu dari alat ukur
    #                           yang sudah diketahui rusak.
    #   - tidak boleh KRITIS -> jangan mengklaim kepastian dari alat ukur
    #                           yang sama. Pada skenario "sensor macet",
    #                           60 bacaan terakhir bernilai identik (3,95)
    #                           namun kepala TTB tetap mengeluarkan 23,8
    #                           menit. Angka itu hasil ekstrapolasi dari
    #                           sinyal beku, jadi menaikkannya ke KRITIS
    #                           berarti menampilkan presisi yang tidak
    #                           dimiliki sistem.
    #
    # Pesan yang benar untuk kondisi ini adalah "alat ukur tidak dapat
    # dipercaya, verifikasi manual" — dan itu tepat WASPADA.
    #
    # Angka TTB-nya sendiri disembunyikan di main.py, dengan alasan sama.
    if failure_label and "sensor" in failure_label.lower():
        status = "WASPADA"
        risk_index = min(max(risk_index, 0.45), 0.60)

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

