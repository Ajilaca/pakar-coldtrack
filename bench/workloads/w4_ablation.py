"""W4 -- ablation multi-seed: GRU konfigurasi asli dengan dan tanpa jalur statistik ringkasan,
5 seed x 10 epoch (data resident di device). Mengukur waktu dinding total pertanyaan riset
"apakah jalur statistik perlu?" dan menyimpan metrik val per seed.

Satu run = seluruh 10 pelatihan, sehingga protokol W4 = 1 run terukur tanpa pemanasan terpisah.
"""

import time
from dataclasses import replace

import numpy as np

from bench.common import SEEDS
from bench.harness import run_config

EPOCH = 10
VARIAN = {"dengan_stat": {}, "tanpa_stat": {"pakai_statistik": False}}


def _ablation(device, quick):
    from bench import b3_sweep as sw
    from bench import train_lib as tl
    from bench.b3_lib import GruCfg

    data = tl.prepare_gru_data()[0]
    seeds = SEEDS[:1] if quick else SEEDS
    hasil, t0 = {}, time.perf_counter()
    for nama, ubah in VARIAN.items():
        runs = []
        for seed in seeds:
            cfg = replace(GruCfg(**ubah), n_epochs=1 if quick else EPOCH)
            t1 = time.perf_counter()
            m, _, _ = sw.eval_gru(data, cfg, seed, device)
            runs.append(
                {
                    "seed": seed,
                    "detik": time.perf_counter() - t1,
                    "macro_f1": m["macro_f1"],
                    "anomali_pr_auc": m["anomali_pr_auc"],
                    "forecast_t30_mae_c": m["forecast_t30_mae_c"],
                }
            )
        hasil[nama] = {
            "runs": runs,
            **{
                f"{k}_mean": float(np.mean([r[k] for r in runs]))
                for k in ("macro_f1", "anomali_pr_auc", "forecast_t30_mae_c", "detik")
            },
        }
    return {
        "waktu": {"ablation_total_s": time.perf_counter() - t0},
        "n_pelatihan": len(seeds) * len(VARIAN),
        "varian": hasil,
    }


def run(ctx):
    from bench import train_lib as tl

    tl.ensure_windows()
    cfg = {"varian": list(VARIAN), "seed": SEEDS, "epoch": EPOCH, "basis": "ml/finetune.py (asli)"}
    return run_config(
        ctx, "W4", "stat_vs_tanpa", cfg, lambda seed, pemanasan: _ablation(ctx.device, ctx.quick), repeats=1, warmup=0
    )
