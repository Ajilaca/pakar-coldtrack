"""W2 -- latih XGBoost TTB 300 pohon (ml/baselines.XGB_PARAMS, pola ml/export_ttb_xgboost): CPU hist vs cuda.

Komponen waktu: muat jendela, praproses (agregasi 72 fitur, NumPy di CPU), latih, prediksi split val.
Kualitas: MAE TTB <= 10 / <= 30 menit / seluruh rentang (split val).
Catatan: prediksi di jalur cuda memakai masukan NumPy (CPU) -- XGBoost memberi peringatan fallback
DMatrix; itu kondisi pemakaian nyata dan ikut terukur di prediksi_s.
"""

from bench.harness import run_config, tidak_berlaku

CONFIGS = [
    ("cpu_hist", "cpu", False),
    ("cuda_hist", "cuda", True),
]


def run(ctx):
    from bench import train_lib as tl
    from ml.baselines import XGB_PARAMS

    tl.ensure_windows()
    pilih = set(ctx.configs) if ctx.configs else None
    files = []
    for cid, dev, hanya_cuda in CONFIGS:
        if pilih and cid not in pilih:
            continue
        cfg = {k: v for k, v in XGB_PARAMS.items() if k != "random_state"} | {"device": dev}
        if hanya_cuda and ctx.device != "cuda":
            files += tidak_berlaku(ctx, "W2", cid, cfg, "XGBoost device=cuda butuh GPU NVIDIA")
            continue
        if dev == "cpu" and ctx.device == "cuda":
            print(f"  {cid}: diukur di tag *-cpu (GPU disembunyikan), bukan di tag gpu")
            continue

        def satu_run(seed, pemanasan, dev=dev):
            data, t_prep = tl.prepare_xgb_data()
            model, t_fit = tl.train_xgb_ttb(data, seed, dev)
            metrik, t_pred = tl.eval_xgb_ttb(model, data)
            return {"waktu": t_prep | {"latih_s": t_fit["latih_s"], "prediksi_s": t_pred},
                    "n_latih": t_fit["n_latih"], "metrik_val": metrik}

        files += run_config(ctx, "W2", cid, cfg, satu_run)
    return files
