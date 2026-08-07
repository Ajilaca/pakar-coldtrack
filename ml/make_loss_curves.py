"""Grafik perbandingan kurva loss: fine-tuning vs dilatih dari nol.

Bukti visual untuk ablation B (context-r2 baris 67). Melatih dua konfigurasi
dengan resep identik -- satu memuat bobot GRU hasil pretraining, satu dari nol --
lalu memplot kurva train & val loss keduanya.

Menjalankan: python -m ml.make_loss_curves
PERINGATAN: 2 konfigurasi x 30 epoch, perkiraan 70 menit di CPU.

Untuk menggambar ulang tanpa melatih lagi (riwayat sudah tersimpan):
    python -c "import json; from ml.make_loss_curves import plot; \
               plot(json.load(open('ml/reports/loss_history.json')))"
"""

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from ml.finetune import (BATCH_SIZE, FREEZE_EPOCHS, LOSS_WEIGHTS, LR_BACKBONE,
                         LR_HEADS, TRAIN_PATH, VAL_PATH, compute_class_weights,
                         make_dataset, set_layer0_frozen)
from ml.model import ColdTrackGRU
from ml.scaler import fit_scaler

BACKBONE_PATH = "ml/reports/backbone_pretrained.pt"
HISTORY_OUT = "ml/reports/loss_history.json"
PLOT_OUT = "ml/reports/loss_curves.png"

N_EPOCHS = 30

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_MUTED = "#52514e"
GRID = "#e8e7e3"
SERIES = {"dari_nol": "#2a78d6", "fine_tuned": "#eb6834"}
LABEL = {"fine_tuned": "Fine-tuning (dari backbone pretrained)",
         "dari_nol": "Dilatih dari nol"}


def train_with_history(pakai_pretrained, train_loader, val_loader, class_weights, tag):
    torch.manual_seed(42)
    model = ColdTrackGRU()

    if pakai_pretrained:
        # Backbone disimpan dari arsitektur sebelum fusion, jadi hanya bobot GRU
        # yang dipindahkan -- kepala memang sengaja dibuat baru saat fine-tuning.
        sd = torch.load(BACKBONE_PATH)
        gru_sd = {k[len("gru."):]: v for k, v in sd.items() if k.startswith("gru.")}
        model.gru.load_state_dict(gru_sd)

    head_params = (list(model.head_forecast.parameters())
                   + list(model.head_failure.parameters())
                   + list(model.head_ttb.parameters()))
    opt = torch.optim.AdamW([
        {"params": model.gru.parameters(), "lr": LR_BACKBONE},
        {"params": head_params, "lr": LR_HEADS},
    ])
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=N_EPOCHS)

    l_fc = nn.L1Loss()
    l_ce = nn.CrossEntropyLoss(weight=class_weights)
    l_ttb = nn.HuberLoss(reduction="none")

    def hitung(batch):
        X, yf, ym, yttb, mask = batch
        f, c, t = model(X)
        return (LOSS_WEIGHTS["forecast"] * l_fc(f, yf)
                + LOSS_WEIGHTS["failure"] * l_ce(c, ym)
                + LOSS_WEIGHTS["ttb"] * ((l_ttb(t, yttb) * mask).sum() / mask.sum().clamp(min=1)))

    riwayat = {"train": [], "val": []}
    for epoch in range(1, N_EPOCHS + 1):
        set_layer0_frozen(model, epoch <= FREEZE_EPOCHS)

        model.train(True)
        total, n = 0.0, 0
        for batch in train_loader:
            loss = hitung(batch)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item() * batch[0].size(0)
            n += batch[0].size(0)
        riwayat["train"].append(total / n)
        sched.step()

        model.train(False)
        total, n = 0.0, 0
        with torch.no_grad():
            for batch in val_loader:
                total += hitung(batch).item() * batch[0].size(0)
                n += batch[0].size(0)
        riwayat["val"].append(total / n)

        print(f"  [{tag}] epoch {epoch:2d}/{N_EPOCHS}  "
              f"train={riwayat['train'][-1]:.3f}  val={riwayat['val'][-1]:.3f}", flush=True)

    return riwayat


def plot(riwayat):
    """Gambar kurva. Bisa dipanggil terpisah dari loss_history.json tanpa melatih ulang."""
    n_epoch = len(riwayat["dari_nol"]["val"])
    epochs = range(1, n_epoch + 1)

    fig, ax = plt.subplots(figsize=(8.4, 5.0))

    for tag in ["fine_tuned", "dari_nol"]:
        # Val = garis penuh (yang menentukan), train = putus-putus (pendukung).
        # Perbedaan arah keduanya inilah bukti overfitting pada varian pretrained.
        ax.plot(epochs, riwayat[tag]["val"], color=SERIES[tag], linewidth=2, label=LABEL[tag])
        ax.plot(epochs, riwayat[tag]["train"], color=SERIES[tag], linewidth=1.2,
                linestyle="--", alpha=0.5)

        ax.annotate(f"val {riwayat[tag]['val'][-1]:.2f}",
                    (n_epoch, riwayat[tag]["val"][-1]), xytext=(6, 0),
                    textcoords="offset points", fontsize=8.5, color=INK, va="center")
        ax.annotate(f"train {riwayat[tag]['train'][-1]:.2f}",
                    (n_epoch, riwayat[tag]["train"][-1]), xytext=(6, 0),
                    textcoords="offset points", fontsize=8.5, color=INK_MUTED, va="center")

    ax.axvline(FREEZE_EPOCHS + 0.5, color=GRID, linewidth=1)
    ax.text(FREEZE_EPOCHS + 0.8, ax.get_ylim()[1] * 0.95,
            "lapis GRU-1 dibuka", fontsize=8, color=INK_MUTED)

    ax.set_xlim(0.5, n_epoch + 3.5)     # ruang untuk label di ujung kanan
    ax.set_xlabel("Epoch", fontsize=10, color=INK)
    ax.set_ylabel("Loss (gabungan 3 kepala)", fontsize=10, color=INK)
    ax.set_title("Pretraining pada korpus miskin fitur justru memperburuk generalisasi",
                 fontsize=11, color=INK, pad=12)

    ax.legend(frameon=False, fontsize=9, labelcolor=INK_MUTED, loc="upper right")
    ax.text(0.02, 0.04, "garis putus-putus = train    garis penuh = validation",
            transform=ax.transAxes, fontsize=8, color=INK_MUTED)

    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, colors=INK_MUTED)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)

    fig.tight_layout()
    fig.savefig(PLOT_OUT, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print(f"\nTersimpan: {PLOT_OUT}")


def main():
    mean, std = fit_scaler(np.load(TRAIN_PATH)["X"])
    train_loader = DataLoader(make_dataset(TRAIN_PATH, mean, std), batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(make_dataset(VAL_PATH, mean, std), batch_size=512)
    class_weights = compute_class_weights(TRAIN_PATH)

    riwayat = {}
    for tag, pakai in [("dari_nol", False), ("fine_tuned", True)]:
        print(f"\n=== {tag} ===", flush=True)
        riwayat[tag] = train_with_history(pakai, train_loader, val_loader, class_weights, tag)

    with open(HISTORY_OUT, "w", encoding="utf-8") as f:
        json.dump(riwayat, f, indent=2)
    print(f"Tersimpan: {HISTORY_OUT}")

    plot(riwayat)


if __name__ == "__main__":
    main()
