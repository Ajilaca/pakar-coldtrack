"""B13 -- GRU v5 dilatih ulang dengan augmentasi supaya tidak bergantung pada satu sinyal bersih simulator.

B12 (bench/experiments/b12/b12_shortcut.py) menunjukkan A3 hanya dikenali dari flag reefer_on, A1 dari door_open,
dan A8 dari suhu awal muat. Augmentasi di bawah hanya dikenakan pada jendela TRAIN (val tetap bersih untuk
memilih epoch); konfigurasi, label, konteks, dan seed sama dengan GRU B8:
  reefer_bohong  sebagian jendela A3: reefer_on = 1 (suhu tetap naik), reefer_duration_min dihitung ulang
  pintu_hilang   sebagian jendela A1: door_open = 0
  suhu_awal      semua jendela: suhu_awal_muat digeser acak, kini_minus_awal ikut disesuaikan
  derau_suhu     sebagian jendela selain masalah_sensor: derau Gaussian pada temp_c (sensor macet memang datar)
Lalu model diekspor ke ONNX kandidat (paritas diuji) dan diuji ulang dengan semua gangguan B12. Split test tidak
disentuh.

  python -m bench.experiments.b13.b13_gru_augmentasi --threads 4

Hasil: bench/results/lokal-cpu/B13/gru_v5_aug_seed1000.json,
       backend/models/candidates/coldtrack_gru_v5_aug.onnx
"""

import argparse
import json
import time

import numpy as np

from bench.core.common import RESULTS_DIR, ROOT, git_info, now_iso, rel, write_json

AUG = {"p_reefer_bohong": 0.5, "p_pintu_hilang": 0.5, "geser_suhu_awal_c": 2.5, "p_derau": 0.5, "derau_maks_c": 0.3}
NAMA = "gru_v5_aug_seed1000"
CKPT = ROOT / "data" / "processed" / "windows" / f"{NAMA}.pt"
ONNX = ROOT / "backend" / "models" / "candidates" / "coldtrack_gru_v5_aug.onnx"
OUT = RESULTS_DIR / "lokal-cpu" / "B13" / f"{NAMA}.json"
B12_V5 = RESULTS_DIR / "lokal-cpu" / "B12" / "shortcut.json"


def augmentasi(X, ctx, y, rng, aug=AUG):
    """Salinan (X mentah [n, 60, 12], konteks mentah [n, 6]) yang sudah diaugmentasi, plus jumlah per jenis."""
    from bench.experiments.b8 import b8_lib as b8
    from ml.preprocess.build_windows import CLASS_TO_IDX
    from ml.tests.test_data_contract import FEATURE_COLUMNS

    ix = {c: i for i, c in enumerate(FEATURE_COLUMNS)}
    kx = {c: i for i, c in enumerate(b8.KONTEKS)}
    X, ctx, n = X.copy(), ctx.copy(), len(y)

    m = (y == CLASS_TO_IDX["A3"]) & (rng.random(n) < aug["p_reefer_bohong"])
    X[m, :, ix["reefer_on"]] = 1.0
    X[m, :, ix["reefer_duration_min"]] = np.arange(1, X.shape[1] + 1, dtype=np.float32)
    jumlah = {"reefer_bohong": int(m.sum())}

    m = (y == CLASS_TO_IDX["A1"]) & (rng.random(n) < aug["p_pintu_hilang"])
    X[m, :, ix["door_open"]] = 0.0
    jumlah["pintu_hilang"] = int(m.sum())

    geser = rng.uniform(-aug["geser_suhu_awal_c"], aug["geser_suhu_awal_c"], n).astype(np.float32)
    ctx[:, kx["suhu_awal_muat"]] += geser
    ctx[:, kx["kini_minus_awal"]] -= geser
    jumlah["suhu_awal"] = n

    m = (y != CLASS_TO_IDX["masalah_sensor"]) & (rng.random(n) < aug["p_derau"])
    sd = rng.uniform(0, aug["derau_maks_c"], int(m.sum())).astype(np.float32)
    e = rng.normal(0, 1, (int(m.sum()), X.shape[1])).astype(np.float32) * sd[:, None]
    X[m, :, ix["temp_c"]] += e
    X[m, :, ix["delta_temp"]] += np.diff(e, axis=1, prepend=np.zeros((len(e), 1), np.float32))
    X[m, :, ix["delta_ambient"]] += e
    jumlah["derau_suhu"] = int(m.sum())
    return X, ctx, jumlah


