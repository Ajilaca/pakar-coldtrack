"""Pustaka latih bersama untuk B1 (reproduksi) dan W1/W2 (benchmark).

Konfigurasi GRU DIIMPOR dari ml/finetune.py (bobot loss, LR per grup, freeze 3 epoch, cosine,
class weight, pilih epoch val terbaik) -- bukan disalin -- supaya reproduksi tidak diam-diam
menyimpang dari konfigurasi yang divalidasi proposal. Yang ditambahkan hanya: device, seed
eksplisit, AMP opsional, dan pencatatan waktu per komponen.

Konfigurasi XGBoost TTB diimpor dari ml/baselines.py (XGB_PARAMS: 300 pohon, hist) dengan pola
latih ml/export_ttb_xgboost.latih_model (sentinel di-mask, target log1p).

Split test TIDAK pernah dimuat di modul ini.
"""

import os
import random
import time

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from bench.common import ROOT

TRAIN, VAL = "train", "val"


def split_path(split):
    from ml import finetune as ft

    if split == "test":
        raise PermissionError("split test tidak boleh dimuat lewat train_lib (aturan: sekali per model, di akhir)")
    return {TRAIN: ft.TRAIN_PATH, VAL: ft.VAL_PATH}[split]


def ensure_windows():
    """Bangun jendela 60x12 dari parquet v4 bila belum ada. Kembalikan detik yang dipakai (0 bila sudah ada)."""
    os.chdir(ROOT)      # skrip ml/ memakai path relatif terhadap root repo
    if all(os.path.exists(split_path(s)) for s in (TRAIN, VAL)):
        return 0.0
    from ml.preprocess import build_windows

    t0 = time.perf_counter()
    build_windows.main()
    return time.perf_counter() - t0


def seed_all(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)        # juga menyemai semua GPU


def _sync(dev):
    if dev.type == "cuda":
        torch.cuda.synchronize()


# ----------------------------------------------------------------------------- GRU

