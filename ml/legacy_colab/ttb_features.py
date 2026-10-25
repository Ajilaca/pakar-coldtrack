"""
Langkah latihan 3: fitur ringkasan jendela untuk TTB (XGBoost). Semua fitur dihitung dari
masukan yang ada di truk (sama dengan GRU); tidak memakai T_cargo/T_air/ev_*.
"""
import numpy as np

# indeks kolom X dari prep_windows.FEATS
I_TS, I_TAMB, I_RH, I_DOOR, I_MOV, I_HS, I_HC, I_BAD = range(8)

def _since(flag):
    """menit sejak flag terakhir bernilai 1 dalam jendela (60 bila tidak ada)."""
    W = flag.shape[1]
    rev = flag[:, ::-1] > 0.5
    first = np.where(rev.any(1), rev.argmax(1), W)
    return first.astype(np.float32)

def build(X, S):
    ts = X[:, :, I_TS]; ta = X[:, :, I_TAMB]
    f = {}
    f["ts_last"] = ts[:, -1]
    for k in (5, 15, 30, 59):
        f[f"ts_d{k}"] = ts[:, -1] - ts[:, -1 - k]
    f["ts_std15"] = ts[:, -15:].std(1); f["ts_std60"] = ts.std(1)
    f["ts_min"] = ts.min(1); f["ts_max"] = ts.max(1); f["ts_mean"] = ts.mean(1)
    f["tamb_last"] = ta[:, -1]; f["tamb_d30"] = ta[:, -1] - ta[:, -31]; f["tamb_max"] = ta.max(1)
    f["rh_last"] = X[:, -1, I_RH]
    f["door_last"] = X[:, -1, I_DOOR]; f["door_min"] = X[:, :, I_DOOR].sum(1)
    f["since_door"] = _since(X[:, :, I_DOOR]); f["moving_sum"] = X[:, :, I_MOV].sum(1)
    f["bad_frac"] = X[:, :, I_BAD].mean(1); f["bad_last"] = X[:, -1, I_BAD]
    f["hsin"] = X[:, -1, I_HS]; f["hcos"] = X[:, -1, I_HC]
    logm, c, tlo, thi = S[:, 0], S[:, 1], S[:, 2], S[:, 3]
    f["log_mass"], f["c"], f["t_lo"], f["t_hi"] = logm, c, tlo, thi
    f["log_tmass"] = logm + np.log(c)                       # log(massa * kalor jenis)
    f["margin_hi"] = thi - ts[:, -1]                         # jarak suhu terbaca ke batas atas
    f["amb_minus_ts"] = ta[:, -1] - ts[:, -1]
    f["heat_rate_proxy"] = (ta[:, -1] - ts[:, -1]) / np.exp(f["log_tmass"])
    names = list(f); return np.column_stack([f[n] for n in names]).astype(np.float32), names
