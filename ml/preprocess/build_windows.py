"""Fase 1 R2 — sliding window 60 menit x 12 fitur dari data trip R1.

Menjalankan: python ml/preprocess/build_windows.py
"""

import os

import numpy as np
import pandas as pd

from ml.tests.test_data_contract import FEATURE_COLUMNS

DATA_PATH = "data/processed/v4_seed1000_700trips.parquet"
OUT_DIR = "data/processed/windows"

WINDOW_SIZE = 60
HORIZONS = [15, 30, 60]  # menit ke depan untuk head-1 (forecast)

# Pemetaan 9 mode anomali R1 -> 7 kelas head-2, sesuai saran context-r2 baris 59:
# A2+A4 (sama-sama drift pelan) -> "degradasi_bertahap"
# A5+A6 (sama-sama masalah sensor, bukan masalah kargo) -> "masalah_sensor"
MODE_MAPPING = {
    'A0': 'A0', 'A1': 'A1', 'A2': 'degradasi_bertahap', 'A3': 'A3',
    'A4': 'degradasi_bertahap', 'A5': 'masalah_sensor', 'A6': 'masalah_sensor',
    'A7': 'A7', 'A8': 'A8',
}
FAILURE_CLASSES = ['A0', 'A1', 'A3', 'A7', 'A8', 'degradasi_bertahap', 'masalah_sensor']
CLASS_TO_IDX = {name: i for i, name in enumerate(FAILURE_CLASSES)}

# Kolom yang harus dihitung ulang per jendela, bukan diambil apa adanya dari parquet.
# reefer_duration_min di dataset dihitung sejak awal perjalanan (nilainya bisa mencapai 479),
# sedangkan backend menghitungnya sejak awal jendela 60 menit (maksimal 60). Perbedaan itu
# membuat model menerima nilai di luar distribusi latihnya setiap kali dipakai sungguhan.
IDX_REEFER_ON = FEATURE_COLUMNS.index('reefer_on')
IDX_REEFER_DURATION = FEATURE_COLUMNS.index('reefer_duration_min')


def hitung_ulang_reefer_duration(window):
    """Hitung ulang reefer_duration_min relatif terhadap awal jendela.

    Menyamakan definisi dengan backend (backend/app/preprocess.py), yang memotong
    payload ke 60 bacaan terakhir LEBIH DULU, baru menghitung fitur turunannya.
    """
    window = window.copy()
    durasi, berjalan = [], 0
    for menyala in window[:, IDX_REEFER_ON]:
        berjalan = berjalan + 1 if menyala >= 0.5 else 0
        durasi.append(berjalan)
    window[:, IDX_REEFER_DURATION] = np.array(durasi, dtype=np.float32)
    return window


def build_windows_for_trip(g):
    """g = potongan dataframe satu trip_id. Return dict array atau None kalau trip terlalu pendek."""
    g = g.sort_values('minute').reset_index(drop=True)
    n = len(g)
    max_h = max(HORIZONS)
    max_start = n - WINDOW_SIZE - max_h
    if max_start < 0:
        return None

    feats = g[FEATURE_COLUMNS].values.astype(np.float32)
    temp = g['temp_c'].values.astype(np.float32)
    ttb = g['time_to_breach'].values.astype(np.float32)
    failure_modes = g['failure_mode'].values

    X_list, yf_list, ym_list, yttb_list = [], [], [], []

    for start in range(max_start + 1):
        end = start + WINDOW_SIZE
        t = end - 1  # "sekarang" = menit terakhir di jendela

        window = hitung_ulang_reefer_duration(feats[start:end])
        forecast_targets = [temp[t + h] for h in HORIZONS]

        if np.isnan(window).any() or np.isnan(forecast_targets).any():
            continue  # buang jendela yang datanya bolong

        X_list.append(window)
        yf_list.append(forecast_targets)
        ym_list.append(CLASS_TO_IDX[MODE_MAPPING[failure_modes[t]]])
        yttb_list.append(ttb[t])

    if not X_list:
        return None

    return {
        'X': np.stack(X_list),                              # (n_windows, 60, 12)
        'y_forecast': np.array(yf_list, dtype=np.float32),   # (n_windows, 3)
        'y_mode': np.array(ym_list, dtype=np.int64),         # (n_windows,)
        'y_ttb': np.array(yttb_list, dtype=np.float32),      # (n_windows,)
    }


def main():
    df = pd.read_parquet(DATA_PATH)

    per_split = {'train': [], 'val': [], 'test': []}
    n_trip_terbuang = 0

    for trip_id, g in df.groupby('trip_id'):
        result = build_windows_for_trip(g)
        if result is None:
            n_trip_terbuang += 1
            continue
        split = g['split'].iloc[0]
        per_split[split].append(result)

    os.makedirs(OUT_DIR, exist_ok=True)

    for split, chunks in per_split.items():
        X = np.concatenate([c['X'] for c in chunks])
        y_forecast = np.concatenate([c['y_forecast'] for c in chunks])
        y_mode = np.concatenate([c['y_mode'] for c in chunks])
        y_ttb = np.concatenate([c['y_ttb'] for c in chunks])

        out_path = os.path.join(OUT_DIR, f'windows_{split}.npz')
        np.savez_compressed(
            out_path, X=X, y_forecast=y_forecast, y_mode=y_mode, y_ttb=y_ttb
        )
        print(f"{split:5s}: {X.shape[0]:>7,} jendela  ->  {out_path}")

    print(f"\nTrip yang dibuang (terlalu pendek untuk 1 jendela pun): {n_trip_terbuang}")


if __name__ == "__main__":
    main()