def prepare_gru_data():
    """Muat + normalisasi jendela train/val (CPU). Kembalikan dict data dan waktu per komponen."""
    from ml import finetune as ft
    from ml.scaler import fit_scaler

    t = {}
    t0 = time.perf_counter()
    X_train = np.load(ft.TRAIN_PATH)["X"]
    t["muat_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    mean, std = fit_scaler(X_train)
    del X_train
    train_ds = ft.make_dataset(ft.TRAIN_PATH, mean, std)
    val_ds = ft.make_dataset(ft.VAL_PATH, mean, std)
    class_w = ft.compute_class_weights(ft.TRAIN_PATH)
    t["praproses_s"] = time.perf_counter() - t0
    return {"train": train_ds, "val": val_ds, "mean": mean, "std": std, "class_w": class_w}, t


def _loss(model, batch, loss_fns, w):
    X, yf, ym, yttb, mask = batch
    forecast, logits, ttb = model(X)
    l_f = loss_fns["forecast"](forecast.float(), yf)
    l_c = loss_fns["failure"](logits.float(), ym)
    l_t = (loss_fns["ttb"](ttb.float(), yttb) * mask).sum() / mask.sum().clamp(min=1)
    return w["forecast"] * l_f + w["failure"] * l_c + w["ttb"] * l_t


def train_gru(data, seed, device, batch_size=None, n_epochs=None, amp=None, num_workers=0,
              pin_memory=False, resident=False, log=print):
    """Latih ColdTrackGRU persis seperti ml.finetune.main, di device mana pun.

    amp: None (fp32) | "bf16" | "fp16" (hanya bermakna di cuda).
    resident: seluruh tensor latih/val dipindah ke device sekali di awal (tanpa DataLoader);
      waktu pemindahan dicatat terpisah sebagai transfer_ke_device_s.
    Kembalikan (model terbaik, riwayat per epoch, ringkasan waktu).
    """
    from ml import finetune as ft
    from ml.model import ColdTrackGRU

    batch_size = batch_size or ft.BATCH_SIZE
    n_epochs = n_epochs or ft.N_EPOCHS
    dev = torch.device(device)
    amp_dtype = {"bf16": torch.bfloat16, "fp16": torch.float16, None: None}[amp]
    if amp_dtype is not None and dev.type != "cuda":
        raise ValueError("AMP hanya diuji di jalur cuda")

    seed_all(seed)
    g = torch.Generator().manual_seed(seed)
    t_transfer = 0.0
    if resident:
        _sync(dev)
        t0 = time.perf_counter()
        tr_t = [t.to(dev) for t in data["train"].tensors]
        va_t = [t.to(dev) for t in data["val"].tensors]
        _sync(dev)
        t_transfer = time.perf_counter() - t0

        def train_batches():
            perm = torch.randperm(len(tr_t[0]), generator=g).to(dev)
            for i in range(0, len(perm), batch_size):
                yield [t[perm[i:i + batch_size]] for t in tr_t]

        def val_batches():
            for i in range(0, len(va_t[0]), batch_size):
                yield [t[i:i + batch_size] for t in va_t]
    else:
        train_loader = DataLoader(data["train"], batch_size=batch_size, shuffle=True, generator=g,
                                  num_workers=num_workers, pin_memory=pin_memory)
        val_loader = DataLoader(data["val"], batch_size=batch_size, shuffle=False,
                                num_workers=num_workers, pin_memory=pin_memory)

        def train_batches():
            return (to_dev(b) for b in train_loader)

        def val_batches():
            return (to_dev(b) for b in val_loader)

    model = ColdTrackGRU().to(dev)
    head_params = (list(model.head_forecast.parameters()) + list(model.head_failure.parameters())
                   + list(model.head_ttb.parameters()))
    opt = torch.optim.AdamW([
        {"params": model.gru.parameters(), "lr": ft.LR_BACKBONE},
        {"params": head_params, "lr": ft.LR_HEADS},
    ])
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=n_epochs)
    loss_fns = {
        "forecast": nn.L1Loss(),
        "failure": nn.CrossEntropyLoss(weight=data["class_w"].to(dev)),
        "ttb": nn.HuberLoss(reduction="none"),
    }
    scaler = torch.amp.GradScaler("cuda", enabled=amp == "fp16")
    nb = pin_memory and dev.type == "cuda"

    def to_dev(batch):
        return [b.to(dev, non_blocking=nb) for b in batch]

    history, best_val, best_state, best_epoch = [], float("inf"), None, None
    if dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    t_total = time.perf_counter()
    for epoch in range(1, n_epochs + 1):
        ft.set_layer0_frozen(model, epoch <= ft.FREEZE_EPOCHS)

        _sync(dev)
        t0 = time.perf_counter()
        model.train(True)
        tr_sum, n = 0.0, 0
        for batch in train_batches():
            with torch.autocast(dev.type, dtype=amp_dtype, enabled=amp_dtype is not None):
                loss = _loss(model, batch, loss_fns, ft.LOSS_WEIGHTS)
            opt.zero_grad()
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            tr_sum += loss.detach() * batch[0].size(0)     # tanpa .item() per batch: tidak memaksa sinkron
            n += batch[0].size(0)
        sched.step()
        _sync(dev)
        t_train = time.perf_counter() - t0

        t0 = time.perf_counter()
        model.train(False)
        va_sum, nv = 0.0, 0
        with torch.no_grad():
            for batch in val_batches():
                with torch.autocast(dev.type, dtype=amp_dtype, enabled=amp_dtype is not None):
                    va_sum += _loss(model, batch, loss_fns, ft.LOSS_WEIGHTS) * batch[0].size(0)
                nv += batch[0].size(0)
        val = float(va_sum / nv)
        _sync(dev)
        t_val = time.perf_counter() - t0

        terbaik = val < best_val
        if terbaik:
            best_val, best_epoch = val, epoch
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        history.append({"epoch": epoch, "train_loss": float(tr_sum / n), "val_loss": val,
                        "detik_latih": t_train, "detik_val": t_val,
                        "sampel_per_detik": n / t_train,
                        "detik_kumulatif": time.perf_counter() - t_total})
        log(f"  epoch {epoch:2d}/{n_epochs} train={history[-1]['train_loss']:.3f} val={val:.3f} "
            f"({t_train:.1f}s + {t_val:.1f}s){'  <- terbaik' if terbaik else ''}")

    model.load_state_dict(best_state)
    ringkas = {
        "detik_total_loop": time.perf_counter() - t_total,
        "transfer_ke_device_s": t_transfer if resident else None,
        "epoch_terbaik": best_epoch,
        "val_loss_terbaik": best_val,
        "vram_puncak_mb": round(torch.cuda.max_memory_allocated() / 2**20, 1) if dev.type == "cuda" else None,
    }
    return model, history, ringkas


