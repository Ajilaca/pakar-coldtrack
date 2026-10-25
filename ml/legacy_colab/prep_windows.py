"""
Langkah latihan 1: bagi trip -> bersihkan sensor (aturan) -> susun jendela 60 menit.
Masukan model HANYA telemetri yang ada di truk. Kolom kebenaran fisika (T_cargo, T_air, ev_*,
sensor_ok, reefer_duty) tidak pernah jadi masukan.
"""
import numpy as np, pandas as pd

W = 60                # panjang jendela (menit)
STRIDE = 10           # geser jendela (menit)
LONG_DOOR_MIN = 20                        # "pintu terbuka lama" = satu bukaan berlangsung >= 20 menit (DESAIN)
SENSOR_MAX, SENSOR_MIN = 60.0, -40.0     # aturan: suhu kabin di luar ini = mustahil
FEATS = ["T_sensor_clean", "T_amb", "RH_amb", "door_open", "moving", "hsin", "hcos", "sensor_bad"]
STATIC = ["log_mass", "c_kj_kgc", "t_lo", "t_hi"]


def split_trips(ds, seed=0, frac=(0.70, 0.15, 0.15)):
    """Bagi PER TRIP (satu trip tidak boleh terbelah)."""
    rng = np.random.default_rng(seed)
    ids = np.array(sorted(ds.trip_id.unique())); rng.shuffle(ids)
    n = len(ids); a, b = int(frac[0] * n), int((frac[0] + frac[1]) * n)
    return dict(train=set(ids[:a]), val=set(ids[a:b]), test=set(ids[b:]))


def clean_trip(g):
    """Aturan sensor (kausal): nilai mustahil -> tandai, ganti dengan nilai valid terakhir."""
    g = g.copy()
    ts = g["T_sensor"].to_numpy(float)
    bad = (ts > SENSOR_MAX) | (ts < SENSOR_MIN)
    s = pd.Series(np.where(bad, np.nan, ts)).ffill()
    s = s.fillna(0.0).to_numpy()   # awal trip tanpa nilai valid -> 0
    g["T_sensor_clean"] = s
    g["sensor_bad"] = bad.astype(float)
    g["hsin"] = np.sin(2 * np.pi * g["hour_of_day"] / 24)
    g["hcos"] = np.cos(2 * np.pi * g["hour_of_day"] / 24)
    g["log_mass"] = np.log(g["mass_kg"])
    g["a1_long"] = long_door_label(g["ev_A1"].to_numpy())
    return g


def long_door_label(ev):
    """Label tingkat-bukaan: seluruh menit dari satu bukaan diberi 1 bila bukaan itu >= LONG_DOOR_MIN menit.
    Di awal bukaan model belum bisa tahu bukaan akan lama, jadi bukan salinan dari door_open."""
    out = np.zeros(len(ev), dtype=np.float32)
    i, n = 0, len(ev)
    while i < n:
        if ev[i] > 0.5:
            j = i
            while j < n and ev[j] > 0.5: j += 1
            if j - i >= LONG_DOOR_MIN: out[i:j] = 1.0
            i = j
        else:
            i += 1
    return out


def make_windows(ds, trip_ids, stride=STRIDE):
    Xs, Ss, Ys, meta = [], [], [], []
    for tid, g in ds[ds.trip_id.isin(trip_ids)].groupby("trip_id", sort=False):
        g = clean_trip(g)
        F = g[FEATS].to_numpy(np.float32)
        S = g[STATIC].iloc[0].to_numpy(np.float32)
        ends = np.arange(W - 1, len(g), stride)
        idx = ends[:, None] - np.arange(W - 1, -1, -1)[None, :]
        Xs.append(F[idx]); Ss.append(np.tile(S, (len(ends), 1)))
        tgt = g[["a1_long", "ev_A2", "ev_A3", "ttb_min",
                 "y_Tcargo_15", "y_Tcargo_30", "y_Tcargo_60"]].to_numpy(np.float32)[ends]
        Ys.append(tgt)
        meta.append(pd.DataFrame(dict(trip_id=tid, minute=ends, mass_kg=g.mass_kg.iloc[0],
                                      state=g.state.iloc[0], category=g.category.iloc[0])))
    X = np.concatenate(Xs); S = np.concatenate(Ss); Y = np.concatenate(Ys)
    meta = pd.concat(meta, ignore_index=True)
    return X, S, Y, meta
