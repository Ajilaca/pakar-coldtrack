"""Latih berkeley_v1 (XGBoost) dan bandingkan dengan aturan v0 di mote VAL. Mote test tidak disentuh.

  python -m ml.sensor_health.train --tag g16-gpu --trials 40

Langkah (definisi: bench/results/keputusan/G4_definisi.json):
1. v0 di mote val: PR-AUC + recall pada alarm skor >= 1.
2. Sweep Optuna (TPE seed 0, trial tetap), objektif PR-AUC val (H = 24 jam).
3. Latih ulang parameter terbaik, pilih ambang di val: alarm palsu/mote-hari terkecil dengan
   recall >= recall v0 di val.
Hasil: bench/results/<tag>/B4/val.json + model ml/sensor_health/artifacts/berkeley_v1.{json,meta.json}
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np

from ml.sensor_health import evaluate as ev

ART = Path(__file__).resolve().parent / "artifacts"
LABEL = "y_24j"
# Level lingkungan absolut: di lab, mote gagal pada periode yang hampir sama sehingga level suhu dapat
# menjadi penanda kalender, bukan kesehatan sensor -- dan tidak berpindah ke domain truk.
FITUR_LINGKUNGAN = {"t_mean", "t_min", "t_max", "t_akhir", "h_mean", "cahaya_mean"}
SEED = 0


def latih(Xtr, ytr, params, device):
    import xgboost as xgb

    m = xgb.XGBClassifier(objective="binary:logistic", tree_method="hist", device=device, random_state=SEED,
                          n_jobs=-1, eval_metric="aucpr", **params)
    t0 = time.perf_counter()
    m.fit(Xtr, ytr)
    return m, time.perf_counter() - t0


def main(argv=None):
    from bench.common import RESULTS_DIR, git_info, now_iso, rel, write_json
    from bench.run import apply_device_env, check_cuda_or_die, resolve_tag

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", default="g16-gpu")
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--fitur", choices=["semua", "kesehatan"], default="semua",
                    help="kesehatan = tanpa level lingkungan absolut (suhu/kelembapan/cahaya), lihat FITUR_LINGKUNGAN")
    a = ap.parse_args(argv)
    _, kind = resolve_tag(a.tag)
    apply_device_env(kind)
    check_cuda_or_die(kind)
    import optuna

    df = ev.muat()
    tr, va = df[df["split"] == "train"], df[df["split"] == "val"]
    cols = [c for c in ev.fitur_kolom(df) if a.fitur == "semua" or c not in FITUR_LINGKUNGAN]
    nama = "berkeley_v1" if a.fitur == "semua" else "berkeley_v1_kesehatan"
    Xtr, ytr, Xva = tr[cols].to_numpy(np.float32), tr[LABEL].to_numpy(), va[cols].to_numpy(np.float32)

    v0 = ev.ringkas(va, va["skor_v0"], 1.0)
    print(f"v0 val: PR-AUC {v0['pr_auc']:.4f} recall {v0['recall_jendela']:.3f} "
          f"alarm palsu/mote-hari {v0['alarm_palsu_per_mote_hari']:.3f}", flush=True)

    def objektif(trial):
        p = {"n_estimators": trial.suggest_int("n_estimators", 100, 800, step=50),
             "max_depth": trial.suggest_int("max_depth", 3, 8),
             "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.3, log=True),
             "subsample": trial.suggest_float("subsample", 0.6, 1.0),
             "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
             "min_child_weight": trial.suggest_float("min_child_weight", 1.0, 20.0, log=True),
             "scale_pos_weight": trial.suggest_float("scale_pos_weight", 1.0, 20.0, log=True)}
        m, _ = latih(Xtr, ytr, p, kind)
        return ev.ringkas(va, m.predict_proba(Xva)[:, 1], 0.5)["pr_auc"]

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    t0 = time.perf_counter()
    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objektif, n_trials=a.trials)
    t_sweep = time.perf_counter() - t0

    best = study.best_params
    model, t_fit = latih(Xtr, ytr, best, kind)
    mentah = model.predict_proba(Xva)[:, 1]
    # penghalusan kausal dipilih di val: alarm palsu terkecil dengan recall >= recall v0
    pilihan = {}
    for j in ev.HALUS:
        sj = ev.haluskan(va, mentah, j)
        aj = ev.pilih_ambang(va, sj, v0["recall_jendela"])
        if aj:
            pilihan[j] = {"ambang": aj[0], "alarm_palsu_per_mote_hari": aj[1], "recall": aj[2]}
            print(f"  halus {j:6s} ambang {aj[0]:.4f} recall {aj[2]:.3f} alarm palsu/mote-hari {aj[1]:.3f}")
    if not pilihan:
        raise SystemExit("Tidak ada ambang v1 yang mencapai recall v0 di val")
    halus = min(pilihan, key=lambda j: pilihan[j]["alarm_palsu_per_mote_hari"])
    s_va = ev.haluskan(va, mentah, halus)
    amb = (pilihan[halus]["ambang"],)
    v1 = ev.ringkas(va, s_va, amb[0])
    sekunder = {f"y_{h}j": {"v0_pr_auc": ev.ringkas(va, va["skor_v0"], 1.0, f"y_{h}j")["pr_auc"],
                            "v1_pr_auc": ev.ringkas(va, s_va, amb[0], f"y_{h}j")["pr_auc"]} for h in (1, 6)}
    pent = sorted(zip(model.feature_importances_, cols), reverse=True)[:8]

    ART.mkdir(exist_ok=True)
    model.save_model(ART / f"{nama}.json")
    meta = {"fitur": cols, "ambang": amb[0], "penghalusan": halus, "label": LABEL, "params": best, "seed": SEED,
            "dilatih_di": a.tag, "waktu_utc": now_iso(), "git": git_info()}
    (ART / f"{nama}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    hasil = {"tahap": "B4", "split": "val", "tag": a.tag, "varian_fitur": a.fitur, "fitur": cols,
             "waktu_utc": now_iso(), "git": git_info(),
             "n_mote": {s: int(df.loc[df["split"] == s, "moteid"].nunique()) for s in ("train", "val", "test")},
             "v0": v0, "v1": v1, "penghalusan_dipilih": halus, "penghalusan_kandidat": pilihan,
             "sekunder_pr_auc": sekunder,
             "sweep": {"n_trial": a.trials, "detik": t_sweep, "pr_auc_val_terbaik": study.best_value, "params": best},
             "waktu": {"latih_final_s": t_fit}, "fitur_terpenting": [(n, float(v)) for v, n in pent],
             "model": rel(ART / f"{nama}.json")}
    path = write_json(RESULTS_DIR / a.tag / "B4" / f"val_{a.fitur}.json", hasil)
    print(f"v1 val: PR-AUC {v1['pr_auc']:.4f} recall {v1['recall_jendela']:.3f} "
          f"alarm palsu/mote-hari {v1['alarm_palsu_per_mote_hari']:.3f} (ambang {amb[0]:.4f})")
    print("sekunder:", sekunder)
    print("fitur terpenting:", [(n, round(float(v), 3)) for v, n in pent[:5]])
    print("Tersimpan:", rel(path))


if __name__ == "__main__":
    main()
