"""B3 / W3 -- sweep hyperparameter Optuna (jumlah trial tetap) di split VAL.

  python -m bench.b3_sweep --tag g16-gpu --model gru --trials 60
  python -m bench.b3_sweep --tag g16-gpu --model xgb --trials 60

DIDAFTARKAN SEBELUM SWEEP DIJALANKAN (aturan main, tidak diubah setelah melihat hasil):
- Objektif per trial (seed 1000, split val): skor = (macro_f1 + anomali_pr_auc) / 2.
- Kendala GRU: forecast_t30_mae_c <= 0,25 C (baseline B1 ~0,21; target PRD < 0,8). Trial yang
  melanggar diberi skor - 1 (tidak layak).
- Sampler TPE seed 0, jumlah trial tetap; tidak ada early stopping antar trial (pruning) supaya
  jumlah kerja sama di semua device saat dipakai sebagai benchmark W3.
- Kandidat (top-3 per model) dikonfirmasi ulang dengan 5 seed di bench/b3_confirm.py. Kandidat
  hanya diajukan ke G3 bila mean skor 5 seed > mean baseline + rentang antar-seed baseline
  (maks - min), dan (GRU) mean forecast_t30 <= 0,25 C.
Ruang pencarian tetap dalam keluarga model yang sama (GRU + statistik ringkasan; XGBoost dengan
72 fitur agregat). Tanpa transfer learning (temuan proposal).

Hasil: bench/results/<tag>/B3/sweep_<model>/trial_XXX.json + ringkasan.json
"""

import argparse
import time

import numpy as np

from bench.common import RESULTS_DIR, git_info, now_iso, write_json

BATAS_FORECAST_T30 = 0.25
SEED_TRIAL = 1000


def skor(m, cek_forecast=True):
    s = (m["macro_f1"] + m["anomali_pr_auc"]) / 2
    if cek_forecast and m["forecast_t30_mae_c"] > BATAS_FORECAST_T30:
        return s - 1.0
    return s


def ruang_gru(trial):
    from bench.b3_lib import GruCfg

    return GruCfg(
        hidden_size=trial.suggest_categorical("hidden_size", [32, 64, 96, 128]),
        num_layers=trial.suggest_int("num_layers", 1, 3),
        dropout=trial.suggest_float("dropout", 0.0, 0.4),
        lr_backbone=trial.suggest_float("lr_backbone", 2e-4, 3e-3, log=True),
        lr_heads=trial.suggest_float("lr_heads", 5e-4, 5e-3, log=True),
        w_forecast=trial.suggest_float("w_forecast", 3.0, 60.0, log=True),
        w_ttb=trial.suggest_float("w_ttb", 0.0, 8.0),
        class_weight_power=trial.suggest_float("class_weight_power", 0.0, 1.0),
        freeze_epochs=trial.suggest_categorical("freeze_epochs", [0, 3]),
        label_smoothing=trial.suggest_float("label_smoothing", 0.0, 0.1),
        batch_size=trial.suggest_categorical("batch_size", [128, 256, 512]),
    )


def ruang_xgb(trial):
    return {
        "n_estimators": trial.suggest_int("n_estimators", 100, 800, step=50),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.3, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "min_child_weight": trial.suggest_float("min_child_weight", 1.0, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 0.1, 10.0, log=True),
        "class_weight_power": trial.suggest_float("class_weight_power", 0.0, 1.0),
    }


def eval_gru(data, cfg, seed, device):
    from bench import b3_lib as b3

    model, info = b3.train(data, cfg, seed, device)
    (f, c, t), d = b3.predict(model, data, device)
    return b3.metrik_lengkap(f, c, t, d, data["mean"], data["std"]), info, model


