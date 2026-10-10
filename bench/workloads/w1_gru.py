"""W1 -- latih GRU (konfigurasi ml/finetune.py) dengan variasi batch, presisi, dan pemuatan data.

Tiap run = satu pelatihan penuh (N_EPOCHS ml.finetune) + evaluasi metrik resmi di split val.
Ulangan memakai seed 1000-1004, jadi ulangan sekaligus distribusi kualitas untuk gerbang G2.
Pemanasan = 1 epoch (cukup untuk kompilasi kernel dan cache disk), dibuang.

Time-to-target: waktu kumulatif (latih + val) sampai epoch pertama dengan val loss <= TARGET.
TARGET ditetapkan SEBELUM W1 dijalankan: 1,05 x median val loss terbaik B1 g16-cpu (b256 fp32,
5 seed), dibaca dari bench/results/g16-cpu/B1/gru_seed*.json -- sama untuk semua device.
"""

import json
import statistics
import time

from bench.common import RESULTS_DIR, rel
from bench.harness import run_config, tidak_berlaku

FAKTOR_TARGET = 1.05

# (config_id, argumen train_gru, hanya_cuda)
CONFIGS = [
    ("b256_fp32", {"batch_size": 256}, False),            # konfigurasi asli ml/finetune.py
    ("b1024_fp32", {"batch_size": 1024}, False),
    ("b4096_fp32", {"batch_size": 4096}, False),
    ("b256_bf16", {"batch_size": 256, "amp": "bf16"}, True),
    ("b1024_bf16", {"batch_size": 1024, "amp": "bf16"}, True),
    ("b4096_bf16", {"batch_size": 4096, "amp": "bf16"}, True),
    ("b256_fp16", {"batch_size": 256, "amp": "fp16"}, True),
    ("b1024_fp16", {"batch_size": 1024, "amp": "fp16"}, True),
    ("b4096_fp16", {"batch_size": 4096, "amp": "fp16"}, True),
    ("b1024_fp32_pin", {"batch_size": 1024, "pin_memory": True}, True),
    ("b1024_fp32_w2pin", {"batch_size": 1024, "num_workers": 2, "pin_memory": True}, True),
    # data dipindah ke device sekali, tanpa DataLoader -- berlaku juga di CPU (membuang overhead loader)
    ("b1024_fp32_resident", {"batch_size": 1024, "resident": True}, False),
]


def target_val_loss():
    files = sorted((RESULTS_DIR / "g16-cpu" / "B1").glob("gru_seed*.json"))
    if len(files) < 5:
        raise RuntimeError("target time-to-target butuh 5 hasil B1 g16-cpu (bench/results/g16-cpu/B1/)")
    vals = [json.loads(f.read_text(encoding="utf-8"))["waktu"]["val_loss_terbaik"] for f in files]
    return FAKTOR_TARGET * statistics.median(vals), [rel(f) for f in files]


def run(ctx):
    from bench import train_lib as tl
    from ml import finetune as ft

    tl.ensure_windows()
    target, sumber_target = target_val_loss()
    print(f"  target val loss (time-to-target) = {target:.4f}")
    pilih = set(ctx.configs) if ctx.configs else None
    files = []

    for cid, kw, hanya_cuda in CONFIGS:
        if pilih and cid not in pilih:
            continue
        cfg = kw | {"n_epochs": ft.N_EPOCHS, "lr": [ft.LR_BACKBONE, ft.LR_HEADS], "loss_weights": ft.LOSS_WEIGHTS}
        if hanya_cuda and ctx.device != "cuda":
            files += tidak_berlaku(ctx, "W1", cid, cfg, "varian khusus GPU (AMP / pin_memory / workers)")
            continue

        def satu_run(seed, pemanasan, kw=kw):
            data, t_prep = tl.prepare_gru_data()
            n_ep = 1 if (pemanasan or ctx.quick) else ft.N_EPOCHS
            model, hist, ringkas = tl.train_gru(data, seed, ctx.device, n_epochs=n_ep, log=lambda s: None, **kw)
            t0 = time.perf_counter()
            metrik = tl.eval_gru(model, data, "val", ctx.device)
            t_eval = time.perf_counter() - t0
            capai = next((h for h in hist if h["val_loss"] <= target), None)
            lat = [h["detik_latih"] for h in hist]
            return {
                "waktu": t_prep | {
                    "transfer_ke_device_s": ringkas["transfer_ke_device_s"],
                    "latih_loop_s": ringkas["detik_total_loop"],
                    "eval_s": t_eval,
                    "detik_latih_per_epoch_median": statistics.median(lat),
                    "sampel_per_detik_median": statistics.median(h["sampel_per_detik"] for h in hist),
                },
                "time_to_target": {
                    "target_val_loss": target, "sumber_target": sumber_target,
                    "tercapai": capai is not None,
                    "epoch": capai["epoch"] if capai else None,
                    "detik": capai["detik_kumulatif"] if capai else None,
                },
                "ringkas_latih": ringkas,
                "metrik_val": metrik,
                "riwayat": hist,
            }

        try:
            files += run_config(ctx, "W1", cid, cfg, satu_run)
        except RuntimeError as e:     # mis. presisi tidak didukung kernel cuDNN RNN -- temuan, bukan crash
            files += tidak_berlaku(ctx, "W1", cid, cfg, f"gagal dijalankan: {type(e).__name__}: {e}"[:500])
    return files
