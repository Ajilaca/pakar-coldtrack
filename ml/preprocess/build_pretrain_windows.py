"""Fase 3 R2 -- siapkan data pretraining head-1 dari dataset suhu publik (IoT India, R1).

Menjalankan: python -m ml.preprocess.build_pretrain_windows
"""

import os

import numpy as np
import pandas as pd

from ml.tests.test_data_contract import FEATURE_COLUMNS

RAW_PATH = "data/raw/iot_temp/IOT-temp.csv"
OUT_DIR = "data/processed/windows"

WINDOW_SIZE = 60
HORIZONS = [15, 30, 60]
MAX_GAP_FILL = 5                              # menit -- bolong sependek ini ditambal
MIN_CHUNK_LEN = WINDOW_SIZE + max(HORIZONS)   # 120 menit, syarat minimal 1 jendela

# Kolom di FEATURE_COLUMNS yang punya sinyal ASLI dari dataset publik ini.
# 9 kolom sisanya diisi nol -- tidak ada info pintu/kecepatan/dll di data ini.
REAL_FEATURE_IDX = {
    'temp_c': FEATURE_COLUMNS.index('temp_c'),
    'delta_temp': FEATURE_COLUMNS.index('delta_temp'),
    'hour_of_day': FEATURE_COLUMNS.index('hour_of_day'),
}


def load_continuous_chunks():
    df_raw = pd.read_csv(RAW_PATH)
    df_raw = df_raw[df_raw['out/in'] == 'Out'].copy()
    df_raw['noted_date'] = pd.to_datetime(df_raw['noted_date'], format='%d-%m-%Y %H:%M')

    temp = df_raw.groupby('noted_date')['temp'].mean()   # rata-rata kalau ada duplikat menit

    full_range = pd.date_range(temp.index.min(), temp.index.max(), freq='1min')
    temp = temp.reindex(full_range)
    temp = temp.ffill(limit=MAX_GAP_FILL)

    df = pd.DataFrame({
        'temp_c': temp,
        'delta_temp': temp.diff(),
        'hour_of_day': temp.index.hour,
    })

    is_valid = df['temp_c'].notna()
    df['chunk_id'] = (~is_valid).cumsum().where(is_valid)

    chunks = []
    for _, g in df.dropna(subset=['chunk_id']).groupby('chunk_id'):
        if len(g) >= MIN_CHUNK_LEN:
            chunks.append(g)
    return chunks


def build_windows_for_chunk(g):
    n = len(g)
    max_h = max(HORIZONS)
    max_start = n - WINDOW_SIZE - max_h
    if max_start < 0:
        return None

    full = np.zeros((n, len(FEATURE_COLUMNS)), dtype=np.float32)
    full[:, REAL_FEATURE_IDX['temp_c']] = g['temp_c'].to_numpy()
    full[:, REAL_FEATURE_IDX['delta_temp']] = g['delta_temp'].to_numpy()
    full[:, REAL_FEATURE_IDX['hour_of_day']] = g['hour_of_day'].to_numpy()

    temp = g['temp_c'].to_numpy()

    X_list, yf_list = [], []
    for start in range(max_start + 1):
        end = start + WINDOW_SIZE
        t = end - 1
        window = full[start:end]
        forecast_targets = [temp[t + h] for h in HORIZONS]

        if np.isnan(window).any() or np.isnan(forecast_targets).any():
            continue

        X_list.append(window)
        yf_list.append(forecast_targets)

    if not X_list:
        return None
    return np.stack(X_list), np.array(yf_list, dtype=np.float32)


def main():
    chunks = load_continuous_chunks()
    print(f"Jumlah chunk kontinu (>= {MIN_CHUNK_LEN} menit): {len(chunks)}")

    rng = np.random.default_rng(42)
    val_flags = rng.permutation(len(chunks)) < max(1, int(len(chunks) * 0.15))

    X_train_list, yf_train_list = [], []
    X_val_list, yf_val_list = [], []

    for is_val, g in zip(val_flags, chunks):
        result = build_windows_for_chunk(g)
        if result is None:
            continue
        X, yf = result
        (X_val_list if is_val else X_train_list).append(X)
        (yf_val_list if is_val else yf_train_list).append(yf)

    X_train, yf_train = np.concatenate(X_train_list), np.concatenate(yf_train_list)
    X_val, yf_val = np.concatenate(X_val_list), np.concatenate(yf_val_list)

    os.makedirs(OUT_DIR, exist_ok=True)
    np.savez_compressed(os.path.join(OUT_DIR, 'pretrain_train.npz'), X=X_train, y_forecast=yf_train)
    np.savez_compressed(os.path.join(OUT_DIR, 'pretrain_val.npz'), X=X_val, y_forecast=yf_val)

    print(f"train: {X_train.shape[0]:,} jendela")
    print(f"val  : {X_val.shape[0]:,} jendela")


if __name__ == "__main__":
    main()
