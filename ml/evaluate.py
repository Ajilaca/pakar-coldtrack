"""Perhitungan metrik resmi R2 -- satu sumber kebenaran, dipakai ablation & evaluasi akhir."""

import numpy as np
import torch
from sklearn.metrics import average_precision_score, f1_score

from ml.scaler import apply_scaler

SENTINEL = 999.0
TEMP_IDX = 0        # posisi temp_c di FEATURE_COLUMNS

TARGETS = {
    'forecast_t30_mae_c': ('<', 0.8),
    'macro_f1': ('>', 0.80),
    'ttb_mae_menit': ('<', 8.0),
    'anomali_pr_auc': ('>', 0.85),
}


def compute_metrics(model, npz_path, mean, std):
    """Kembalikan metrik dalam satuan ASLI (derajat C, menit) -- bukan skala ternormalisasi."""
    d = np.load(npz_path)
    X = torch.tensor(apply_scaler(d['X'], mean, std))

    model.eval()
    with torch.no_grad():
        forecast, logits, ttb_log = model(X)

    forecast_c = forecast.numpy() * std[TEMP_IDX] + mean[TEMP_IDX]
    pred = logits.argmax(dim=1).numpy()
    prob_anomali = 1 - torch.softmax(logits, dim=1).numpy()[:, 0]

    # TTB hanya dinilai pada jendela yang benar-benar menuju breach;
    # jendela bersentinel di-mask saat training, jadi tidak adil ikut dinilai.
    msk = d['y_ttb'] != SENTINEL
    ttb_pred = np.expm1(ttb_log.numpy())

    return {
        'forecast_t15_mae_c': float(np.abs(forecast_c[:, 0] - d['y_forecast'][:, 0]).mean()),
        'forecast_t30_mae_c': float(np.abs(forecast_c[:, 1] - d['y_forecast'][:, 1]).mean()),
        'forecast_t60_mae_c': float(np.abs(forecast_c[:, 2] - d['y_forecast'][:, 2]).mean()),
        'macro_f1': float(f1_score(d['y_mode'], pred, average='macro')),
        'akurasi': float((pred == d['y_mode']).mean()),
        'ttb_mae_menit': float(np.abs(ttb_pred[msk] - d['y_ttb'][msk]).mean()),
        'anomali_pr_auc': float(average_precision_score((d['y_mode'] != 0).astype(int), prob_anomali)),
    }


def print_vs_target(metrics, judul=""):
    if judul:
        print(judul)
    for nama, (arah, batas) in TARGETS.items():
        nilai = metrics[nama]
        lolos = nilai < batas if arah == '<' else nilai > batas
        print(f"  {nama:22s} {nilai:8.3f}  target {arah}{batas:<6} {'LOLOS' if lolos else 'belum'}")
