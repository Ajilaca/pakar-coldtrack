"""Satu pengukuran siklus inferensi W8 (dijalankan sebagai subprocess dengan cwd = backend/).

HARNESS, BUKAN worker Fase 3 rencana armada (belum ada): satu siklus = N truk virtual masing-masing
mengirim jendela 60 bacaan ke POST /api/v1/analyze lewat TestClient (pydantic -> preprocess ->
ONNX GRU + TTB -> aturan), berurutan. Payload = 5 skenario demo backend, diputar untuk N truk.

  python bench/w8_cycle.py --trucks 100 --cycles 3 [--cores 2]

Keluaran: satu baris JSON.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trucks", type=int, required=True)
    ap.add_argument("--cycles", type=int, default=3)
    ap.add_argument("--cores", type=int, default=0, help="batasi afinitas CPU (emulasi VPS n vCPU); 0 = semua")
    a = ap.parse_args()
    if a.cores:
        os.sched_setaffinity(0, set(range(a.cores)))
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    payloads = []
    for p in sorted((BACKEND / "data" / "scenarios").glob("*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        r = s["readings"]
        while len(r) < 60:
            r = [r[0]] + r
        payloads.append({"cargo_profile": s.get("cargo_profile", "vaksin_2_8C"), "readings": r[-60:]})

    def satu_siklus():
        t0 = time.perf_counter()
        status = {}
        for k in range(a.trucks):
            p = payloads[k % len(payloads)]
            res = client.post("/api/v1/analyze", json={"shipment_id": f"TRK-{k:04d}", **p})
            if res.status_code != 200:
                raise RuntimeError(f"HTTP {res.status_code}: {res.text[:200]}")
            st = res.json()["status"]
            status[st] = status.get(st, 0) + 1
        return time.perf_counter() - t0, status

    satu_siklus()  # pemanasan (muat model, JIT ORT)
    hasil = [satu_siklus() for _ in range(a.cycles)]
    det = sorted(h[0] for h in hasil)
    print(
        json.dumps(
            {
                "trucks": a.trucks,
                "cores": a.cores or os.cpu_count(),
                "cycles": a.cycles,
                "siklus_s": det,
                "siklus_median_s": det[len(det) // 2],
                "ms_per_truk_median": det[len(det) // 2] / a.trucks * 1000,
                "status_siklus_terakhir": hasil[-1][1],
            }
        )
    )


if __name__ == "__main__":
    main()
