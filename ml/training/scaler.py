"""Normalisasi fitur: ubah tiap kolom ke skala seragam (mean 0, std 1).

Tanpa ini, solar_radiation (std ~270) menenggelamkan door_open (std ~0.06),
padahal door_open justru sinyal penting untuk deteksi anomali.
"""

import numpy as np


def fit_scaler(X):
    """X: (n_windows, 60, n_fitur). Return (mean, std) per fitur."""
    flat = X.reshape(-1, X.shape[-1])
    mean = flat.mean(axis=0)
    std = flat.std(axis=0)
    std[std < 1e-6] = 1.0        # hindari bagi nol untuk fitur yang konstan
    return mean.astype(np.float32), std.astype(np.float32)


def apply_scaler(X, mean, std):
    return ((X - mean) / std).astype(np.float32)


def save_scaler(path, mean, std):
    np.savez(path, mean=mean, std=std)


def load_scaler(path):
    d = np.load(path)
    return d['mean'], d['std']
