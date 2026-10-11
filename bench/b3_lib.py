"""Pustaka B3 (latih ulang sesuai PRD): pelatih GRU yang bisa disetel + diagnosis per kelas.

Pelatih di sini adalah generalisasi bench.train_lib.train_gru: dengan argumen bawaan hasilnya
setara konfigurasi ml/finetune.py (bobot loss 30/1/8, LR 5e-4/2e-3, class weight sqrt, freeze 3
epoch, cosine 30 epoch, hidden 64 x 2 lapis, dropout 0,2). Benchmark W1 tetap memakai
train_lib.train_gru supaya angka B2 tidak berubah.

Data selalu resident di device (tanpa DataLoader): untuk B3 yang dinilai adalah model, dan mode
ini ~2x lebih cepat di GPU (temuan W1 B2). Split test tidak pernah dimuat di sini.
"""

import time
from dataclasses import asdict, dataclass

import numpy as np
import torch
from torch import nn

from bench.train_lib import _sync, seed_all


@dataclass
class GruCfg:
    hidden_size: int = 64
    num_layers: int = 2
    dropout: float = 0.2
    lr_backbone: float = 5e-4
    lr_heads: float = 2e-3
    w_forecast: float = 30.0
    w_failure: float = 1.0
    w_ttb: float = 8.0
    class_weight_power: float = 0.5      # 0,5 = sqrt (asli); 0 = tanpa bobot kelas; 1 = inverse frekuensi
    freeze_epochs: int = 3
    n_epochs: int = 30
    batch_size: int = 256
    weight_decay: float = 0.01           # bawaan AdamW, sama dengan ml/finetune.py
    label_smoothing: float = 0.0
    pakai_statistik: bool = True         # False = ablation: jalur statistik ringkasan diganti nol

    def as_dict(self):
        return asdict(self)


def _tanpa_stat_cls():
    from ml.model import ColdTrackGRU

    class ColdTrackGRUTanpaStat(ColdTrackGRU):
        """Ablation W4: statistik ringkasan diganti nol (dimensi kepala tetap sama)."""

        def aggregate(self, x):
            return torch.zeros(x.shape[0], x.shape[2] * self.N_STATS, device=x.device, dtype=x.dtype)

    return ColdTrackGRUTanpaStat


def class_weights(y_mode, n_classes, power):
    counts = np.bincount(y_mode, minlength=n_classes).astype(np.float64)
    w = (len(y_mode) / (n_classes * counts)) ** power
    return torch.tensor(w, dtype=torch.float32)


def train(data, cfg: GruCfg, seed, device, log=None):
    from ml.model import ColdTrackGRU
    from ml.preprocess.build_windows import FAILURE_CLASSES

    dev = torch.device(device)
    ColdTrackGRUTanpaStat = _tanpa_stat_cls()
    seed_all(seed)
    g = torch.Generator().manual_seed(seed)
    tr = [t.to(dev) for t in data["train"].tensors]
    va = [t.to(dev) for t in data["val"].tensors]
    y_tr = data["train"].tensors[2].numpy()

    kelas = ColdTrackGRU if cfg.pakai_statistik else ColdTrackGRUTanpaStat
    model = kelas(hidden_size=cfg.hidden_size, num_layers=cfg.num_layers, dropout=cfg.dropout).to(dev)
    heads = (list(model.head_forecast.parameters()) + list(model.head_failure.parameters())
             + list(model.head_ttb.parameters()))
    opt = torch.optim.AdamW([{"params": model.gru.parameters(), "lr": cfg.lr_backbone},
                             {"params": heads, "lr": cfg.lr_heads}], weight_decay=cfg.weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=cfg.n_epochs)
    l_fc = nn.L1Loss()
    l_ce = nn.CrossEntropyLoss(weight=class_weights(y_tr, len(FAILURE_CLASSES), cfg.class_weight_power).to(dev),
                               label_smoothing=cfg.label_smoothing)
    l_ttb = nn.HuberLoss(reduction="none")

    def loss_fn(b):
        X, yf, ym, yttb, mask = b
        f, c, t = model(X)
        return (cfg.w_forecast * l_fc(f, yf) + cfg.w_failure * l_ce(c, ym)
                + cfg.w_ttb * (l_ttb(t, yttb) * mask).sum() / mask.sum().clamp(min=1))

    best, best_state, best_ep, hist = float("inf"), None, None, []
    _sync(dev)
    t0 = time.perf_counter()
    n = len(tr[0])
    for ep in range(1, cfg.n_epochs + 1):
        for name, p in model.gru.named_parameters():
            if "_l0" in name:
                p.requires_grad = ep > cfg.freeze_epochs
        model.train(True)
        perm = torch.randperm(n, generator=g).to(dev)
        for i in range(0, n, cfg.batch_size):
            idx = perm[i:i + cfg.batch_size]
            loss = loss_fn([t[idx] for t in tr])
            opt.zero_grad()
            loss.backward()
            opt.step()
        sched.step()
        model.train(False)
        with torch.no_grad():
            vs = sum(float(loss_fn([t[i:i + 4096] for t in va])) * min(4096, len(va[0]) - i)
                     for i in range(0, len(va[0]), 4096)) / len(va[0])
        hist.append(vs)
        if vs < best:
            best, best_ep = vs, ep
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        if log:
            log(f"    epoch {ep:2d} val={vs:.4f}")
    _sync(dev)
    model.load_state_dict(best_state)
    return model, {"detik_latih": time.perf_counter() - t0, "epoch_terbaik": best_ep, "val_loss_terbaik": best,
                   "riwayat_val_loss": hist}


