"""Fitur jendela per mote + label + skor aturan v0 (definisi: bench/results/keputusan/G4_definisi.json).

Semua fitur kausal: hanya memakai menit <= akhir jendela. Data disusun sebagai matriks
[mote x menit] (NaN = tidak ada bacaan / setelah mote gagal), lalu dipotong jendela 60 menit
berlangkah 10 menit.

  python -m ml.sensor_health.features      -> data/berkeley/windows.parquet (tidak dikomit)
"""

import time

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv

from ml.sensor_health import data as sd

JENDELA, LANGKAH = 60, 10
H_UTAMA, H_SEKUNDER = 24, (1, 6)
K_TETANGGA = 3
LOMPAT_C = 5.0                     # sama dengan JUMP_C aturan v0
SPLIT_SEED, SPLIT_PORSI = 0, (0.6, 0.2, 0.2)
OUT = sd.DATA_DIR / "windows.parquet"


def susun_matriks(pm, ev):
    menit = pd.date_range(pm["menit"].min(), pm["menit"].max(), freq="min")
    motes = list(ev.index)
    r = pm["moteid"].map({m: i for i, m in enumerate(motes)}).to_numpy()
    c = ((pm["menit"] - menit[0]) // pd.Timedelta(minutes=1)).to_numpy()
    M = {}
    for k in ["temperature", "humidity", "light", "voltage", "n_bacaan"]:
        a = np.full((len(motes), len(menit)), np.nan, np.float32)
        a[r, c] = pm[k].to_numpy(np.float32)
        M[k] = a
    gagal = np.array([((t.floor("min") - menit[0]) // pd.Timedelta(minutes=1)) if pd.notna(t) else len(menit)
                      for t in ev["t_gagal"]])
    for a in M.values():                            # data pada/ setelah kegagalan tidak dipakai
        for i, f in enumerate(gagal):
            a[i, max(f, 0):] = np.nan
    return menit, motes, M, gagal


def tetangga(motes, loc, k=K_TETANGGA):
    xy = loc.reindex(motes)[["x", "y"]].to_numpy(float)
    d = np.sqrt(((xy[:, None, :] - xy[None, :, :]) ** 2).sum(-1))
    np.fill_diagonal(d, np.inf)
    return np.argsort(d, axis=1)[:, :k]


def ffill(a):
    """Forward-fill sepanjang sumbu terakhir (NaN awal tetap NaN)."""
    idx = np.where(~np.isnan(a), np.arange(a.shape[-1]), 0)
    np.maximum.accumulate(idx, axis=-1, out=idx)
    out = np.take_along_axis(a, idx, axis=-1)
    out[..., :1][np.isnan(a[..., :1])] = np.nan
    return out


def panjang_datar(t):
    """Panjang rangkaian nilai sama berturut-turut (antar bacaan valid, dibulatkan 0,01 C) di tiap menit."""
    out = np.zeros_like(t)
    run, prev = 0.0, np.nan
    for i, v in enumerate(t):
        if np.isnan(v):
            out[i] = run
            continue
        v = round(float(v), 2)
        run = run + 1 if v == prev else 0.0
        prev = v
        out[i] = run
    return out


def lompatan(t):
    """|selisih| terhadap bacaan valid sebelumnya, di menit yang punya bacaan; NaN di menit kosong."""
    prev = np.concatenate([[np.nan], ffill(t)[:-1]])
    j = np.abs(t - prev)
    j[np.isnan(t)] = np.nan
    return j


def skor_v0(t, v):
    """Status aturan v0 per menit. Menit tanpa bacaan dilewati (deret dipadatkan) lalu dipetakan balik."""
    from backend.app.core.sensor_rules import sensor_status

    ok = ~np.isnan(t)
    st = np.zeros(len(t), np.float32)
    if ok.sum() == 0:
        return st
    tt = t[ok].astype(float)
    vv = np.where(np.isnan(v[ok]), 3.0, v[ok]).astype(float)   # tegangan hilang: anggap normal (tidak memicu)
    st[ok] = sensor_status(tt, door_open=np.zeros(len(tt), bool), t_amb=np.zeros(len(tt)), battery_v=vv)
    return st


def fitur_mote(i, M, nbr_med, gagal):
    T, V = M["temperature"][i], M["voltage"][i]
    ujung = np.arange(JENDELA - 1, min(gagal[i], T.shape[0]), LANGKAH)     # indeks menit akhir jendela
    if len(ujung) == 0:
        return None
    s = ujung - (JENDELA - 1)

    def w(a):
        return swv(a, JENDELA)[s]

    with np.errstate(all="ignore"), __import__("warnings").catch_warnings():
        __import__("warnings").simplefilter("ignore", RuntimeWarning)
        Tw, Vw = w(T), w(V)
        Tf, Vf = ffill(T), ffill(V)
        datar, lomp = panjang_datar(T), lompatan(T)
        selisih = w(T - nbr_med[i])
        f = {
            "t_mean": np.nanmean(Tw, 1), "t_std": np.nanstd(Tw, 1), "t_min": np.nanmin(Tw, 1),
            "t_max": np.nanmax(Tw, 1), "t_akhir": Tf[ujung], "t_tren": Tf[ujung] - Tf[s],
            "lompat_maks": np.nanmax(w(lomp), 1), "n_lompat_5c": np.nansum(w(lomp) > LOMPAT_C, 1),
            "datar_maks": np.nanmax(w(datar), 1), "missing": np.isnan(Tw).mean(1),
            "bacaan_per_menit": np.nanmean(w(M["n_bacaan"][i]), 1),
            "v_mean": np.nanmean(Vw, 1), "v_min": np.nanmin(Vw, 1), "v_akhir": Vf[ujung],
            "v_tren": Vf[ujung] - Vf[s],
            "v_turun_6j": Vf[ujung] - Vf[np.maximum(ujung - 360, 0)],
            "v_turun_24j": Vf[ujung] - Vf[np.maximum(ujung - 1440, 0)],
            "h_mean": np.nanmean(w(M["humidity"][i]), 1), "h_std": np.nanstd(w(M["humidity"][i]), 1),
            "cahaya_mean": np.nanmean(w(M["light"][i]), 1),
            "beda_tetangga_mean": np.nanmean(selisih, 1), "beda_tetangga_abs": np.nanmean(np.abs(selisih), 1),
        }
    st = skor_v0(T, V)
    f["skor_v0"] = swv(st, JENDELA)[s].max(1)
    sisa = gagal[i] - ujung                                      # menit sampai gagal (> 0)
    for h in (H_UTAMA, *H_SEKUNDER):
        f[f"y_{h}j"] = (sisa <= h * 60).astype(np.int8)
    f["menit_ke_gagal"] = sisa
    f["ujung"] = ujung
    return pd.DataFrame(f)


def split_mote(motes):
    rng = np.random.default_rng(SPLIT_SEED)
    acak = list(rng.permutation(motes))
    n_tr = round(len(acak) * SPLIT_PORSI[0])
    n_va = round(len(acak) * SPLIT_PORSI[1])
    return {m: ("train" if k < n_tr else "val" if k < n_tr + n_va else "test") for k, m in enumerate(acak)}


def bangun():
    t0 = time.perf_counter()
    df = sd.muat_mentah()
    ev = sd.kejadian_gagal(df, H_UTAMA)
    pm = sd.per_menit(df)
    t_muat = time.perf_counter() - t0
    menit, motes, M, gagal = susun_matriks(pm, ev)
    nb = tetangga(motes, sd.muat_lokasi())
    with np.errstate(all="ignore"), __import__("warnings").catch_warnings():
        __import__("warnings").simplefilter("ignore", RuntimeWarning)
        nbr_med = np.nanmedian(M["temperature"][nb], axis=1)          # [mote, menit]
    split = split_mote(motes)
    parts = []
    for i, m in enumerate(motes):
        f = fitur_mote(i, M, nbr_med, gagal)
        if f is not None:
            f.insert(0, "moteid", m)
            f.insert(1, "split", split[m])
            f["waktu_ujung"] = menit[f["ujung"].to_numpy()]
            parts.append(f)
    out = pd.concat(parts, ignore_index=True)
    out.to_parquet(OUT, index=False)
    return out, {"muat_s": t_muat, "fitur_s": time.perf_counter() - t0 - t_muat, "n_jendela": len(out),
                 "split_mote": {s: sorted(k for k, v in split.items() if v == s) for s in ("train", "val", "test")}}


if __name__ == "__main__":
    out, info = bangun()
    print(info["n_jendela"], "jendela", {k: round(v, 1) for k, v in info.items() if k.endswith("_s")})
    print(out.groupby("split")[["y_24j", "y_6j", "y_1j"]].agg(["mean", "size"]).round(4).to_string())
