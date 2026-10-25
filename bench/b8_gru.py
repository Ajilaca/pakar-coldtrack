"""Pelatih GRU B8: arsitektur v3 (ml/model.ColdTrackGRU) + fitur konteks trip opsional di kepala.

Fitur konteks (bench/b8_lib.KONTEKS, dinormalisasi dengan statistik train) disambung ke vektor fusi
[h_GRU, 72 statistik jendela] sebelum ketiga kepala; dengan 0 fitur konteks modelnya sama persis
dengan ColdTrackGRU. Loop latih mengikuti bench/b3_lib.train (AdamW dua grup LR, cosine, class weight
berpangkat, label smoothing, pilih epoch val terbaik). Split test tidak dimuat.
"""

import time

import numpy as np
import torch
from torch import nn

from bench.train_lib import seed_all


def kelas_model():
    from ml.model import ColdTrackGRU

    class ColdTrackGRUKonteks(ColdTrackGRU):
        def __init__(self, n_konteks=0, **kw):
            super().__init__(**kw)
            fused = self.head_forecast.in_features + n_konteks
            self.head_forecast = nn.Linear(fused, 3)
            self.head_failure = nn.Linear(fused, self.head_failure.out_features)
            self.head_ttb = nn.Linear(fused, 1)

        def forward(self, x, ctx):
            _, h_n = self.gru(x)
            fused = torch.cat([self.dropout(h_n[-1]), self.aggregate(x), ctx], dim=1)
            return self.head_forecast(fused), self.head_failure(fused), self.head_ttb(fused).squeeze(-1)

    return ColdTrackGRUKonteks


def siapkan(b8_tr, b8_va, konteks, label="y_baru"):
    from ml import finetune as ft
    from ml.scaler import fit_scaler

    mean, std = fit_scaler(np.load(ft.TRAIN_PATH)["X"])
    ctx_mean = b8_tr["ctx"].mean(0).astype(np.float32)
    ctx_std = np.maximum(b8_tr["ctx"].std(0), 1e-6).astype(np.float32)
    out = {"mean": mean, "std": std, "ctx_mean": ctx_mean, "ctx_std": ctx_std, "konteks": konteks}
    for nama, path, b8 in (("train", ft.TRAIN_PATH, b8_tr), ("val", ft.VAL_PATH, b8_va)):
        X, yf, _, yttb, mask = ft.make_dataset(path, mean, std).tensors
        ym = torch.tensor(b8[label], dtype=torch.int64)
        ctx = ((b8["ctx"] - ctx_mean) / ctx_std).astype(np.float32) if konteks else np.zeros((len(ym), 0), np.float32)
        out[nama] = [X, yf, ym, yttb, mask, torch.tensor(ctx)]
        out[f"npz_{nama}"] = {**dict(np.load(path)), "y_mode": b8[label]}
    return out


def latih(data, cfg, seed, log=None):
    from bench.b3_lib import class_weights
    from ml.preprocess.build_windows import FAILURE_CLASSES

    seed_all(seed)
    g = torch.Generator().manual_seed(seed)
    tr, va = data["train"], data["val"]
    model = kelas_model()(n_konteks=tr[5].shape[1], hidden_size=cfg["hidden_size"],
                          num_layers=cfg["num_layers"], dropout=cfg["dropout"])
    heads = (list(model.head_forecast.parameters()) + list(model.head_failure.parameters())
             + list(model.head_ttb.parameters()))
    opt = torch.optim.AdamW([{"params": model.gru.parameters(), "lr": cfg["lr_backbone"]},
                             {"params": heads, "lr": cfg["lr_heads"]}], weight_decay=cfg["weight_decay"])
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=cfg["n_epochs"])
    l_fc = nn.L1Loss()
    l_ce = nn.CrossEntropyLoss(weight=class_weights(tr[2].numpy(), len(FAILURE_CLASSES), cfg["class_weight_power"]),
                               label_smoothing=cfg["label_smoothing"])
    l_ttb = nn.HuberLoss(reduction="none")

    def loss_fn(b):
        X, yf, ym, yttb, mask, ctx = b
        f, c, t = model(X, ctx)
        return (cfg["w_forecast"] * l_fc(f, yf) + cfg["w_failure"] * l_ce(c, ym)
                + cfg["w_ttb"] * (l_ttb(t, yttb) * mask).sum() / mask.sum().clamp(min=1))

    best, best_state, best_ep, hist = float("inf"), None, None, []
    t0 = time.perf_counter()
    n = len(tr[0])
    for ep in range(1, cfg["n_epochs"] + 1):
        te = time.perf_counter()
        for name, p in model.gru.named_parameters():
            if "_l0" in name:
                p.requires_grad = ep > cfg["freeze_epochs"]
        model.train(True)
        perm = torch.randperm(n, generator=g)
        for i in range(0, n, cfg["batch_size"]):
            idx = perm[i:i + cfg["batch_size"]]
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
            log(f"    epoch {ep:2d} val={vs:.4f} ({time.perf_counter() - te:.0f} s)", flush=True)
        if ep - best_ep >= cfg.get("patience", cfg["n_epochs"]):
            break           # berhenti dini; jadwal cosine tetap T_max = n_epochs
    model.load_state_dict(best_state)
    return model, {"detik_latih": time.perf_counter() - t0, "epoch_terbaik": best_ep, "val_loss_terbaik": best,
                   "riwayat_val_loss": hist}


@torch.no_grad()
def evaluasi(model, data, bs=4096):
    from bench.b8_label_konteks import metrik_kelas
    from ml.evaluate import metrics_from_outputs

    va = data["val"]
    model.eval()
    outs = [[], [], []]
    for i in range(0, len(va[0]), bs):
        for k, o in enumerate(model(va[0][i:i + bs], va[5][i:i + bs])):
            outs[k].append(o.float())
    forecast, logits, ttb = (torch.cat(o) for o in outs)
    m = metrics_from_outputs(forecast, logits, ttb, data["npz_val"], data["mean"], data["std"])
    m.update({k: v for k, v in metrik_kelas(data["npz_val"]["y_mode"], torch.softmax(logits, 1).numpy()).items()
              if k == "per_kelas"})
    return m
