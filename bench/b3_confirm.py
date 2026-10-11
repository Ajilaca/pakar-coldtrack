"""B3 / W4 -- konfirmasi kandidat sweep dengan 5 seed + ablation, lalu aturan adopsi (split VAL).

  python -m bench.b3_confirm --tag g16-gpu

Varian GRU (5 seed masing-masing):
  baseline              konfigurasi asli ml/finetune.py
  baseline_tanpa_stat   ablation: jalur statistik ringkasan dimatikan
  sweep_top{1,2,3}      top-3 sweep GRU
  top1_tanpa_stat       ablation pada kandidat terbaik
  top1_bobot_asli       kandidat terbaik dengan bobot loss asli (30/1/8)
Varian XGBoost classifier (5 seed): baseline (ml/baselines.XGB_PARAMS) dan top-3 sweep XGB.

Aturan adopsi (didaftarkan di bench/b3_sweep.py sebelum sweep): kandidat lolos bila mean skor
5 seed > mean baseline + rentang antar-seed baseline, dan (GRU) mean forecast_t30 <= 0,25 C.

Hasil: bench/results/<tag>/B3/confirm/<varian>_seed<seed>.json + keputusan_kandidat.json
"""

import argparse
import json
from dataclasses import replace

import numpy as np

from bench.b3_sweep import BATAS_FORECAST_T30, eval_gru, eval_xgb, skor
from bench.common import RESULTS_DIR, SEEDS, git_info, now_iso, write_json


def _top(tag, model):
    p = RESULTS_DIR / tag / "B3" / f"sweep_{model}" / "ringkasan.json"
    return json.loads(p.read_text(encoding="utf-8"))["terbaik"]


def ringkas(runs, gru):
    s = np.array([r["skor"] for r in runs])
    out = {"skor_mean": float(s.mean()), "skor_min": float(s.min()), "skor_maks": float(s.max()),
           "rentang": float(np.ptp(s))}
    for k in ["macro_f1", "anomali_pr_auc", "akurasi"] + (["forecast_t30_mae_c", "ttb_mae_menit"] if gru else []):
        out[k + "_mean"] = float(np.mean([r["metrik_val"][k] for r in runs]))
    return out


def main(argv=None):
    from bench.run import apply_device_env, check_cuda_or_die, resolve_tag

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", default="g16-gpu")
    a = ap.parse_args(argv)
    _, kind = resolve_tag(a.tag)
    apply_device_env(kind)
    check_cuda_or_die(kind)

    from bench import train_lib as tl
    from bench.b3_lib import GruCfg
    from ml.baselines import XGB_PARAMS

    tl.ensure_windows()
    out = RESULTS_DIR / a.tag / "B3" / "confirm"
    base = GruCfg()
    top_gru = _top(a.tag, "gru")
    best = GruCfg(**top_gru[0]["params"])
    varian_gru = {"baseline": base, "baseline_tanpa_stat": replace(base, pakai_statistik=False)}
    varian_gru |= {f"sweep_top{i + 1}": GruCfg(**t["params"]) for i, t in enumerate(top_gru)}
    varian_gru |= {"top1_tanpa_stat": replace(best, pakai_statistik=False),
                   "top1_bobot_asli": replace(best, w_forecast=30.0, w_failure=1.0, w_ttb=8.0)}

    base_xgb = {k: v for k, v in XGB_PARAMS.items() if k not in ("random_state", "n_jobs", "tree_method")}
    varian_xgb = {"baseline": base_xgb | {"class_weight_power": 0.0}}
    varian_xgb |= {f"sweep_top{i + 1}": t["params"] for i, t in enumerate(_top(a.tag, "xgb"))}

    hasil = {"waktu_utc": now_iso(), "git": git_info(), "tag": a.tag, "split": "val", "gru": {}, "xgb": {}}
    data = tl.prepare_gru_data()[0]
    for nama, cfg in varian_gru.items():
        runs = []
        for seed in SEEDS:
            m, info, _ = eval_gru(data, cfg, seed, kind)
            r = {"varian": nama, "seed": seed, "params": cfg.as_dict(), "skor": skor(m),
                 "metrik_val": m, "latih": info, "waktu_utc": now_iso()}
            write_json(out / f"gru_{nama}_seed{seed}.json", r)
            runs.append(r)
        hasil["gru"][nama] = ringkas(runs, gru=True) | {"params": cfg.as_dict()}
        h = hasil["gru"][nama]
        print(f"GRU {nama:20s} skor {h['skor_mean']:.4f} (rentang {h['rentang']:.4f}) F1 {h['macro_f1_mean']:.4f} "
              f"PR-AUC {h['anomali_pr_auc_mean']:.4f} t30 {h['forecast_t30_mae_c_mean']:.4f}", flush=True)

    xd = tl.prepare_xgb_data()[0]
    for nama, p in varian_xgb.items():
        runs = []
        for seed in SEEDS:
            m, info, _ = eval_xgb(xd, p, seed, kind)
            r = {"varian": nama, "seed": seed, "params": p, "skor": skor(m, cek_forecast=False),
                 "metrik_val": m, "latih": info, "waktu_utc": now_iso()}
            write_json(out / f"xgb_{nama}_seed{seed}.json", r)
            runs.append(r)
        hasil["xgb"][nama] = ringkas(runs, gru=False) | {"params": p}
        h = hasil["xgb"][nama]
        print(f"XGB {nama:20s} skor {h['skor_mean']:.4f} (rentang {h['rentang']:.4f}) F1 {h['macro_f1_mean']:.4f} "
              f"PR-AUC {h['anomali_pr_auc_mean']:.4f}", flush=True)

    # aturan adopsi yang didaftarkan sebelum sweep
    keputusan = {}
    for model in ("gru", "xgb"):
        b = hasil[model]["baseline"]
        ambang = b["skor_mean"] + b["rentang"]
        for nama, h in hasil[model].items():
            if not nama.startswith("sweep_top"):
                continue
            ok = h["skor_mean"] > ambang
            if model == "gru":
                ok = ok and h["forecast_t30_mae_c_mean"] <= BATAS_FORECAST_T30
            keputusan[f"{model}/{nama}"] = {"lolos": ok, "skor_mean": h["skor_mean"], "ambang": ambang}
    lolos = {k: v for k, v in keputusan.items() if v["lolos"]}
    hasil["keputusan"] = keputusan
    hasil["kandidat_terbaik"] = {m: max((k for k in lolos if k.startswith(m)), key=lambda k: lolos[k]["skor_mean"],
                                        default=None) for m in ("gru", "xgb")}
    write_json(RESULTS_DIR / a.tag / "B3" / "keputusan_kandidat.json", hasil)
    print("Kandidat lolos aturan adopsi:", hasil["kandidat_terbaik"])


if __name__ == "__main__":
    main()
