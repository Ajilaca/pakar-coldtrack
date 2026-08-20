"""Feature driver explanation layer module per ColdTrack architecture."""

import pandas as pd

from app.schemas import FeatureDriver

# Ambang "sudah sangat mengkhawatirkan" untuk tiap sinyal. Dipakai menormalkan
# nilai mentah jadi skor 0..1 supaya besaran dengan satuan berbeda (C/menit,
# derajat, persen waktu) bisa dibandingkan secara adil.
_RATE_ALARM_C_PER_MIN = 0.05   # 0,05 C/menit = ~1 C tiap 20 menit, sudah cepat

# Yang dinilai adalah KENAIKAN suhu ambien di sepanjang jendela analisis
# (60 bacaan terakhir), bukan selisihnya dengan suhu kargo.
#
# Selisih kargo-vs-ambien pada truk reefer memang selalu besar (20-30 C) —
# itu justru bukti pendinginnya bekerja, bukan tanda bahaya. Memakai selisih
# mentah membuat sinyal ini menang di semua skenario, termasuk perjalanan
# sehat. Yang benar-benar menandakan beban termal tak biasa adalah ketika
# udara luar MENINGKAT dibanding kondisi awal perjalanan.
_AMBIENT_RISE_FLOOR_C = 2.0    # naik di bawah ini masih wajar
_AMBIENT_RISE_ALARM_C = 10.0   # naik sebesar ini bebannya ekstrem

# Radiasi matahari, dinilai dari TINGKAT nyatanya, bukan kenaikannya.
#
# Diperlukan karena beban panas bisa tinggi tanpa suhu udara ikut naik —
# persis skenario "kejut ambien saat macet": ambien hanya bergerak 1,3 C
# sementara radiasi menembus 1400 W/m2.
#
# Sengaja memakai tingkat, bukan kenaikan: jendela yang dianalisis hanya 60
# bacaan terakhir, sehingga puncak radiasi bisa jatuh di dalam jendela lalu
# menurun — dan ukuran "kenaikan" justru menghasilkan nilai negatif untuk
# perjalanan yang sedang terpanggang matahari.
_SOLAR_FLOOR = 300.0           # W/m2, di bawah ini beban surya belum berarti
_SOLAR_ALARM = 900.0           # W/m2, setara terik tengah hari

# Lantai kecil supaya pembagian tetap aman saat semua sinyal tenang, dan agar
# perjalanan sehat menghasilkan kontribusi yang hampir merata — itu memang
# gambaran jujurnya: tidak ada satu faktor yang menonjol.
_BASELINE = 0.05

