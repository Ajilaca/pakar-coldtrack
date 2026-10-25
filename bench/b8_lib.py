"""Pustaka B8: definisi label v5 (A1/A7 sementara) dan fitur konteks trip.

Label v5 hanya mengubah A1 (pintu) dan A7 (kejut ambien); kelas lain sama dengan
ml/preprocess/build_windows.py. Di dataset v4 kedua peristiwa itu sementara (A1: door_open = 1
selama 20 menit, A7: speed_kmh = 0 selama 30 menit) tetapi failure_mode bertahan sampai akhir trip
(bench/results/g16-gpu/B3/label_check.json). Pada v5, jendela yang berakhir di menit t diberi label
kelasnya bila onset <= t <= akhir_label, dengan

    akhir_label = max(akhir_kejadian + 59, menit_pulih)

- akhir_kejadian + 59: menit kejadian masih ada di jendela 60 menit;
- menit_pulih: menit pertama setelah kejadian saat temp_true_c kembali <= rata-rata 15 menit sebelum
  onset + TOL_PULIH_C, dibatasi PULIH_MAKS_MENIT. temp_true_c hanya dipakai untuk LABEL, tidak
  pernah sebagai fitur.

Di luar rentang itu jendela A1/A7 berlabel A0. Ini perubahan DEFINISI label, bukan perbaikan model:
metrik v5 tidak sebanding langsung dengan metrik label lama dan harus dilaporkan berdampingan.

Fitur konteks (KONTEKS) dihitung kausal dari temp_c sejak awal trip sampai menit t, setelah celah
diisi nilai terakhir (sama dengan mesin fisika). Semuanya dapat dihitung dari riwayat 240 menit
yang sudah disimpan worker armada dan rencana chip.

Urutan jendela identik dengan build_windows (diverifikasi terhadap y_mode di npz). Split test
hanya dibangun lewat bench/b10_test_once.py (izinkan_test=True, tidak disimpan ke disk).
"""

import numpy as np

KONTEKS = [
    "menit_trip",            # menit sejak trip dimulai
    "suhu_awal_muat",        # rata-rata temp_c 5 menit pertama trip
    "kini_minus_awal",       # temp_c sekarang - suhu_awal_muat
    "tren_240",              # temp_c sekarang - temp_c 239 menit lalu (atau awal trip)
    "rata240_minus_rata60",  # rata-rata 240 menit terakhir - rata-rata 60 menit terakhir
    "kemiringan_240",        # kemiringan regresi linear temp_c 240 menit terakhir (C/menit)
]
TOL_PULIH_C = 0.15        # 3 x simpangan derau simulator (sigma 0,05 C)
PULIH_MAKS_MENIT = 120
BASIS_MENIT = 15
SEMENTARA = {"A1": "door_open", "A7": "speed_kmh"}


def _ffill(x):
    x = np.asarray(x, dtype=np.float64).copy()
    ok = ~np.isnan(x)
    if not ok.any():
        return np.zeros_like(x)
    idx = np.where(ok, np.arange(len(x)), 0)
    np.maximum.accumulate(idx, out=idx)
    x = x[idx]
    x[:np.argmax(ok)] = x[np.argmax(ok)]
    return x


def konteks_trip(temp_c):
    """Fitur konteks untuk SETIAP menit trip, shape (n, len(KONTEKS)). Kausal."""
    y = _ffill(temp_c)
    n = len(y)
    i = np.arange(n, dtype=np.float64)
    cy = np.concatenate([[0.0], np.cumsum(y)])
    ciy = np.concatenate([[0.0], np.cumsum(i * y)])
    a = np.maximum(0, np.arange(n) - 239)
    a60 = np.maximum(0, np.arange(n) - 59)
    b = np.arange(n) + 1
    m = (b - a).astype(np.float64)
    sy = cy[b] - cy[a]
    sxy = ciy[b] - ciy[a] - a * sy                    # x = i - a
    sx = m * (m - 1) / 2
    sxx = (m - 1) * m * (2 * m - 1) / 6
    den = m * sxx - sx ** 2
    slope = np.where(den > 0, (m * sxy - sx * sy) / np.where(den > 0, den, 1), 0.0)
    awal = y[:5].mean()
    out = np.column_stack([
        i,
        np.full(n, awal),
        y - awal,
        y - y[a],
        sy / m - (cy[b] - cy[a60]) / (b - a60),
        slope,
    ])
    return out.astype(np.float32)


