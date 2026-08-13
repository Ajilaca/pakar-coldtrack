"""Hasilkan artefak laporan R2: metrics.json + grafik evaluasi.

Semua metrik dihitung di split TEST -- split yang tidak pernah dipakai untuk
mengambil keputusan apa pun. Angka val lebih bagus tapi optimistis, karena
arsitektur dan hiperparameter dipilih berdasarkan val.

Menjalankan: python -m ml.make_reports
"""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from matplotlib.colors import LinearSegmentedColormap
from sklearn.metrics import confusion_matrix

from ml.evaluate import SENTINEL, TARGETS, compute_metrics
from ml.model import ColdTrackGRU
from ml.preprocess.build_windows import FAILURE_CLASSES
from ml.scaler import apply_scaler, load_scaler

TEST_PATH = "data/processed/windows/windows_test.npz"
VAL_PATH = "data/processed/windows/windows_val.npz"
CHECKPOINT = "ml/reports/coldtrack_finetuned.pt"
SCALER_PATH = "ml/reports/scaler_finetune.npz"
BASELINE_PATH = "ml/reports/baseline_metrics.json"
ABLATION_PATH = "ml/reports/ablation_results.json"

METRICS_OUT = "ml/reports/metrics.json"
CM_OUT = "ml/reports/confusion_matrix.png"
TTB_OUT = "ml/reports/ttb_by_horizon.png"

# Palet tervalidasi (lihat catatan di model_card.md)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_MUTED = "#52514e"
SERIES_1 = "#2a78d6"
BLUE_RAMP = ["#fcfcfb", "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
             "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95",
             "#104281", "#0d366b"]

HORIZON_BUCKETS = [(0, 10), (10, 30), (30, 60), (60, 120), (120, 400)]


def load_model():
    mean, std = load_scaler(SCALER_PATH)
    model = ColdTrackGRU()
    model.load_state_dict(torch.load(CHECKPOINT))
    model.eval()
    return model, mean, std


def predict(model, path, mean, std):
    d = np.load(path)
    X = torch.tensor(apply_scaler(d["X"], mean, std))
    with torch.no_grad():
        forecast, logits, ttb_log = model(X)
    return d, logits.argmax(dim=1).numpy(), np.expm1(ttb_log.numpy())


def ttb_by_horizon(d, ttb_pred):
    """MAE TTB dipecah per rentang -- angka tunggal menyembunyikan fakta bahwa
    model akurat saat breach dekat dan buruk saat jauh."""
    msk = d["y_ttb"] != SENTINEL
    aktual, prediksi = d["y_ttb"][msk], ttb_pred[msk]

    hasil = []
    for lo, hi in HORIZON_BUCKETS:
        sel = (aktual >= lo) & (aktual < hi)
        if sel.sum() < 5:
            continue
        hasil.append({
            "rentang_menit": f"{lo}-{hi}",
            "n": int(sel.sum()),
            "mae_menit": float(np.abs(prediksi[sel] - aktual[sel]).mean()),
        })
    return hasil