@torch.no_grad()
def eval_gru(model, data, split, device, bs=4096):
    """Metrik resmi (ml.evaluate) pada split val. Inferensi per batch di device, metrik di CPU."""
    from ml.evaluate import metrics_from_outputs
    from ml.scaler import apply_scaler

    dev = torch.device(device)
    d = np.load(split_path(split))
    X = torch.tensor(apply_scaler(d["X"], data["mean"], data["std"]))
    model.eval()
    outs = [[], [], []]
    for i in range(0, len(X), bs):
        for k, o in enumerate(model(X[i:i + bs].to(dev))):
            outs[k].append(o.float().cpu())
    f, c, t = (torch.cat(o) for o in outs)
    return metrics_from_outputs(f, c, t, d, data["mean"], data["std"])


# ----------------------------------------------------------------------------- XGBoost

def prepare_xgb_data():
    from ml.baselines import SENTINEL, aggregate

    t = {}
    t0 = time.perf_counter()
    tr, va = np.load(split_path(TRAIN)), np.load(split_path(VAL))
    Xtr_raw, Xva_raw = tr["X"], va["X"]
    t["muat_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    out = {
        "Xtr": aggregate(Xtr_raw), "Xva": aggregate(Xva_raw),
        "ttb_tr": tr["y_ttb"], "ttb_va": va["y_ttb"],
        "mode_tr": tr["y_mode"], "mode_va": va["y_mode"],
        "sentinel": SENTINEL,
    }
    t["praproses_s"] = time.perf_counter() - t0      # agregasi 72 fitur (CPU, NumPy)
    return out, t


def xgb_params(seed, device):
    from ml.baselines import XGB_PARAMS

    return {**XGB_PARAMS, "random_state": seed, "device": device}


def train_xgb_ttb(data, seed, device):
    """Pola ml/export_ttb_xgboost.latih_model: hanya jendela menuju breach, target log1p."""
    import xgboost as xgb

    msk = data["ttb_tr"] != data["sentinel"]
    model = xgb.XGBRegressor(**xgb_params(seed, device))
    t0 = time.perf_counter()
    model.fit(data["Xtr"][msk], np.log1p(data["ttb_tr"][msk]))
    return model, {"latih_s": time.perf_counter() - t0, "n_latih": int(msk.sum())}


def eval_xgb_ttb(model, data):
    msk = data["ttb_va"] != data["sentinel"]
    y = data["ttb_va"][msk]
    t0 = time.perf_counter()
    # clamp(min=0) meniru Postprocess di grafik ONNX yang dipakai produksi
    p = np.clip(np.expm1(model.predict(data["Xva"][msk])), 0, None)
    t_pred = time.perf_counter() - t0
    out = {f"ttb_mae_le{b}_menit": float(np.abs(p[y <= b] - y[y <= b]).mean()) for b in (10, 30)}
    out["ttb_mae_semua_menit"] = float(np.abs(p - y).mean())
    out["n_val"] = len(y)
    return out, t_pred


def train_eval_xgb_clf(data, seed, device):
    """Pembanding mode kegagalan + PR-AUC anomali (pola ml/baselines.py)."""
    import xgboost as xgb
    from sklearn.metrics import average_precision_score, f1_score

    from ml.preprocess.build_windows import FAILURE_CLASSES

    # disable_default_eval_metric: XGBoost 3.2.0 build CUDA crash (cudaErrorNoDevice) saat menghitung
    # metrik latih multi:softprob dengan device="cpu" bila GPU disembunyikan (g16-cpu, d0-old).
    # Metrik latih tidak dipakai (tanpa eval_set) dan tidak memengaruhi pohon; prediksi identik.
    clf = xgb.XGBClassifier(objective="multi:softprob", num_class=len(FAILURE_CLASSES),
                            disable_default_eval_metric=True, **xgb_params(seed, device))
    t0 = time.perf_counter()
    clf.fit(data["Xtr"], data["mode_tr"])
    t_fit = time.perf_counter() - t0
    proba = clf.predict_proba(data["Xva"])
    pred = proba.argmax(1)
    y = data["mode_va"]
    return {
        "macro_f1": float(f1_score(y, pred, average="macro")),
        "akurasi": float((pred == y).mean()),
        "anomali_pr_auc": float(average_precision_score((y != 0).astype(int), 1 - proba[:, 0])),
    }, t_fit