def eval_xgb(xd, p, seed, device):
    import xgboost as xgb
    from sklearn.metrics import average_precision_score, f1_score

    from ml.preprocess.build_windows import FAILURE_CLASSES

    p = dict(p)
    power = p.pop("class_weight_power")
    counts = np.bincount(xd["mode_tr"], minlength=len(FAILURE_CLASSES))
    w = (len(xd["mode_tr"]) / (len(FAILURE_CLASSES) * counts)) ** power
    clf = xgb.XGBClassifier(objective="multi:softprob", num_class=len(FAILURE_CLASSES), tree_method="hist",
                            device=device, random_state=seed, n_jobs=-1, disable_default_eval_metric=True, **p)
    t0 = time.perf_counter()
    clf.fit(xd["Xtr"], xd["mode_tr"], sample_weight=w[xd["mode_tr"]])
    t_fit = time.perf_counter() - t0
    proba = clf.predict_proba(xd["Xva"])
    y = xd["mode_va"]
    m = {"macro_f1": float(f1_score(y, proba.argmax(1), average="macro")),
         "akurasi": float((proba.argmax(1) == y).mean()),
         "anomali_pr_auc": float(average_precision_score((y != 0).astype(int), 1 - proba[:, 0]))}
    return m, {"detik_latih": t_fit}, clf


def main(argv=None):
    from bench.run import apply_device_env, check_cuda_or_die, resolve_tag

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", default="g16-gpu")
    ap.add_argument("--model", choices=["gru", "xgb"], required=True)
    ap.add_argument("--trials", type=int, default=60)
    a = ap.parse_args(argv)
    profile, kind = resolve_tag(a.tag)
    apply_device_env(kind)
    check_cuda_or_die(kind)

    import optuna

    from bench import train_lib as tl
    from bench.common import rel, stamp
    from bench.env_capture import capture

    tl.ensure_windows()
    out = RESULTS_DIR / a.tag / "B3" / f"sweep_{a.model}"
    env_path = write_json(out / f"env_{stamp()}.json", capture(a.tag, profile))
    data = tl.prepare_gru_data()[0] if a.model == "gru" else tl.prepare_xgb_data()[0]
    t_mulai = time.perf_counter()

    def objective(trial):
        if a.model == "gru":
            cfg = ruang_gru(trial)
            m, info, _ = eval_gru(data, cfg, SEED_TRIAL, kind)
            params = cfg.as_dict()
            s = skor(m)
        else:
            params = ruang_xgb(trial)
            m, info, _ = eval_xgb(data, params, SEED_TRIAL, kind)
            s = skor(m, cek_forecast=False)
        write_json(out / f"trial_{trial.number:03d}.json", {
            "trial": trial.number, "model": a.model, "tag": a.tag, "seed": SEED_TRIAL, "split": "val",
            "waktu_utc": now_iso(), "git": git_info(), "env": rel(env_path), "params": params,
            "skor": s, "metrik_val": {k: v for k, v in m.items() if k != "confusion"}, "latih": info})
        print(f"  trial {trial.number:3d} skor {s:.4f} F1 {m['macro_f1']:.4f} PR-AUC {m['anomali_pr_auc']:.4f}"
              + (f" t30 {m['forecast_t30_mae_c']:.4f}" if a.model == "gru" else "")
              + f" ({info['detik_latih']:.0f}s)", flush=True)
        return s

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=0))
    study.optimize(objective, n_trials=a.trials)
    top = sorted(study.trials, key=lambda t: t.value, reverse=True)[:3]
    write_json(out / "ringkasan.json", {
        "model": a.model, "tag": a.tag, "n_trial": len(study.trials), "detik_total": time.perf_counter() - t_mulai,
        "trial_per_jam": len(study.trials) / ((time.perf_counter() - t_mulai) / 3600),
        "terbaik": [{"trial": t.number, "skor": t.value, "params": t.params} for t in top],
        "aturan": {"skor": "(macro_f1 + anomali_pr_auc) / 2", "batas_forecast_t30": BATAS_FORECAST_T30,
                   "seed_trial": SEED_TRIAL, "sampler": "TPE seed 0"},
        "waktu_utc": now_iso(), "git": git_info(),
    })
    print("Top-3:", [(t.number, round(t.value, 4)) for t in top])


if __name__ == "__main__":
    main()
