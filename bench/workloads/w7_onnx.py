"""W7 -- inferensi ONNX model proposal: CPU EP vs CUDA EP, batch 1 / 32 / 256 / 1024.

Pengukuran dijalankan bench/ort_bench.py sebagai subprocess:
- CPU EP  : Python venv ini (onnxruntime CPU, versi sama di semua device)
- CUDA EP : venv ORT GPU terpisah (CUDA 13; lihat bench/README.md). EP aktif dicek tiap run;
            bila CUDA EP jatuh ke CPU, run ditandai cuda_ep_aktif=false, bukan disembunyikan.
GRU diukur dengan TF32 bawaan ORT dan dengan use_tf32=0 (TF32 mengubah keluaran ~4e-3 C).

Jeda pendinginan W7 = 15 detik (bukan 60): satu run hanya ~3-20 detik, sehingga 60 detik per
ulangan membuat W7 > 2 jam tanpa manfaat termal; suhu tetap tercatat di telemetri tiap run.
"""

import json
import subprocess
import sys

from bench.common import ROOT, ort_gpu_python
from bench.harness import run_config, tidak_berlaku

COOLDOWN_W7 = 15
BATCHES = [1, 32, 256, 1024]
MODELS = {"gru": "ml/reports/coldtrack.onnx", "xgb_ttb": "ml/reports/coldtrack_ttb.onnx"}
# (nama varian, ep, tf32, model yang relevan)
VARIAN = [
    ("cpu", "cpu", None, ["gru", "xgb_ttb"]),
    ("cuda", "cuda", None, ["gru", "xgb_ttb"]),
    ("cuda_notf32", "cuda", 0, ["gru"]),       # XGB TTB tanpa matmul: TF32 tidak relevan
]


def run(ctx):
    from bench import train_lib as tl

    tl.ensure_windows()
    win = ROOT / "data" / "processed" / "windows" / "windows_val.npz"
    pilih = set(ctx.configs) if ctx.configs else None
    files = []
    for vnama, ep, tf32, models in VARIAN:
        for m in models:
            for b in BATCHES:
                cid = f"{m}_{vnama}_b{b}"
                if pilih and cid not in pilih:
                    continue
                cfg = {"model": MODELS[m], "ep": ep, "tf32": tf32, "batch": b}
                if ep == "cuda" and ctx.device != "cuda":
                    files += tidak_berlaku(ctx, "W7", cid, cfg, "CUDA EP butuh GPU NVIDIA")
                    continue
                if ep == "cpu" and ctx.device == "cuda":
                    print(f"  {cid}: CPU EP diukur di tag *-cpu, bukan di tag gpu")
                    continue
                py = ort_gpu_python() if ep == "cuda" else sys.executable
                if py is None:
                    files += tidak_berlaku(ctx, "W7", cid, cfg, "venv ORT GPU tidak ditemukan")
                    continue
                args = [py, str(ROOT / "bench" / "ort_bench.py"), "--model", str(ROOT / MODELS[m]),
                        "--ep", ep, "--batch", str(b), "--windows", str(win)]
                if tf32 is not None:
                    args += ["--tf32", str(tf32)]
                if ctx.quick:
                    args += ["--min-iters", "20", "--min-seconds", "0.2", "--max-seconds", "2"]

                def satu_run(seed, pemanasan, args=args, py=py):
                    r = subprocess.run(args, check=False, capture_output=True, text=True, timeout=600)
                    if r.returncode != 0:
                        raise RuntimeError(r.stderr[-1500:])
                    hasil = json.loads(r.stdout.strip().splitlines()[-1])
                    return {"python": py, "waktu": {"session_init_s": hasil["session_init_s"],
                                                    "latensi_p50_ms": hasil["latensi_ms"]["p50"]},
                            "inferensi": hasil}

                files += run_config(ctx, "W7", cid, cfg, satu_run, cooldown=0 if ctx.quick else COOLDOWN_W7)
    return files
