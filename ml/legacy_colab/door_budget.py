"""
door_budget: fisika murni. Saat pintu terbuka: berapa menit muatan masih aman, dan apa yang terjadi bila ditutup sekarang.
Semua konstanta truk mengikuti coldtrack_sim.TRUCK (bertag SUMBER/ASUMSI di sana).
"""
import numpy as np
import coldtrack_sim as cs

HORIZON = 240.0


def _k_cargo(mass_kg, c_kj, h=None, rho=None):
    """laju relaksasi muatan ke suhu kabin (per menit) = h*A / (m*c)."""
    h = cs.TRUCK["h_conv"] if h is None else h
    rho = cs.TRUCK["rho_bulk"] if rho is None else rho
    ua = h * 6.0 * (mass_kg / rho) ** (2 / 3)
    return min(ua / (mass_kg * c_kj * 1000.0) * 60.0, 1.0)


def _time_to_limit(tc0, tcab, thi, k):
    """Muatan mengikuti kabin: Tc(t) = tcab + (tc0 - tcab) e^{-k t}. Menit sampai Tc = thi."""
    if tc0 >= thi: return 0.0
    if tcab <= thi: return HORIZON                       # kabin tidak cukup panas untuk melewati batas
    r = (thi - tcab) / (tc0 - tcab)
    return float(np.clip(-np.log(np.clip(r, 1e-9, 1.0)) / max(k, 1e-9), 0, HORIZON))


def _close_now(ta0, tc0, tamb, mass_kg, c_kj, tset, thi, minutes=180, h=None, rho=None):
    """Simulasi maju, pintu ditutup, pendingin hidup. Kembalikan suhu muatan puncak."""
    P = cs._truck_const()
    h = cs.TRUCK["h_conv"] if h is None else h
    rho = cs.TRUCK["rho_bulk"] if rho is None else rho
    ua_ac = h * 6.0 * (mass_kg / rho) ** (2 / 3)
    Cc = mass_kg * c_kj * 1000.0
    Ta, Tc, peak, t_peak = ta0, tc0, tc0, 0
    dt, sub = 5.0, 12
    for m in range(minutes):
        for _ in range(sub):
            q = float(np.clip(P["Qmax"] * (Ta - tset) / cs.TRUCK["band_k"], 0, P["Qmax"]))
            Ta += (P["UA"] * (tamb - Ta) + ua_ac * (Tc - Ta) - q) / P["C_air"] * dt
            Tc += ua_ac * (Ta - Tc) / Cc * dt
        if Tc > peak: peak, t_peak = Tc, m + 1
    return peak, t_peak


def door_budget(tc_est, t_cabin, t_amb, mass_kg, c_kj, t_hi, t_set, h=None, rho=None):
    """
    tc_est   : suhu muatan taksiran (C), dari penaksir berjalan
    t_cabin  : bacaan sensor kabin sekarang (C)
    t_amb    : suhu luar (C)
    Kembalikan dict: sisa menit (bacaan sensor), sisa menit (kasus terburuk kabin=luar),
    dan hasil bila pintu ditutup sekarang.
    """
    k = _k_cargo(mass_kg, c_kj, h, rho)
    from_sensor = _time_to_limit(tc_est, t_cabin, t_hi, k)
    worst = _time_to_limit(tc_est, t_amb, t_hi, k)
    peak, t_peak = _close_now(t_cabin, tc_est, t_amb, mass_kg, c_kj, t_set, t_hi, h=h, rho=rho)
    return dict(sisa_menit_sensor=round(from_sensor, 1), sisa_menit_terburuk=round(worst, 1),
                jika_ditutup_puncak_c=round(peak, 2), jika_ditutup_menit_puncak=int(t_peak),
                jika_ditutup_melanggar=bool(peak > t_hi))


def sensitivity(state, h_list=(5, 10, 20), rho_list=(400, 500, 700)):
    """Seberapa jauh hasil bergeser bila asumsi h dan kerapatan berubah."""
    rows = []
    for h in h_list:
        for rho in rho_list:
            r = door_budget(**state, h=h, rho=rho); r.update(h=h, rho=rho); rows.append(r)
    return rows
