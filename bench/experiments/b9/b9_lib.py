"""Pustaka B9: sinyal kompresor SINTETIS (siklus kerja + arus saat menyala) di atas trip dataset v4.

Tujuan: menyiapkan kontrak fitur yang nanti diisi sensor sungguhan (sinyal kopling kompresor lewat
optocoupler, clamp arus lewat XADC FPGA), sebelum ada data nyata. Semua besaran di CFG berlabel
[SIM] (diambil dari simulator v4), [REPO] (dari parameter lain di repo), atau [ASUMSI].

Kondisi mesin c(t) mengikuti aturan injeksi simulator v4 (ml/simulator/02_simulator_fixed_v4.ipynb):
A2 kapasitas u turun linear 1 -> 0,15 selama 120 menit sejak onset lalu tetap 0,15; A3 u = 0 sejak
onset; A4 k_cool x 0,6 sejak onset; selain itu 1.

Siklus kerja TIDAK diturunkan dari pengendali proporsional simulator (itu hanya salinan suhu);
dihitung dari model termostat terpisah: duty = beban panas / kapasitas, dengan beban dari suhu
luar, radiasi, pintu, dan faktor isolasi per truk yang tidak diketahui model. Penurunan arus saat
gangguan adalah satu-satunya efek yang dikarang; besarnya diatur `skala_efek` untuk uji
sensitivitas. Tidak ada fitur yang membandingkan dengan awal trip (di simulator gangguan selalu
mulai di tengah trip, sehingga baseline awal trip akan menjadi artefak seperti suhu saat muat).
"""

import numpy as np

KOLOM = ["duty_kompresor", "arus_nyala_relatif"]

CFG = {
    "k_leak": 0.5, "k_door": 8.0, "k_solar": 0.05,   # [SIM] koefisien beban simulator v4
    "margin_kapasitas": 1.5,     # [REPO] Qmargin di backend/app/core/coldtrack_sim.TRUCK, pada kondisi rancangan
    "solar_rancangan": 700.0,    # [SIM] radiasi puncak generate_ambient_solar (W/m2)
    "ta_rancangan": 31.0,        # [SIM] suhu luar maksimum generate_ambient_solar (C)
    "ta_acuan": 28.5,            # [SIM] suhu luar rata-rata; acuan efek suhu di bawah
    "kap_turun_per_c": 0.015,    # [ASUMSI] kapasitas turun 1,5 %/C di atas suhu acuan
    "arus_naik_per_c": 0.010,    # [ASUMSI] arus naik 1 %/C di atas suhu acuan
    "isolasi": (0.8, 1.4),       # [ASUMSI] faktor beban dinding per truk (selaras K 0,40 vs 0,70 di TRUCK)
    "derau_beban": 0.05,         # [ASUMSI] variasi beban per menit
    "arus_nominal_sd": 0.08,     # [ASUMSI] beda unit dan tegangan antar truk
    "derau_arus": 0.02,          # [ASUMSI] kelas akurasi umum CT murah
    "offset_kal_sd": 0.02,       # [ASUMSI] offset kalibrasi CT
    "derau_duty": 0.01,          # [ASUMSI] kuantisasi pembacaan kopling
    "duty_min": 0.05,
    "efek_a4": (0.05, 0.15),     # [ASUMSI] arus saat menyala turun 5-15 % (refrigeran kurang)
    "efek_a2": (0.10, 0.25),     # [ASUMSI] arus turun s.d. 10-25 % saat kapasitas 0,15 (kompresor aus)
}
SETPOINT = {"vaksin_2_8C": 5.0, "daging_beku": -21.5, "ikan_segar": 2.5, "sayur_buah": 3.0, "produk_susu": 3.0}  # [SIM]


def kapasitas(mode, onset, n):
    c = np.ones(n)
    if mode == "A2":
        akhir = min(onset + 120, n)
        c[onset:akhir] = np.linspace(1.0, 0.15, akhir - onset)
        c[akhir:] = 0.15
    elif mode == "A3":
        c[onset:] = 0.0
    elif mode == "A4":
        c[onset:] = 0.6
    return c


