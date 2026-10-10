"""Ukur inferensi ONNX Runtime untuk satu konfigurasi (model x EP x batch). Hanya butuh numpy +
onnxruntime, supaya bisa dijalankan di venv utama (CPU EP) maupun venv ORT GPU (CUDA EP) dengan
kode pengukuran yang SAMA. Dipanggil oleh bench/workloads/w7_onnx.py.

  python bench/ort_bench.py --model M.onnx --ep cpu|cuda [--tf32 0|1] --batch 32 --windows V.npz

Keluaran: satu baris JSON di stdout.
- latensi per panggilan sess.run (masukan NumPy di host, jadi CUDA EP ikut menanggung salin
  host<->device, sama seperti pemakaian nyata di backend)
- kualitas pada SELURUH split val (tidak diukur waktunya) untuk cek paritas antar-EP
"""

import argparse
import json
import time

import numpy as np

SENTINEL = 999.0


def kualitas(sess, d, bs=4096):
    X = d["X"].astype(np.float32)
    outs = None
    for i in range(0, len(X), bs):
        o = sess.run(None, {"window": X[i:i + bs]})
        outs = [[*a, b] for a, b in zip(outs, o)] if outs else [[b] for b in o]
    outs = {n.name: np.concatenate(v) for n, v in zip(sess.get_outputs(), outs)}
    q = {}
    msk = d["y_ttb"] != SENTINEL
    y = d["y_ttb"][msk]
    if "time_to_breach_min" in outs:
        p = np.ravel(outs["time_to_breach_min"])[msk]
        q["ttb_mae_semua_menit"] = float(np.abs(p - y).mean())
        q["ttb_mae_le30_menit"] = float(np.abs(p[y <= 30] - y[y <= 30]).mean())
    if "forecast_c" in outs:
        q["forecast_t30_mae_c"] = float(np.abs(outs["forecast_c"][:, 1] - d["y_forecast"][:, 1]).mean())
    if "failure_prob" in outs:
        q["akurasi_mode"] = float((outs["failure_prob"].argmax(1) == d["y_mode"]).mean())
    return q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--ep", choices=["cpu", "cuda"], required=True)
    ap.add_argument("--tf32", type=int, default=None, help="hanya cuda; None = bawaan ORT")
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--windows", required=True)
    ap.add_argument("--warmup-iters", type=int, default=20)
    ap.add_argument("--min-iters", type=int, default=300)
    ap.add_argument("--min-seconds", type=float, default=3.0)
    ap.add_argument("--max-seconds", type=float, default=20.0)
    a = ap.parse_args()

    import onnxruntime as ort

    if a.ep == "cuda":
        ort.preload_dlls(cuda=True, cudnn=True, msvc=False)
        opts = {} if a.tf32 is None else {"use_tf32": a.tf32}
        providers = [("CUDAExecutionProvider", opts), "CPUExecutionProvider"]
    else:
        providers = ["CPUExecutionProvider"]

    d = np.load(a.windows)
    t0 = time.perf_counter()
    sess = ort.InferenceSession(a.model, providers=providers)
    init_s = time.perf_counter() - t0
    aktif = sess.get_providers()

    x = d["X"][:a.batch].astype(np.float32)
    feed = {sess.get_inputs()[0].name: x}
    for _ in range(a.warmup_iters):
        sess.run(None, feed)

    lat = []
    t_start = time.perf_counter()
    while True:
        t0 = time.perf_counter_ns()
        sess.run(None, feed)
        lat.append((time.perf_counter_ns() - t0) / 1e6)
        el = time.perf_counter() - t_start
        if (len(lat) >= a.min_iters and el >= a.min_seconds) or el >= a.max_seconds:
            break
    lat = np.array(lat)
    p50 = float(np.percentile(lat, 50))
    print(json.dumps({
        "onnxruntime": ort.__version__,
        "ep_diminta": a.ep, "tf32": a.tf32, "providers_aktif": aktif,
        "cuda_ep_aktif": aktif[0] == "CUDAExecutionProvider",
        "batch": a.batch, "n_iter": len(lat), "session_init_s": init_s,
        "latensi_ms": {"p50": p50, "p95": float(np.percentile(lat, 95)), "p99": float(np.percentile(lat, 99)),
                       "mean": float(lat.mean()), "min": float(lat.min())},
        "throughput_jendela_per_s": a.batch / (p50 / 1000),
        "kualitas_val": kualitas(sess, d),
    }))


if __name__ == "__main__":
    main()