def plot_confusion(d, pred, macro_f1):
    cm = confusion_matrix(d["y_mode"], pred, labels=range(len(FAILURE_CLASSES)))
    cm_norm = cm / cm.sum(axis=1, keepdims=True).clip(min=1)
    cmap = LinearSegmentedColormap.from_list("blue_seq", BLUE_RAMP)

    fig, ax = plt.subplots(figsize=(7.5, 6.4))
    ax.imshow(cm_norm, cmap=cmap, vmin=0, vmax=1)

    n = len(FAILURE_CLASSES)
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(FAILURE_CLASSES, rotation=45, ha="right", fontsize=9, color=INK_MUTED)
    ax.set_yticklabels(FAILURE_CLASSES, fontsize=9, color=INK_MUTED)

    for i in range(n):
        for j in range(n):
            if cm[i, j] == 0:
                continue
            ax.text(j, i, f"{cm_norm[i, j] * 100:.0f}%\n{cm[i, j]}",
                    ha="center", va="center", fontsize=8,
                    color="#ffffff" if cm_norm[i, j] > 0.55 else INK)

    ax.set_xlabel("Prediksi model", fontsize=10, color=INK)
    ax.set_ylabel("Kelas sebenarnya", fontsize=10, color=INK)
    ax.set_title(f"Confusion matrix — split test (Macro F1 = {macro_f1:.3f})",
                 fontsize=11, color=INK, pad=12)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)

    fig.tight_layout()
    fig.savefig(CM_OUT, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print(f"Tersimpan: {CM_OUT}")


def plot_ttb(horizon):
    label = [h["rentang_menit"] for h in horizon]
    mae = [h["mae_menit"] for h in horizon]
    n = [h["n"] for h in horizon]

    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    ax.bar(range(len(mae)), mae, width=0.62, color=SERIES_1)

    ax.axhline(TARGETS["ttb_mae_menit"][1], color=INK_MUTED, linestyle="--", linewidth=1)
    ax.text(len(mae) - 0.4, TARGETS["ttb_mae_menit"][1] + 2, "target 8 menit",
            fontsize=8, color=INK_MUTED, ha="right")

    for i, (v, cnt) in enumerate(zip(mae, n)):
        ax.text(i, v + 2, f"{v:.1f}", ha="center", fontsize=9, color=INK)
        ax.text(i, -8, f"n={cnt}", ha="center", fontsize=8, color=INK_MUTED)

    ax.set_xticks(range(len(label)))
    ax.set_xticklabels(label, fontsize=9, color=INK_MUTED)
    ax.set_xlabel("Time-to-Breach sebenarnya (menit)", fontsize=10, color=INK, labelpad=16)
    ax.set_ylabel("MAE prediksi (menit)", fontsize=10, color=INK)
    ax.set_title("Akurasi Time-to-Breach makin buruk seiring jaraknya — split test",
                 fontsize=11, color=INK, pad=12)

    ax.grid(axis="y", color="#e8e7e3", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#e8e7e3")

    fig.tight_layout()
    fig.savefig(TTB_OUT, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print(f"Tersimpan: {TTB_OUT}")


def main():
    model, mean, std = load_model()

    m_test = compute_metrics(model, TEST_PATH, mean, std)
    m_val = compute_metrics(model, VAL_PATH, mean, std)
    d_test, pred_test, ttb_test = predict(model, TEST_PATH, mean, std)
    horizon = ttb_by_horizon(d_test, ttb_test)

    status = {}
    for nama, (arah, batas) in TARGETS.items():
        nilai = m_test[nama]
        status[nama] = {
            "nilai": round(nilai, 4),
            "target": f"{arah}{batas}",
            "lolos": bool(nilai < batas if arah == "<" else nilai > batas),
        }

    laporan = {
        "model": "GRU fusion (2 lapis, hidden 64) + statistik ringkasan jendela, 3 kepala",
        "parameter": sum(p.numel() for p in model.parameters()),
        "dataset": "v4_seed1000_700trips",
        "dilatih_dari_nol": True,
        "metrik_test": {k: round(v, 4) for k, v in m_test.items()},
        "metrik_val_pembanding": {k: round(v, 4) for k, v in m_val.items()},
        "vs_target": status,
        "ttb_per_horizon_test": horizon,
        "catatan": [
            "Metrik utama dari split TEST. Split val dipakai untuk memilih arsitektur dan hiperparameter, jadi angkanya optimistis.",
            "Split test hanya berisi 10,6% jendela breach vs 22,6% di val, dengan median TTB 63 vs 10 menit. Split distratifikasi per failure_mode tapi tidak per kejadian breach, sehingga statistik TTB antar split tidak sebanding.",
            "MAE TTB keseluruhan menyembunyikan fakta penting: model akurat saat breach dekat (0-10 menit) dan tidak akurat saat jauh. Lihat ttb_per_horizon_test.",
        ],
    }

    try:
        with open(BASELINE_PATH, encoding="utf-8") as f:
            laporan["baseline_pembanding_val"] = json.load(f)
    except OSError:
        pass
    try:
        with open(ABLATION_PATH, encoding="utf-8") as f:
            laporan["ablation_val"] = json.load(f)
    except OSError:
        pass

    with open(METRICS_OUT, "w", encoding="utf-8") as f:
        json.dump(laporan, f, indent=2, ensure_ascii=False)
    print(f"Tersimpan: {METRICS_OUT}")

    plot_confusion(d_test, pred_test, m_test["macro_f1"])
    plot_ttb(horizon)

    print("\nMetrik test vs target:")
    for nama, s in status.items():
        print(f"  {nama:22s} {s['nilai']:8.3f}  target {s['target']:<7} {'LOLOS' if s['lolos'] else 'belum'}")


if __name__ == "__main__":
    main()