_RECENT_WINDOW = 30  # jumlah bacaan terakhir yang ditimbang


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_feature_drivers(df_features: pd.DataFrame) -> list[FeatureDriver]:
    """Hitung tiga faktor pendorong teratas dari data yang benar-benar masuk.

    Sebelumnya fungsi ini mengembalikan kontribusi tetap (0,44 / 0,31 / 0,18)
    untuk semua masukan, sehingga panel "Mengapa AI berpikir begini"
    menampilkan angka yang sama persis di skenario apa pun.

    Sekarang tiap sinyal dinilai dari datanya sendiri, lalu tiga yang paling
    mengkhawatirkan diambil dan dinormalkan hingga berjumlah 1,0. Efek
    sampingnya disengaja: skenario pintu terbuka akan memunculkan "status
    pintu" di urutan atas, skenario sensor macet memunculkan "variansi suhu",
    dan seterusnya.

    CATATAN JUJUR: ini atribusi HEURISTIK, bukan SHAP. Angkanya berasal dari
    data masukan, bukan dari pembongkaran bobot model. Jangan sebut SHAP di
    proposal maupun demo.
    """
    if df_features.empty:
        return []

    latest = df_features.iloc[-1]
    recent = df_features.tail(min(_RECENT_WINDOW, len(df_features)))

    temp_now = float(latest.get("temp_c", 4.0))
    ambient_now = float(latest.get("ambient_c", 30.0))

    # --- sinyal 1: laju kenaikan suhu ---------------------------------
    rate = float(recent["delta_temp"].mean()) if "delta_temp" in recent else 0.0
    rate_sev = _clamp01(rate / _RATE_ALARM_C_PER_MIN) if rate > 0 else 0.0

    # --- sinyal 2: kenaikan suhu ambien terhadap awal perjalanan -------
    if "ambient_c" in df_features and len(df_features) >= 8:
        baseline_n = max(4, len(df_features) // 4)
        ambient_baseline = float(df_features["ambient_c"].head(baseline_n).mean())
        ambient_recent = float(recent["ambient_c"].mean())
    else:
        ambient_baseline = ambient_now
        ambient_recent = ambient_now
    ambient_rise = ambient_recent - ambient_baseline
    gap_sev = _clamp01(
        (ambient_rise - _AMBIENT_RISE_FLOOR_C) / (_AMBIENT_RISE_ALARM_C - _AMBIENT_RISE_FLOOR_C)
    )
    gap = abs(ambient_now - temp_now)

    # --- sinyal 2b: beban panas saat kendaraan berhenti ----------------
    #
    # Radiasi matahari SENDIRIAN bukan penanda bahaya — 400-700 W/m2 itu
    # siang hari biasa, dan muncul di hampir semua perjalanan siang. Yang
    # berbahaya adalah terik DITAMBAH kendaraan diam, karena aliran udara
    # pendingin kondensor hilang dan panas menumpuk di badan kargo.
    #
    # Kombinasi inilah yang memisahkan skenario "kejut ambien saat macet"
    # (diam 35% waktu di bawah 848 W/m2) dari perjalanan siang lain yang
    # tetap melaju 60 km/jam.
    # Dihitung dari SELURUH jendela, bukan 30 bacaan terakhir: panas yang
    # menumpuk selama berhenti tidak langsung hilang begitu truk jalan lagi.
    # Pada skenario "kejut ambien", macetnya terjadi di paruh awal jendela —
    # memakai 30 bacaan terakhir membuatnya terbaca "diam 0% waktu".
    solar_recent = (
        float(df_features["solar_radiation"].mean()) if "solar_radiation" in df_features else 0.0
    )
    if "speed_kmh" in df_features:
        stopped_frac = float((df_features["speed_kmh"] < 1.0).mean())
    else:
        stopped_frac = 0.0
    solar_norm = _clamp01((solar_recent - _SOLAR_FLOOR) / (_SOLAR_ALARM - _SOLAR_FLOOR))
    stopped_norm = _clamp01(stopped_frac / 0.30)  # diam 30% waktu sudah maksimal
    heat_soak_sev = solar_norm * stopped_norm

    # --- sinyal 3: unit pendingin -------------------------------------
    if "reefer_on" in recent:
        reefer_on_frac = float(recent["reefer_on"].mean())
    else:
        reefer_on_frac = 1.0
    reefer_sev = _clamp01(1.0 - reefer_on_frac)  # makin sering mati, makin gawat
    reefer_dur = float(latest.get("reefer_duration_min", 0.0))

    # --- sinyal 4: pintu kargo ----------------------------------------
    #
    # Dinilai dari SELURUH jendela, bukan 30 bacaan terakhir, dan diberi
    # bobot dasar begitu pintu pernah terbuka. Alasannya: membuka pintu itu
    # peristiwa sesaat tetapi panas yang masuk bertahan lama. Menilainya
    # murni dari "berapa persen waktu pintu terbuka" membuat kejadian nyata
    # yang baru saja lewat nyaris tak terbaca.
    if "door_open" in df_features:
        door_frac = float(df_features["door_open"].mean())
        door_ever = bool(df_features["door_open"].max())
    else:
        door_frac, door_ever = 0.0, False
    door_sev = _clamp01(0.40 + door_frac * 3.0) if door_ever else 0.0

    # --- sinyal 5: variansi pembacaan (deteksi sensor macet) ----------
    temp_std = float(recent["temp_c"].std()) if "temp_c" in recent else 0.0
    if pd.isna(temp_std):
        temp_std = 0.0
    # std mendekati nol pada jendela sepanjang ini tidak wajar untuk kargo hidup
    stuck_sev = _clamp01(1.0 - temp_std / 0.05) if len(recent) >= 10 else 0.0

    candidates: list[tuple[str, str, float]] = [
        (
            "laju_kenaikan_suhu",
            f"{'+' if rate >= 0 else ''}{rate:.2f} C/mnt",
            rate_sev,
        ),
        (
            "delta_suhu_ambien",
            f"{'+' if ambient_rise >= 0 else ''}{ambient_rise:.1f} C (selisih {gap:.0f} C)",
            gap_sev,
        ),
        (
            "beban_panas_berhenti",
            f"{solar_recent:.0f} W/m2, diam {stopped_frac * 100:.0f}% waktu",
            heat_soak_sev,
        ),
        (
            "durasi_reefer_aktif",
            "mati" if reefer_on_frac < 0.5 else f"{int(reefer_dur)} mnt",
            reefer_sev,
        ),
        (
            "status_pintu",
            (
                f"terbuka {door_frac * 100:.0f}% waktu"
                if door_frac > 0.5
                else (f"sempat terbuka ({door_frac * 100:.0f}% waktu)" if door_ever else "tertutup")
            ),
            door_sev,
        ),
        (
            "variansi_suhu",
            f"{temp_std:.3f} C",
            stuck_sev,
        ),
    ]

    top3 = sorted(candidates, key=lambda c: c[2], reverse=True)[:3]
    total = sum(sev + _BASELINE for _, _, sev in top3)

    return [
        FeatureDriver(
            feature=name,
            value=value,
            contribution=round((sev + _BASELINE) / total, 3),
        )
        for name, value, sev in top3
    ]
