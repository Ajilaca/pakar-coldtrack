"""Ablation study R2 (context-r2 baris 75).

A. Multi-task vs single-task  -- apakah backbone bersama merugikan?
B. Fine-tuning vs dari nol     -- apakah pretraining memberi nilai tambah?

Menjalankan: python -m ml.ablation
PERINGATAN: 5 konfigurasi x 30 epoch, perkiraan 2-3 jam di CPU.
"""

import json
import time

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from ml.evaluate import SENTINEL, TEMP_IDX, compute_metrics
from ml.model import ColdTrackGRU
from ml.preprocess.build_windows import FAILURE_CLASSES
from ml.scaler import apply_scaler, fit_scaler

TRAIN_PATH = "data/processed/windows/windows_train.npz"
VAL_PATH = "data/processed/windows/windows_val.npz"
BACKBONE_PATH = "ml/reports/backbone_pretrained.pt"
OUT_PATH = "ml/reports/ablation_results.json"

N_EPOCHS = 30
FREEZE_EPOCHS = 3
BATCH_SIZE = 256
LR_BACKBONE, LR_HEADS = 5e-4, 2e-3

# (nama, bobot loss (forecast, failure, ttb), pakai bobot pretrained)
# Bobot 0 = head itu tidak ikut dilatih sama sekali -> jadi single-task.
KONFIGURASI = [
    ("multitask_finetuned", (30.0, 1.0, 8.0), True),    # acuan utama
    ("multitask_dari_nol",  (30.0, 1.0, 8.0), False),   # Ablation B
    ("single_forecast",     (30.0, 0.0, 0.0), True),    # Ablation A
    ("single_failure",      (0.0,  1.0, 0.0), True),    # Ablation A
    ("single_ttb",          (0.0,  0.0, 8.0), True),    # Ablation A
]


def make_dataset(path, mean, std):
    d = np.load(path)
    X = torch.tensor(apply_scaler(d['X'], mean, std))
    yf = torch.tensor((d['y_forecast'] - mean[TEMP_IDX]) / std[TEMP_IDX], dtype=torch.float32)
    ym = torch.tensor(d['y_mode'], dtype=torch.int64)
    raw = d['y_ttb']
    mask = torch.tensor((raw != SENTINEL).astype(np.float32))
    yttb = torch.tensor(np.log1p(np.where(raw == SENTINEL, 0.0, raw)), dtype=torch.float32)
    return TensorDataset(X, yf, ym, yttb, mask)


def latih(bobot, pakai_pretrained, train_loader, val_loader, class_weights):
    torch.manual_seed(42)      # seed sama untuk semua konfigurasi -> perbandingan adil
    model = ColdTrackGRU()
    if pakai_pretrained:
        model.load_state_dict(torch.load(BACKBONE_PATH))

    head_params = (list(model.head_forecast.parameters())
                   + list(model.head_failure.parameters())
                   + list(model.head_ttb.parameters()))
    opt = torch.optim.AdamW([
        {'params': model.gru.parameters(), 'lr': LR_BACKBONE},
        {'params': head_params, 'lr': LR_HEADS},
    ])
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=N_EPOCHS)

    l_fc = nn.L1Loss()
    l_ce = nn.CrossEntropyLoss(weight=class_weights)
    l_ttb = nn.HuberLoss(reduction='none')

    def hitung_loss(batch):
        X, yf, ym, yttb, mask = batch
        f, c, t = model(X)
        loss = 0.0
        if bobot[0]:
            loss = loss + bobot[0] * l_fc(f, yf)
        if bobot[1]:
            loss = loss + bobot[1] * l_ce(c, ym)
        if bobot[2]:
            loss = loss + bobot[2] * ((l_ttb(t, yttb) * mask).sum() / mask.sum().clamp(min=1))
        return loss

    best_val, best_state = float('inf'), None
    for epoch in range(1, N_EPOCHS + 1):
        for nama, p in model.gru.named_parameters():
            if '_l0' in nama:
                p.requires_grad = epoch > FREEZE_EPOCHS

        model.train(True)
        for batch in train_loader:
            loss = hitung_loss(batch)
            opt.zero_grad()
            loss.backward()
            opt.step()
        sched.step()

        model.train(False)
        total, n = 0.0, 0
        with torch.no_grad():
            for batch in val_loader:
                total += hitung_loss(batch).item() * batch[0].size(0)
                n += batch[0].size(0)
        val = total / n
        if val < best_val:
            best_val, best_state = val, {k: v.clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    return model


def main():
    mean, std = fit_scaler(np.load(TRAIN_PATH)['X'])
    train_loader = DataLoader(make_dataset(TRAIN_PATH, mean, std), batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(make_dataset(VAL_PATH, mean, std), batch_size=512)

    y_mode = np.load(TRAIN_PATH)['y_mode']
    counts = np.bincount(y_mode, minlength=len(FAILURE_CLASSES))
    class_weights = torch.tensor(
        np.sqrt(len(y_mode) / (len(FAILURE_CLASSES) * counts)), dtype=torch.float32)

    hasil = {}
    for i, (nama, bobot, pakai_pretrained) in enumerate(KONFIGURASI, 1):
        t0 = time.time()
        print(f"[{i}/{len(KONFIGURASI)}] {nama} ...", flush=True)

        model = latih(bobot, pakai_pretrained, train_loader, val_loader, class_weights)
        m = compute_metrics(model, VAL_PATH, mean, std)
        m['_menit'] = round((time.time() - t0) / 60, 1)
        m['_bobot_loss'] = list(bobot)
        m['_pakai_pretrained'] = pakai_pretrained
        hasil[nama] = m

        print(f"    fc_t30={m['forecast_t30_mae_c']:.3f}C  F1={m['macro_f1']:.4f}  "
              f"acc={m['akurasi']:.4f}  ttb={m['ttb_mae_menit']:.2f}m  "
              f"prauc={m['anomali_pr_auc']:.4f}  ({m['_menit']} menit)", flush=True)

        # simpan tiap selesai satu konfigurasi -- kalau mati di tengah, hasil sebelumnya aman
        with open(OUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(hasil, f, indent=2, ensure_ascii=False)

    print(f"\nTersimpan: {OUT_PATH}")
    print("\nCatatan: metrik single-task hanya sahih untuk head yang dilatih di konfigurasi itu; "
          "head lain outputnya acak dan harus diabaikan.")


if __name__ == "__main__":
    main()
