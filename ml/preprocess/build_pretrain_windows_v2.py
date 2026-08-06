"""Fase 3 R2 (v2) -- korpus pretraining dari Intel Berkeley Lab Data.

Menggantikan korpus lama (IOT-temp India) yang terbukti tidak memberi manfaat
transfer (lihat ablation B): korpus itu cuma mengisi 3 dari 12 fitur dan
ukurannya 14x lebih kecil dari data fine-tuning.

Intel Lab punya suhu DAN kelembapan (4 dari 12 fitur), 1,89 juta baris bersih
dari 53 sensor, plus derau sensor nyata (18,5% outlier -- lihat dataset_card.md).

Menjalankan: python -m ml.preprocess.build_pretrain_windows_v2
"""

import os

import numpy as np
import pandas as pd

from ml.tests.test_data_contract import FEATURE_COLUMNS

RAW_PATH = "data/raw/intel_lab/data.txt"
OUT_DIR = "data/processed/windows"

WINDOW_SIZE = 60
HORIZONS = [15, 30, 60]
MAX_GAP_FILL = 5
MIN_CHUNK_LEN = WINDOW_SIZE + max(HORIZONS)

# Batas wajar untuk membuang outlier ekstrem (temuan EDA R1 di dataset_card.md:
# 17,7% data di luar rentang fisik, termasuk -38,4 C dan 385,6 C)
TEMP_RANGE = (0.0, 50.0)
HUMID_RANGE = (0.0, 100.0)
MOTE_RANGE = (1, 54)          # moteid di luar ini = bit error transmisi

# Kolom FEATURE_COLUMNS yang punya sinyal ASLI dari dataset ini.
# 8 kolom sisanya (pintu, reefer, kecepatan, dll) diisi nol -- Intel Lab
# adalah sensor ruangan, tidak punya konteks kendaraan.
REAL_IDX = {nama: FEATURE_COLUMNS.index(nama)
            for nama in ['temp_c', 'delta_temp', 'humidity', 'hour_of_day']}


def load_clean():
    cols = ['date', 'time', 'epoch', 'moteid', 'temperature', 'humidity', 'light', 'voltage']
    df = pd.read_csv(RAW_PATH, sep=' ', names=cols, header=None, on_bad_lines='skip')

    for c in ['moteid', 'temperature', 'humidity']:
        df[c] = pd.to_numeric(df[c], errors='coerce')

    n_awal = len(df)
    df = df[
        df.temperature.between(*TEMP_RANGE)
        & df.humidity.between(*HUMID_RANGE)
        & df.moteid.between(*MOTE_RANGE)
    ]
    print(f"Outlier dibuang: {n_awal - len(df):,} dari {n_awal:,} ({(n_awal-len(df))/n_awal*100:.1f}%)")

    df['ts'] = pd.to_datetime(df['date'] + ' ' + df['time'], errors='coerce')
    return df.dropna(subset=['ts'])


def continuous_chunks(df):
    """Pecah tiap sensor jadi potongan waktu yang rapat (bolong <= 5 menit)."""
    chunks = []
    for _, g in df.groupby('moteid'):
        s = g.set_index('ts')[['temperature', 'humidity']].resample('1min').mean()
        s = s.ffill(limit=MAX_GAP_FILL)

        valid = s.temperature.notna()
        chunk_id = (~valid).cumsum().where(valid)

        for _, c in s.dropna(subset=['temperature']).groupby(chunk_id):
            if len(c) >= MIN_CHUNK_LEN:
                chunks.append(c)
    return chunks


def build_windows(chunk):
    n = len(chunk)
    max_start = n - WINDOW_SIZE - max(HORIZONS)
    if max_start < 0:
        return None

    temp = chunk['temperature'].to_numpy(dtype=np.float32)
    humid = chunk['humidity'].to_numpy(dtype=np.float32)

    full = np.zeros((n, len(FEATURE_COLUMNS)), dtype=np.float32)
    full[:, REAL_IDX['temp_c']] = temp
    full[:, REAL_IDX['delta_temp']] = np.diff(temp, prepend=temp[0])
    full[:, REAL_IDX['humidity']] = humid
    full[:, REAL_IDX['hour_of_day']] = chunk.index.hour

    X, yf = [], []
    for start in range(max_start + 1):
        end = start + WINDOW_SIZE
        t = end - 1
        target = [temp[t + h] for h in HORIZONS]
        X.append(full[start:end])
        yf.append(target)

    return np.stack(X), np.array(yf, dtype=np.float32)


def main():
    df = load_clean()
    chunks = continuous_chunks(df)
    print(f"Chunk kontinu (>= {MIN_CHUNK_LEN} menit): {len(chunks):,}")

    rng = np.random.default_rng(42)
    is_val = rng.permutation(len(chunks)) < int(len(chunks) * 0.15)

    X_tr, yf_tr, X_va, yf_va = [], [], [], []
    for val, chunk in zip(is_val, chunks):
        hasil = build_windows(chunk)
        if hasil is None:
            continue
        X, yf = hasil
        (X_va if val else X_tr).append(X)
        (yf_va if val else yf_tr).append(yf)

    os.makedirs(OUT_DIR, exist_ok=True)
    for nama, Xs, yfs in [('pretrain_train', X_tr, yf_tr), ('pretrain_val', X_va, yf_va)]:
        X, yf = np.concatenate(Xs), np.concatenate(yfs)
        path = os.path.join(OUT_DIR, f'{nama}.npz')
        np.savez_compressed(path, X=X, y_forecast=yf)
        print(f"{nama:14s}: {X.shape[0]:>9,} jendela  ->  {path}")


if __name__ == "__main__":
    main()