def ekspor(model_inti, ck):
    import onnxruntime as ort
    import torch

    from bench.experiments.b8 import b8_lib as b8
    from bench.experiments.b8.b8_export_onnx import TOLERANSI, Deploy

    model = Deploy(model_inti, ck).eval()
    X = np.load(b8.path_npz("val"))["X"][:256].astype(np.float32)
    C = b8.muat("val")["ctx"][:256].astype(np.float32)
    torch.onnx.export(model, (torch.tensor(X[:1]), torch.tensor(C[:1])), ONNX,
                      input_names=["window", "konteks"],
                      output_names=["forecast_c", "failure_prob", "time_to_breach_min"],
                      dynamic_axes={k: {0: "batch"} for k in ("window", "konteks", "forecast_c", "failure_prob",
                                                               "time_to_breach_min")},
                      opset_version=17, dynamo=False)
    with torch.no_grad():
        ref = [t.numpy() for t in model(torch.tensor(X), torch.tensor(C))]
    got = ort.InferenceSession(str(ONNX), providers=["CPUExecutionProvider"]).run(None, {"window": X, "konteks": C})
    selisih = max(float(np.abs(a - b).max()) / max(float(np.abs(a).max()), 1.0) for a, b in zip(ref, got, strict=True))
    if selisih > TOLERANSI:
        ONNX.unlink()
        raise SystemExit(f"DITOLAK: ONNX beda dari PyTorch ({selisih:.2e})")
    return selisih


def main():
    import torch

    from bench.experiments.b8 import b8_gru
    from bench.experiments.b8 import b8_lib as b8
    from bench.experiments.b12.b12_shortcut import uji_gangguan
    from ml.training import finetune as ft
    from ml.training.scaler import apply_scaler

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--patience", type=int, default=8)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    t0 = time.perf_counter()

    cfg = json.loads((ROOT / "ml/reports/labels_b3.json").read_text(encoding="utf-8"))["konfigurasi"]
    cfg["patience"] = a.patience
    b8_tr = b8.muat("train")
    data = b8_gru.siapkan(b8_tr, b8.muat("val"), konteks=True, label="y_baru")
    Xa, Ca, jumlah = augmentasi(np.load(ft.TRAIN_PATH)["X"].astype(np.float32), b8_tr["ctx"].astype(np.float32),
                                b8_tr["y_baru"], np.random.default_rng(a.seed))
    data["train"][0] = torch.tensor(apply_scaler(Xa, data["mean"], data["std"]))
    data["train"][5] = torch.tensor(((Ca - data["ctx_mean"]) / data["ctx_std"]).astype(np.float32))
    print("augmentasi:", jumlah, flush=True)

    model, info = b8_gru.latih(data, cfg, a.seed, log=print)
    val = b8_gru.evaluasi(model, data)
    ck = {"state": model.state_dict(), "mean": data["mean"], "std": data["std"], "ctx_mean": data["ctx_mean"],
          "ctx_std": data["ctx_std"], "cfg": cfg, "konteks": True, "augmentasi": AUG}
    torch.save(ck, CKPT)
    paritas = ekspor(model.eval(), ck)
    print(f"val macro F1 {val['macro_f1']:.3f}  PR-AUC {val['anomali_pr_auc']:.3f}  ekspor {rel(ONNX)} "
          f"(paritas {paritas:.1e})", flush=True)

    b12 = uji_gangguan(ONNX, data["ctx_mean"])
    pembanding = json.loads(B12_V5.read_text(encoding="utf-8"))["uji"] if B12_V5.exists() else {}
    hasil = {"waktu_utc": now_iso(), "git": git_info(), "split": "val", "label": "v5", "seed": a.seed,
             "konfigurasi": cfg, "augmentasi": AUG, "jumlah_augmentasi": jumlah, "latih": info,
             "checkpoint": rel(CKPT), "onnx": rel(ONNX), "paritas_onnx": paritas, **val,
             "b12": b12["uji"],
             "b12_v5_tanpa_augmentasi": {k: {"macro_f1": v["macro_f1"], "f1": v["f1"]} for k, v in pembanding.items()},
             "detik_total": round(time.perf_counter() - t0, 1)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    print("Tersimpan:", rel(write_json(OUT, hasil)))


if __name__ == "__main__":
    main()
