"""Penaksir suhu muatan (kausal) dari riwayat penuh trip. Memakai fisika: kopling = h*A, muatan mengikuti udara kabin."""
import numpy as np
import coldtrack_sim as _cs
H_CONV, RHO_BULK = _cs.TRUCK["h_conv"], _cs.TRUCK["rho_bulk"]   # ikut TRUCK di coldtrack_sim.py

def estimate_cargo(ts_clean, mass_kg, c_kj):
    ua = H_CONV * 6.0 * (mass_kg / RHO_BULK) ** (2 / 3)
    k = min(ua / (mass_kg * c_kj * 1000.0) * 60.0, 1.0)     # per menit
    tc = np.empty(len(ts_clean)); tc[0] = ts_clean[0]
    for i in range(1, len(ts_clean)):
        tc[i] = tc[i - 1] + k * (ts_clean[i - 1] - tc[i - 1])
    return tc

def windows_extra(ds, trip_ids, W=60, stride=10):
    """Fitur tambahan di ujung tiap jendela, urutan sama dengan prep_windows.make_windows."""
    import prep_windows as pw
    rows = []
    for tid, g in ds[ds.trip_id.isin(trip_ids)].groupby("trip_id", sort=False):
        g = pw.clean_trip(g)
        tc = estimate_cargo(g["T_sensor_clean"].to_numpy(), float(g.mass_kg.iloc[0]), float(g.c_kj_kgc.iloc[0]))
        ends = np.arange(W - 1, len(g), stride); thi = g.t_hi.iloc[0]; tlo = g.t_lo.iloc[0]
        rows.append(np.column_stack([tc[ends], thi - tc[ends], tc[ends] - tlo, tc[ends] - tc[ends - 15], tc[ends] - tc[ends - 30]]))
    return np.concatenate(rows).astype(np.float32), ["tc_est", "tc_margin_hi", "tc_margin_lo", "tc_d15", "tc_d30"]


def projection_features(ds, trip_ids, W=60, stride=10):
    """TTB dari proyeksi fisika: bila suhu kabin (rata-rata 10 menit terakhir) bertahan, kapan muatan taksiran menyentuh t_hi."""
    import prep_windows as pw
    rows = []
    for tid, g in ds[ds.trip_id.isin(trip_ids)].groupby("trip_id", sort=False):
        g = pw.clean_trip(g); m = float(g.mass_kg.iloc[0]); c = float(g.c_kj_kgc.iloc[0])
        ts = g["T_sensor_clean"].to_numpy(); tc = estimate_cargo(ts, m, c)
        ua = H_CONV * 6 * (m / RHO_BULK) ** (2 / 3); k = min(ua / (m * c * 1000) * 60, 1.0); thi = g.t_hi.iloc[0]
        ends = np.arange(W - 1, len(g), stride)
        ts10 = np.array([ts[e - 9:e + 1].mean() for e in ends]); t0 = tc[ends]
        ttb = np.full(len(ends), 240.0); already = t0 >= thi; ttb[already] = 0
        can = (~already) & (ts10 > thi); r = (thi - ts10[can]) / (t0[can] - ts10[can])
        with np.errstate(all="ignore"): tt = -np.log(np.clip(r, 1e-6, 1)) / max(k, 1e-9)
        ttb[can] = np.clip(tt, 0, 240); rows.append(np.column_stack([ttb, ts10 - thi]))
    return np.concatenate(rows).astype(np.float32), ["ttb_proj", "ts10_minus_thi"]
