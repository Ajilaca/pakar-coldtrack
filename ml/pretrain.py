"""Fase 3 R2 -- pretraining Tahap 1: backbone GRU + head-1 (forecast) saja.

Korpus: Intel Berkeley Lab Data (1,3 juta jendela) -- menggantikan korpus lama
IOT-temp India (5.630 jendela) yang terbukti tidak memberi manfaat transfer
pada ablation B.

Menjalankan: python -m ml.pretrain
"""

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from ml.model import ColdTrackGRU
from ml.scaler import apply_scaler, fit_scaler, save_scaler

TRAIN_PATH = "data/processed/windows/pretrain_train.npz"
VAL_PATH = "data/processed/windows/pretrain_val.npz"
OUT_PATH = "ml/reports/backbone_pretrained.pt"
SCALER_PATH = "ml/reports/scaler_pretrain.npz"

BATCH_SIZE = 256
N_EPOCHS = 10           # korpus 207x lebih besar -> butuh jauh lebih sedikit epoch
LR = 1e-3
MAX_WINDOWS = 200_000   # ambil sampel; jendela bertetangga tumpang tindih 59/60 menit
TEMP_IDX = 0            # posisi kolom temp_c di FEATURE_COLUMNS


def subsample(path):
    """Muat npz lalu ambil sampel acak. Dimuat SEKALI saja -- korpus penuh ~3,3 GB."""
    data = np.load(path)
    X, y = data['X'], data['y_forecast']
    if MAX_WINDOWS and len(X) > MAX_WINDOWS:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(X), MAX_WINDOWS, replace=False)
        X, y = X[idx], y[idx]
    return X, y


def to_dataset(X_raw, y_raw, mean, std):
    X = torch.tensor(apply_scaler(X_raw, mean, std))
    y = torch.tensor((y_raw - mean[TEMP_IDX]) / std[TEMP_IDX], dtype=torch.float32)
    return TensorDataset(X, y)


def run_epoch(model, loader, loss_fn, optimizer=None):
    is_train = optimizer is not None
    model.train(is_train)

    total_loss, n_samples = 0.0, 0
    for X_batch, y_batch in loader:
        forecast, _, _ = model(X_batch)
        loss = loss_fn(forecast, y_batch)

        if is_train:
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        total_loss += loss.item() * X_batch.size(0)
        n_samples += X_batch.size(0)

    return total_loss / n_samples


def main():
    print("Memuat korpus pretraining (butuh 1-3 menit, harap tunggu)...", flush=True)

    X_tr, y_tr = subsample(TRAIN_PATH)
    print(f"  train: {X_tr.shape[0]:,} jendela", flush=True)

    X_va, y_va = subsample(VAL_PATH)
    print(f"  val  : {X_va.shape[0]:,} jendela", flush=True)

    # Scaler dihitung dari sampel yang sama -- cukup akurat untuk mean/std,
    # sekaligus menghindari memuat ulang korpus penuh (3,3 GB) untuk kedua kalinya.
    mean, std = fit_scaler(X_tr)
    save_scaler(SCALER_PATH, mean, std)
    print("Scaler siap. Mulai melatih...\n", flush=True)

    train_loader = DataLoader(to_dataset(X_tr, y_tr, mean, std), batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(to_dataset(X_va, y_va, mean, std), batch_size=BATCH_SIZE, shuffle=False)

    model = ColdTrackGRU()
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR)
    loss_fn = nn.L1Loss()

    for epoch in range(1, N_EPOCHS + 1):
        train_loss = run_epoch(model, train_loader, loss_fn, optimizer)
        val_loss = run_epoch(model, val_loader, loss_fn, optimizer=None)
        print(
            f"epoch {epoch:2d}/{N_EPOCHS}  train_mae={train_loss:.4f}  "
            f"val_mae={val_loss:.4f}  (skala ternormalisasi)",
            flush=True,
        )

    torch.save(model.state_dict(), OUT_PATH)
    print(f"\nBackbone tersimpan: {OUT_PATH}")


if __name__ == "__main__":
    main()