def sinyal_trip(g, mode, onset, rng, cfg=CFG, skala_efek=1.0, isolasi=None):
    """g: DataFrame satu trip urut menit. Kembalikan (duty, arus_nyala_relatif) per menit."""
    n = len(g)
    ta = g["ambient_c"].to_numpy(float)
    t = g["temp_true_c"].to_numpy(float)
    sol = g["solar_radiation"].to_numpy(float)
    door = g["door_open"].to_numpy(float)
    c = kapasitas(mode, onset, n)

    lo, hi = isolasi or cfg["isolasi"]
    iso = rng.uniform(lo, hi)
    beban = (iso * cfg["k_leak"] * (ta - t) + cfg["k_door"] * door * (ta - t) + cfg["k_solar"] * sol)
    beban *= 1 + rng.normal(0, cfg["derau_beban"], n)
    tset = SETPOINT[g["cargo_type"].iloc[0]]
    q_nom = cfg["margin_kapasitas"] * (cfg["k_leak"] * (cfg["ta_rancangan"] - tset)
                                       + cfg["k_solar"] * cfg["solar_rancangan"])
    panas = np.maximum(ta - cfg["ta_acuan"], 0)
    q_kap = q_nom * c * (1 - cfg["kap_turun_per_c"] * panas)
    with np.errstate(divide="ignore", invalid="ignore"):
        duty = np.where(c > 0, np.clip(beban / q_kap, cfg["duty_min"], 1.0), 0.0)
    duty = np.clip(duty + rng.normal(0, cfg["derau_duty"], n) * (c > 0), 0, 1)

    efek = np.ones(n)
    if mode == "A4":
        efek[onset:] = 1 - skala_efek * rng.uniform(*cfg["efek_a4"])
    elif mode == "A2":
        efek = 1 - skala_efek * rng.uniform(*cfg["efek_a2"]) * (1 - c) / 0.85
    arus = (rng.normal(1, cfg["arus_nominal_sd"]) * (1 + rng.normal(0, cfg["offset_kal_sd"]))
            * (1 + cfg["arus_naik_per_c"] * panas) * efek * (1 + rng.normal(0, cfg["derau_arus"], n)))
    arus = np.where(c > 0, arus, 0.0)
    return duty.astype(np.float32), arus.astype(np.float32)


def jendela(split, skala_efek=1.0, isolasi=None, seed=9000, izinkan_test=False):
    """Jendela 60 menit x KOLOM untuk `split`, urutan identik dengan build_windows (diverifikasi)."""
    import pandas as pd

    from bench.core.common import DATA_PATH
    from bench.experiments.b8.b8_lib import path_npz
    from ml.preprocess.build_windows import HORIZONS, WINDOW_SIZE
    from ml.tests.test_data_contract import FEATURE_COLUMNS

    ref_path = path_npz(split, izinkan_test)
    df = pd.read_parquet(DATA_PATH)
    out = []
    for tid, g in df.groupby("trip_id"):
        if g["split"].iloc[0] != split:
            continue
        g = g.sort_values("minute").reset_index(drop=True)
        feats = g[FEATURE_COLUMNS].values.astype(np.float32)
        temp = g["temp_c"].values.astype(np.float32)
        max_start = len(g) - WINDOW_SIZE - max(HORIZONS)
        if max_start < 0:
            continue
        mode = next((m for m in pd.unique(g["failure_mode"]) if m != "A0"), "A0")
        onset = 0 if pd.isna(g["onset_minute"].iloc[0]) else int(g["onset_minute"].iloc[0])
        rng = np.random.default_rng(seed + int(tid))
        duty, arus = sinyal_trip(g, mode, onset, rng, skala_efek=skala_efek, isolasi=isolasi)
        sig = np.column_stack([duty, arus])
        for start in range(max_start + 1):
            t = start + WINDOW_SIZE - 1
            if np.isnan(feats[start:start + WINDOW_SIZE]).any() or np.isnan([temp[t + h] for h in HORIZONS]).any():
                continue
            out.append(sig[start:start + WINDOW_SIZE])
    out = np.stack(out)
    if len(out) != len(np.load(ref_path)["y_mode"]):
        raise RuntimeError(f"jumlah jendela B9 {split} tidak cocok dengan build_windows")
    return out
