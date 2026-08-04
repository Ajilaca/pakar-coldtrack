"""Fase 3 R2 -- pretraining Tahap 1: backbone GRU + head-1 (forecast) saja.

Menjalankan: python -m ml.pretrain
"""

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

from ml.model import ColdTrackGRU
from ml.scaler import fit_scaler, apply_scaler, save_scaler

TRAIN_PATH = "data/processed/windows/pretrain_train.npz"
VAL_PATH = "data/processed/windows/pretrain_val.npz"
OUT_PATH = "ml/reports/backbone_pretrained.pt"
SCALER_PATH = "ml/reports/scaler_pretrain.npz"

BATCH_SIZE = 256
N_EPOCHS = 30
LR = 1e-3
TEMP_IDX = 0        # posisi kolom temp_c di FEATURE_COLUMNS


def make_dataset(path, mean, std):
    data = np.load(path)
    X = torch.tensor(apply_scaler(data['X'], mean, std))
    # target forecast juga dinormalisasi, pakai statistik kolom temp_c
    y = torch.tensor((data['y_forecast'] - mean[TEMP_IDX]) / std[TEMP_IDX], dtype=torch.float32)
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
    mean, std = fit_scaler(np.load(TRAIN_PATH)['X'])
    save_scaler(SCALER_PATH, mean, std)

    train_loader = DataLoader(make_dataset(TRAIN_PATH, mean, std), batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(make_dataset(VAL_PATH, mean, std), batch_size=BATCH_SIZE, shuffle=False)

    model = ColdTrackGRU()
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR)
    loss_fn = nn.L1Loss()

    for epoch in range(1, N_EPOCHS + 1):
        train_loss = run_epoch(model, train_loader, loss_fn, optimizer)
        val_loss = run_epoch(model, val_loader, loss_fn, optimizer=None)
        print(f"epoch {epoch:2d}/{N_EPOCHS}  train_mae={train_loss:.4f}  val_mae={val_loss:.4f}  (skala ternormalisasi)")

    torch.save(model.state_dict(), OUT_PATH)
    print(f"\nBackbone tersimpan: {OUT_PATH}")


if __name__ == "__main__":
    main()
