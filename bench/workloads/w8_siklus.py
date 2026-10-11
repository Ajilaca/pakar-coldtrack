"""W8 -- siklus worker inferensi end-to-end: 24 / 100 / 500 truk virtual per siklus.

HARNESS berbasis endpoint backend POST /api/v1/analyze (bench/w8_cycle.py), BUKAN worker Fase 3
rencana armada (belum ada). Backend memakai ONNX Runtime CPU, jadi W8 hanya bermakna di jalur CPU;
tag GPU dicatat "tidak berlaku". Varian 2 inti (afinitas CPU) membandingkan dengan acuan PRD:
< 30 detik per siklus untuk 100 truk di VPS 2 vCPU.
"""

import json
import subprocess
import sys

from bench.common import ROOT
from bench.harness import run_config, tidak_berlaku

CONFIGS = [("truk24", 24, 0), ("truk100", 100, 0), ("truk500", 500, 0), ("truk100_2inti", 100, 2)]


def run(ctx):
    files = []
    for cid, n, inti in CONFIGS:
        if ctx.configs and cid not in ctx.configs:
            continue
        cfg = {"truk": n, "inti_cpu": inti or "semua", "harness": "POST /api/v1/analyze via TestClient"}
        if ctx.device == "cuda":
            files += tidak_berlaku(ctx, "W8", cid, cfg, "backend memakai ONNX Runtime CPU; diukur di tag *-cpu")
            continue
        args = [
            sys.executable,
            str(ROOT / "bench" / "w8_cycle.py"),
            "--trucks",
            str(5 if ctx.quick else n),
            "--cycles",
            "1" if ctx.quick else "3",
        ] + (["--cores", str(inti)] if inti else [])

        def satu(seed, pemanasan, args=args):
            r = subprocess.run(args, check=False, capture_output=True, text=True, timeout=3600)
            if r.returncode != 0:
                raise RuntimeError(r.stderr[-1500:])
            h = json.loads(r.stdout.strip().splitlines()[-1])
            return {
                "waktu": {"siklus_median_s": h["siklus_median_s"], "ms_per_truk_median": h["ms_per_truk_median"]},
                "siklus": h,
            }

        files += run_config(ctx, "W8", cid, cfg, satu, cooldown=0 if ctx.quick else 15)
    return files
