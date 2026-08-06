"""Fase 4 R2 -- fine-tuning Tahap 2: load backbone pretrained, aktifkan 3 head,
latih di data cold chain asli (v3).

Menjalankan: python -m ml.finetune
"""

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

from ml.model import ColdTrackGRU
from ml.preprocess.build_windows import FAILURE_CLASSES
from ml.scaler import fit_scaler, apply_scaler, save_scaler

TRAIN_PATH = "data/processed/windows/windows_train.npz"
VAL_PATH = "data/processed/windows/windows_val.npz"
BACKBONE_PATH = "ml/reports/backbone_pretrained.pt"
OUT_PATH = "ml/reports/coldtrack_finetuned.pt"
SCALER_PATH = "ml/reports/scaler_finetune.npz"

BATCH_SIZE = 256
N_EPOCHS = 25
FREEZE_EPOCHS = 3
LR_BACKBONE = 3e-4      # pelan -- backbone sudah punya bekal dari pretraining
LR_HEADS = 2e-3         # cepat -- 3 head masih acak, perlu mengejar
LOSS_WEIGHTS = {'forecast': 1.0, 'failure': 1.0, 'ttb': 0.8}

TEMP_IDX = 0
SENTINEL = 999.0


def make_dataset(path, mean, std):
    data = np.load(path)
    X = torch.tensor(apply_scaler(data['X'], mean, std))
    yf = torch.tensor((data['y_forecast'] - mean[TEMP_IDX]) / std[TEMP_IDX], dtype=torch.float32)
    ym = torch.tensor(data['y_mode'], dtype=torch.int64)

    raw_ttb = data['y_ttb']
    # sentinel 999 ("tidak pernah breach") di-mask dari loss, sesuai context-r1 langkah 6
    mask = torch.tensor((raw_ttb != SENTINEL).astype(np.float32))
    yttb = torch.tensor(np.log1p(np.where(raw_ttb == SENTINEL, 0.0, raw_ttb)), dtype=torch.float32)

    return TensorDataset(X, yf, ym, yttb, mask)


def compute_class_weights(path):
    y_mode = np.load(path)['y_mode']
    counts = np.bincount(y_mode, minlength=len(FAILURE_CLASSES))
    weights = np.sqrt(len(y_mode) / (len(FAILURE_CLASSES) * counts))
    return torch.tensor(weights, dtype=torch.float32)


def set_layer0_frozen(model, frozen):
    for name, param in model.gru.named_parameters():
        if '_l0' in name:
            param.requires_grad = not frozen


def run_epoch(model, loader, loss_fns, optimizer=None):
    is_train = optimizer is not None
    model.train(is_train)

    sums = {'total': 0.0, 'forecast': 0.0, 'failure': 0.0, 'ttb': 0.0}
    n_samples, n_correct = 0, 0

    for X_batch, yf_batch, ym_batch, yttb_batch, mask_batch in loader:
        forecast, failure_logits, ttb = model(X_batch)

        loss_forecast = loss_fns['forecast'](forecast, yf_batch)
        loss_failure = loss_fns['failure'](failure_logits, ym_batch)
        # rata-rata hanya atas baris yang TIDAK bersentinel
        loss_ttb = (loss_fns['ttb'](ttb, yttb_batch) * mask_batch).sum() / mask_batch.sum().clamp(min=1)

        loss = (
            LOSS_WEIGHTS['forecast'] * loss_forecast
            + LOSS_WEIGHTS['failure'] * loss_failure
            + LOSS_WEIGHTS['ttb'] * loss_ttb
        )

        if is_train:
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        bs = X_batch.size(0)
        sums['total'] += loss.item() * bs
        sums['forecast'] += loss_forecast.item() * bs
        sums['failure'] += loss_failure.item() * bs
        sums['ttb'] += loss_ttb.item() * bs
        n_correct += (failure_logits.argmax(dim=1) == ym_batch).sum().item()
        n_samples += bs

    out = {k: v / n_samples for k, v in sums.items()}
    out['acc'] = n_correct / n_samples
    return out


def main():
    mean, std = fit_scaler(np.load(TRAIN_PATH)['X'])
    save_scaler(SCALER_PATH, mean, std)

    train_loader = DataLoader(make_dataset(TRAIN_PATH, mean, std), batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(make_dataset(VAL_PATH, mean, std), batch_size=BATCH_SIZE, shuffle=False)

    model = ColdTrackGRU()
    model.load_state_dict(torch.load(BACKBONE_PATH))
    print(f"Bobot pretrained dimuat dari {BACKBONE_PATH}\n")

    head_params = (
        list(model.head_forecast.parameters())
        + list(model.head_failure.parameters())
        + list(model.head_ttb.parameters())
    )
    optimizer = torch.optim.AdamW([
        {'params': model.gru.parameters(), 'lr': LR_BACKBONE},
        {'params': head_params, 'lr': LR_HEADS},
    ])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=N_EPOCHS)

    loss_fns = {
        'forecast': nn.L1Loss(),
        'failure': nn.CrossEntropyLoss(weight=compute_class_weights(TRAIN_PATH)),
        'ttb': nn.HuberLoss(reduction='none'),      # 'none' supaya bisa di-mask manual
    }

    best_val, best_state = float('inf'), None

    for epoch in range(1, N_EPOCHS + 1):
        frozen = epoch <= FREEZE_EPOCHS
        set_layer0_frozen(model, frozen)
        status = "BEKU" if frozen else "buka semua"

        train_m = run_epoch(model, train_loader, loss_fns, optimizer)
        val_m = run_epoch(model, val_loader, loss_fns, optimizer=None)
        scheduler.step()

        tanda = ""
        if val_m['total'] < best_val:
            best_val = val_m['total']
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            tanda = "  <- terbaik"

        print(
            f"epoch {epoch:2d}/{N_EPOCHS} [{status:10s}]  "
            f"train={train_m['total']:.3f}  val={val_m['total']:.3f}  "
            f"(fc={val_m['forecast']:.3f} ce={val_m['failure']:.3f} ttb={val_m['ttb']:.3f} acc={val_m['acc']:.3f})"
            f"{tanda}"
        )

    model.load_state_dict(best_state)     # pakai epoch terbaik, bukan epoch terakhir
    torch.save(model.state_dict(), OUT_PATH)
    print(f"\nModel fine-tuned tersimpan (val terbaik={best_val:.3f}): {OUT_PATH}")


if __name__ == "__main__":
    main()
