"""
Mesin terpadu ColdTrack: telemetri per menit -> status AMAN/WASPADA/KRITIS, TTB, sisa waktu pintu, status sensor.
Semua hitungan bersifat kausal (nilai di menit t hanya memakai data sampai menit t), jadi bisa dijalankan
menit demi menit di frontend. Bagian belajar (GRU/XGBoost) ditambahkan terpisah (engine tidak bergantung padanya).
"""
import numpy as np, pandas as pd
import coldtrack_sim as cs, observer as ob, sensor_rules as sr, door_budget as db

AMAN, WASPADA, KRITIS = 0, 1, 2
NAMA = {0: "AMAN", 1: "WASPADA", 2: "KRITIS"}
CFG = dict(
    ttb_kritis=30,          # TTB <= 30 menit -> minimal KRITIS      (proposal lama)
    ttb_waspada=60,         # TTB <= 60 menit -> minimal WASPADA     (proposal lama)
    ttb_tampil=60,          # TTB hanya ditampilkan bila <= ini       (proposal lama: 30; dilonggarkan, lihat dokumen)
    margin_waspada_k=1.0,   # muatan < 1 K dari batas atas -> WASPADA (DESAIN)
    door_waspada_min=30,    # pintu terbuka dan sisa waktu kasus terburuk <= 30 menit -> WASPADA (DESAIN)
    entry_tol_k=2.0,        # suhu awal muatan > t_set + 2 K -> peringatan pra-pendinginan (DESAIN)
)


def check_entry(t_init, t_lo, t_hi, t_set, cfg=CFG):
    """Aturan masuk truk (A8): periksa suhu muatan saat naik."""
    if t_init > t_hi: return "TOLAK", f"Suhu muatan {t_init:.1f} C sudah melewati batas {t_hi:.1f} C."
    if t_init < t_lo: return "TOLAK", f"Suhu muatan {t_init:.1f} C di bawah batas bawah {t_lo:.1f} C."
    if t_init > t_set + cfg["entry_tol_k"]: return "PERINGATAN", f"Muatan {t_init:.1f} C lebih hangat dari titik setel {t_set:.1f} C (pra-pendinginan kurang)."
    return "OK", "Suhu awal muatan sesuai."


def _roll_mean(x, w):
    c = np.cumsum(np.insert(x, 0, 0.0)); n = np.arange(1, len(x) + 1); lo = np.maximum(n - w, 0)
    idx = np.arange(1, len(x) + 1)
    return (c[idx] - c[lo]) / (idx - lo)


def ttb_series(ts_clean, tc, tamb, door, moving, k, thi, slope_thr=0.15):
    """TTB fisika per menit: bila kabin bertahan (atau menuju suhu luar saat pintu terbuka / berhenti dan memanas)."""
    n = len(ts_clean); ts10 = _roll_mean(ts_clean, 10)
    slope = np.r_[np.zeros(5), (ts_clean[5:] - ts_clean[:-5]) / 5.0]
    heating = (door > 0.5) | ((moving < 0.5) & (slope > slope_thr))
    cab = np.where(heating, np.maximum(ts10, tamb), ts10)
    ttb = np.full(n, 240.0); already = tc >= thi; ttb[already] = 0
    can = (~already) & (cab > thi)
    r = (thi - cab[can]) / (tc[can] - cab[can])
    with np.errstate(all="ignore"): tt = -np.log(np.clip(r, 1e-6, 1)) / max(k, 1e-9)
    ttb[can] = np.clip(tt, 0, 240)
    return ttb, cab


def run(tel, prod, mass_kg, cfg=CFG):
    """
    tel : DataFrame per menit dengan kolom T_sensor, T_amb, door_open, moving  (RH_amb dan hour_of_day opsional)
    prod: dict dari coldtrack_sim.get_product (c, t_lo, t_hi, t_set)
    Kembalikan DataFrame hasil per menit.
    """
    ts_raw = tel["T_sensor"].to_numpy(float); tamb = tel["T_amb"].to_numpy(float)
    door = tel["door_open"].to_numpy(float); moving = tel["moving"].to_numpy(float)
    batt = tel["battery_v"].to_numpy(float) if "battery_v" in tel else None
    sst = sr.sensor_status(ts_raw, door > 0.5, tamb, moving=moving, battery_v=batt)

    bad = (ts_raw > sr.SENSOR_MAX) | (ts_raw < sr.SENSOR_MIN)
    ts = pd.Series(np.where(bad, np.nan, ts_raw)).ffill().fillna(prod["t_set"]).to_numpy()   # tahan nilai valid terakhir
    c, thi, tlo = prod["c"], prod["t_hi"], prod["t_lo"]
    tc = ob.estimate_cargo(ts, mass_kg, c)
    k = db._k_cargo(mass_kg, c)
    ttb, cab = ttb_series(ts, tc, tamb, door, moving, k, thi)
    # sisa waktu pintu (kasus terburuk: kabin = suhu luar)
    worst = np.array([db._time_to_limit(tc[i], tamb[i], thi, k) if door[i] > 0.5 else np.nan for i in range(len(ts))])
    margin = thi - tc

    status = np.zeros(len(ts), dtype=int); reason = [""] * len(ts)
    for i in range(len(ts)):
        s, why = AMAN, "Kondisi normal."
        def up(level, txt):
            nonlocal s, why
            if level > s: s, why = level, txt
        if tc[i] >= thi or tc[i] < tlo: up(KRITIS, "Suhu muatan di luar batas aman.")
        if ttb[i] <= cfg["ttb_kritis"]: up(KRITIS, f"Muatan diperkirakan melewati batas dalam {ttb[i]:.0f} menit.")
        if ttb[i] <= cfg["ttb_waspada"]: up(WASPADA, f"Muatan diperkirakan melewati batas dalam {ttb[i]:.0f} menit.")
        if margin[i] < cfg["margin_waspada_k"]: up(WASPADA, "Suhu muatan mendekati batas atas.")
        if door[i] > 0.5 and worst[i] <= cfg["door_waspada_min"]: up(WASPADA, f"Pintu terbuka; sisa waktu kasus terburuk ~{worst[i]:.0f} menit. Tutup pintu.")
        if sst[i] >= 1:                                        # penjepit sensor: tidak boleh AMAN, dan tidak boleh KRITIS karena angka sensor
            if sst[i] == 2: s, why = WASPADA, "Sensor rusak. Verifikasi manual diperlukan; sisa waktu tidak ditampilkan."
            else: up(WASPADA, "Sensor mencurigakan. Verifikasi manual.")
        status[i] = s; reason[i] = why

    show = (ttb <= cfg["ttb_tampil"]) & (sst < 2)              # TTB disembunyikan bila sensor rusak / di luar rentang
    out = pd.DataFrame(dict(minute=np.arange(len(ts)), T_sensor=ts_raw, T_cargo_est=tc, margin_hi=margin, ttb_phys=ttb,
                            ttb_show=np.where(show, ttb, np.nan), door_budget_worst=worst, sensor_status=sst,
                            status=status, status_txt=[NAMA[x] for x in status], reason=reason))
    return out