def akhir_label_sementara(g, kelas):
    """Menit terakhir jendela yang masih berlabel `kelas` pada trip A1/A7 (lihat docstring modul)."""
    kolom = SEMENTARA[kelas]
    aktif = g[kolom].to_numpy() >= 0.5 if kelas == "A1" else g[kolom].to_numpy() <= 0.0
    onset = int(g["onset_minute"].iloc[0])
    menit_aktif = np.where(aktif & (np.arange(len(g)) >= onset))[0]
    akhir = int(menit_aktif.max()) if len(menit_aktif) else onset
    tt = g["temp_true_c"].to_numpy()
    basis = np.nanmean(tt[max(0, onset - BASIS_MENIT):onset]) if onset > 0 else tt[0]
    sesudah = np.arange(akhir + 1, min(len(g), akhir + 1 + PULIH_MAKS_MENIT))
    pulih_idx = sesudah[tt[sesudah] <= basis + TOL_PULIH_C]
    pulih = int(pulih_idx[0]) if len(pulih_idx) else akhir + PULIH_MAKS_MENIT
    return max(akhir + 59, pulih), {"onset": onset, "akhir_kejadian": akhir, "pulih": pulih}


def path_npz(split, izinkan_test=False):
    from bench.common import ROOT
    from bench.train_lib import split_path

    if split == "test":
        if not izinkan_test:
            raise PermissionError("split test hanya lewat bench/b10_test_once.py (sekali per model, tercatat)")
        return ROOT / "data" / "processed" / "windows" / "windows_test.npz"
    return split_path(split)


def bangun(split, izinkan_test=False):
    """Rekonstruksi jendela build_windows untuk `split`: label lama, label v5, konteks, menit, trip."""
    import pandas as pd

    from bench.common import DATA_PATH
    from ml.preprocess.build_windows import (
        CLASS_TO_IDX,
        HORIZONS,
        MODE_MAPPING,
        WINDOW_SIZE,
    )
    from ml.tests.test_data_contract import FEATURE_COLUMNS

    ref_path = path_npz(split, izinkan_test)
    df = pd.read_parquet(DATA_PATH)
    y_lama, y_baru, ctx, menit, trip, info = [], [], [], [], [], {}
    for tid, g in df.groupby("trip_id"):
        if g["split"].iloc[0] != split:
            continue
        g = g.sort_values("minute").reset_index(drop=True)
        feats = g[FEATURE_COLUMNS].values.astype(np.float32)
        temp = g["temp_c"].values.astype(np.float32)
        mode = g["failure_mode"].values
        max_start = len(g) - WINDOW_SIZE - max(HORIZONS)
        if max_start < 0:
            continue
        kelas_trip = next((m for m in pd.unique(mode) if m != "A0"), "A0")
        batas = None
        if kelas_trip in SEMENTARA:
            batas, info[int(tid)] = akhir_label_sementara(g, kelas_trip)
        k = konteks_trip(temp)
        for start in range(max_start + 1):
            t = start + WINDOW_SIZE - 1
            if np.isnan(feats[start:start + WINDOW_SIZE]).any() or np.isnan([temp[t + h] for h in HORIZONS]).any():
                continue
            lama = CLASS_TO_IDX[MODE_MAPPING[mode[t]]]
            baru = lama
            if batas is not None and mode[t] == kelas_trip and t > batas:
                baru = CLASS_TO_IDX["A0"]
            y_lama.append(lama)
            y_baru.append(baru)
            ctx.append(k[t])
            menit.append(t)
            trip.append(int(tid))
    y_lama = np.array(y_lama, dtype=np.int64)
    ref = np.load(ref_path)["y_mode"]
    if len(ref) != len(y_lama) or not (ref == y_lama).all():
        raise RuntimeError(f"rekonstruksi jendela {split} tidak cocok dengan npz build_windows")
    return {"y_lama": y_lama, "y_baru": np.array(y_baru, dtype=np.int64), "ctx": np.stack(ctx),
            "menit": np.array(menit), "trip": np.array(trip)}, info


def path_b8(split):
    from bench.common import ROOT

    return ROOT / "data" / "processed" / "windows" / f"b8_{split}.npz"


def muat(split):
    """Bangun sekali lalu simpan di samping npz build_windows (data/processed/windows/ tidak dikomit)."""
    p = path_b8(split)
    if not p.exists():
        d, _ = bangun(split)
        np.savez_compressed(p, **d)
    return dict(np.load(p))
