"""W3 -- sweep hyperparameter Optuna dengan beban TETAP, sama di semua device.

Ruang pencarian = bench/b3_sweep.py (ruang_gru / ruang_xgb), sampler TPE seed 0, tanpa pruning.
Beban dikecilkan dari sweep B3 (60 trial x 30 epoch) agar dapat dijalankan di CPU dan d0-old dalam
waktu wajar; yang diukur adalah throughput (trial/jam) dan waktu dinding, bukan mutu model terbaik.
  gru: 8 trial x 5 epoch (data resident di device)    xgb: 20 trial classifier

Satu run berisi banyak pelatihan sehingga protokol W3 = 1 run terukur tanpa pemanasan terpisah;
sebaran waktu antar-trial tercatat di dalam run.
"""

import time
from dataclasses import replace

from bench.harness import run_config, tidak_berlaku

BEBAN = {"gru": {"trial": 8, "epoch": 5}, "xgb": {"trial": 20}}


def _sweep(model, device, quick):
    import optuna

    from bench import b3_sweep as sw
    from bench import train_lib as tl

    n_trial = 2 if quick else BEBAN[model]["trial"]
    data = tl.prepare_gru_data()[0] if model == "gru" else tl.prepare_xgb_data()[0]
    per_trial = []

    def objektif(trial):
        t0 = time.perf_counter()
        if model == "gru":
            cfg = replace(sw.ruang_gru(trial), n_epochs=1 if quick else BEBAN["gru"]["epoch"])
            m, _, _ = sw.eval_gru(data, cfg, sw.SEED_TRIAL, device)
            s = sw.skor(m)
        else:
            m, _, _ = sw.eval_xgb(data, sw.ruang_xgb(trial), sw.SEED_TRIAL, device)
            s = sw.skor(m, cek_forecast=False)
        per_trial.append({"trial": trial.number, "detik": time.perf_counter() - t0, "skor": s})
        return s

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=0))
    t0 = time.perf_counter()
    study.optimize(objektif, n_trials=n_trial)
    total = time.perf_counter() - t0
    return {
        "waktu": {"sweep_s": total, "trial_per_jam": n_trial / (total / 3600)},
        "n_trial": n_trial,
        "skor_terbaik": study.best_value,
        "per_trial": per_trial,
    }


def run(ctx):
    from bench import train_lib as tl

    tl.ensure_windows()
    files = []
    for cid, model, xgb_dev in [("gru", "gru", None), ("xgb_cpu", "xgb", "cpu"), ("xgb_cuda", "xgb", "cuda")]:
        if ctx.configs and cid not in ctx.configs:
            continue
        cfg = {"model": model, **BEBAN[model]}
        if xgb_dev == "cuda" and ctx.device != "cuda":
            files += tidak_berlaku(ctx, "W3", cid, cfg, "XGBoost device=cuda butuh GPU NVIDIA")
            continue
        if xgb_dev == "cpu" and ctx.device == "cuda":
            print(f"  {cid}: diukur di tag *-cpu")
            continue
        dev = xgb_dev or ctx.device
        files += run_config(
            ctx,
            "W3",
            cid,
            cfg,
            lambda seed, pemanasan, model=model, dev=dev: _sweep(model, dev, ctx.quick),
            repeats=1,
            warmup=0,
        )
    return files