@torch.no_grad()
def predict(model, data, device, split="val", bs=4096):
    from bench.train_lib import split_path
    from ml.scaler import apply_scaler

    d = np.load(split_path(split))
    X = torch.tensor(apply_scaler(d["X"], data["mean"], data["std"]))
    model.eval()
    outs = [[], [], []]
    for i in range(0, len(X), bs):
        for k, o in enumerate(model(X[i:i + bs].to(device))):
            outs[k].append(o.float().cpu())
    return [torch.cat(o) for o in outs], d


def metrik_lengkap(forecast, logits, ttb_log, d, mean, std):
    """Metrik resmi (ml.evaluate) + rincian per kelas + matriks kebingungan."""
    from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

    from ml.evaluate import metrics_from_outputs
    from ml.preprocess.build_windows import FAILURE_CLASSES

    m = metrics_from_outputs(forecast, logits, ttb_log, d, mean, std)
    pred = logits.argmax(1).numpy()
    p, r, f, s = precision_recall_fscore_support(d["y_mode"], pred, labels=range(len(FAILURE_CLASSES)),
                                                 zero_division=0)
    m["per_kelas"] = {c: {"presisi": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "n": int(s[i])}
                      for i, c in enumerate(FAILURE_CLASSES)}
    m["confusion"] = confusion_matrix(d["y_mode"], pred, labels=range(len(FAILURE_CLASSES))).tolist()
    return m


def menit_sejak_onset(split="val"):
    """Untuk tiap jendela split (urutan SAMA dengan ml/preprocess/build_windows.main), kembalikan
    menit sejak onset anomali pada menit "sekarang" (akhir jendela); NaN untuk jendela A0.

    Merekonstruksi loop build_windows_for_trip (termasuk jendela yang dibuang karena NaN) lalu
    memverifikasi jumlah jendela terhadap npz.
    """
    import pandas as pd

    from bench.train_lib import split_path
    from ml.preprocess.build_windows import DATA_PATH, HORIZONS, WINDOW_SIZE
    from ml.tests.test_data_contract import FEATURE_COLUMNS

    df = pd.read_parquet(DATA_PATH)
    out = []
    for _, g in df.groupby("trip_id"):
        if g["split"].iloc[0] != split:
            continue
        g = g.sort_values("minute").reset_index(drop=True)
        feats = g[FEATURE_COLUMNS].values.astype(np.float32)
        temp = g["temp_c"].values.astype(np.float32)
        mode = g["failure_mode"].values
        onset = g["onset_minute"].iloc[0]
        minute = g["minute"].values
        max_start = len(g) - WINDOW_SIZE - max(HORIZONS)
        if max_start < 0:
            continue
        for start in range(max_start + 1):
            t = start + WINDOW_SIZE - 1
            if np.isnan(feats[start:start + WINDOW_SIZE]).any() or np.isnan([temp[t + h] for h in HORIZONS]).any():
                continue
            if mode[t] == "A0":
                out.append(np.nan)
            else:
                # A8: anomali sejak menit 0 (onset_minute kosong) -> dihitung dari awal trip
                out.append(float(minute[t] - (0 if pd.isna(onset) else onset)))
    out = np.array(out)
    n_npz = len(np.load(split_path(split))["y_mode"])
    if len(out) != n_npz:
        raise RuntimeError(f"rekonstruksi onset tidak cocok: {len(out)} vs {n_npz} jendela")
    return out
