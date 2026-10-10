"""B1 -- reproduksi baseline: latih ulang GRU dan XGBoost dengan konfigurasi asli, 5 seed, split VAL.

  python -m bench.b1_reproduce --tag g16-cpu
  python -m bench.b1_reproduce --tag g16-gpu --models gru --seeds 1000

Hasil: bench/results/<tag>/B1/<model>_seed<seed>.json. Gerbang G1 dihitung oleh bench/g1_check.py.
Arsitektur tidak diubah. Split test tidak disentuh.
"""

import argparse
import sys
import time

from bench.common import RESULTS_DIR, SEEDS, git_info, now_iso, rel, write_json


def main(argv=None):
    from bench.run import apply_device_env, check_cuda_or_die, resolve_tag

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", required=True)
    ap.add_argument("--models", default="gru,xgb_ttb,xgb_clf")
    ap.add_argument("--seeds", default=",".join(map(str, SEEDS)))
    ap.add_argument("--epochs", type=int, default=None, help="hanya untuk uji cepat; default = ml.finetune.N_EPOCHS")
    a = ap.parse_args(argv)

    profile, kind = resolve_tag(a.tag)
    apply_device_env(kind)
    check_cuda_or_die(kind)

    from bench import train_lib as tl
    from bench.env_capture import capture

    quick = a.epochs is not None
    out_dir = RESULTS_DIR / ("_quick" if quick else "") / a.tag / "B1"
    env_path = write_json(out_dir / "env.json", capture(a.tag, profile))
    seeds = [int(s) for s in a.seeds.split(",")]
    models = a.models.split(",")
    t_windows = tl.ensure_windows()

    def base(model, seed):
        return {"tahap": "B1", "model": model, "tag": a.tag, "device": kind, "seed": seed,
                "split_evaluasi": "val", "waktu_utc": now_iso(), "git": git_info(), "env": rel(env_path),
                "kondisi_manual": profile.get("kondisi"), "detik_bangun_jendela": t_windows}

    if "gru" in models:
        data, t_prep = tl.prepare_gru_data()
        for seed in seeds:
            print(f"\n[GRU] seed {seed} [{a.tag}]", flush=True)
            model, hist, ringkas = tl.train_gru(data, seed, kind, n_epochs=a.epochs,
                                                log=lambda s: print(s, flush=True))
            t0 = time.perf_counter()
            metrik = tl.eval_gru(model, data, "val", kind)
            r = base("gru", seed) | {"konfigurasi": "ml.finetune (asli)", "waktu": t_prep | ringkas |
                                     {"eval_s": time.perf_counter() - t0}, "metrik_val": metrik,
                                     "riwayat": hist}
            print(f"  val: {metrik}")
            write_json(out_dir / f"gru_seed{seed}.json", r)

    if "xgb_ttb" in models or "xgb_clf" in models:
        xdata, t_prep = tl.prepare_xgb_data()
        for seed in seeds:
            if "xgb_ttb" in models:
                m, t_fit = tl.train_xgb_ttb(xdata, seed, kind)
                metrik, t_pred = tl.eval_xgb_ttb(m, xdata)
                print(f"[XGB TTB] seed {seed}: {metrik}  ({t_fit['latih_s']:.1f}s)", flush=True)
                write_json(out_dir / f"xgb_ttb_seed{seed}.json", base("xgb_ttb", seed) | {
                    "konfigurasi": "ml.baselines.XGB_PARAMS + pola ml.export_ttb_xgboost.latih_model",
                    "waktu": t_prep | t_fit | {"eval_s": t_pred}, "metrik_val": metrik})
            if "xgb_clf" in models:
                metrik, t_fit = tl.train_eval_xgb_clf(xdata, seed, kind)
                print(f"[XGB clf] seed {seed}: {metrik}  ({t_fit:.1f}s)", flush=True)
                write_json(out_dir / f"xgb_clf_seed{seed}.json", base("xgb_clf", seed) | {
                    "konfigurasi": "ml.baselines (XGBClassifier multi:softprob)",
                    "waktu": t_prep | {"latih_s": t_fit}, "metrik_val": metrik})
    return 0


if __name__ == "__main__":
    sys.exit(main())
