"""Uji A/B kode backend untuk W8: dua commit dijalankan bergantian di mesin yang sama (jalur CPU).

  CUDA_VISIBLE_DEVICES= python -m bench.w8_ab_kode --a fd61a98 --b 5d13490 --ulang 3 --truk 100

Tujuan: mengukur efek perbedaan kode backend (bukan device) pada W8, karena d0-old menjalankan B5 di commit
fd61a98 sedangkan G16 di 5d13490. Tiap commit di-checkout ke git worktree sementara; bench/w8_cycle.py dari
commit itu sendiri yang dijalankan. Urutan bergantian A, B, A, B, ... agar kondisi termal terbagi rata.
Hasil: bench/results/<tag>/W8_ab_kode/ab.json
"""

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

from bench.common import RESULTS_DIR, ROOT, now_iso
from bench.env_capture import cpu_info, git_info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="commit A (mis. commit run d0-old)")
    ap.add_argument("--b", required=True, help="commit B (mis. commit run G16)")
    ap.add_argument("--ulang", type=int, default=3)
    ap.add_argument("--truk", type=int, default=100)
    ap.add_argument("--siklus", type=int, default=5)
    ap.add_argument("--tag", default="g16-cpu")
    a = ap.parse_args()

    hasil = {a.a: [], a.b: []}
    status = {}
    with tempfile.TemporaryDirectory() as tmp:
        wt = {}
        for c in (a.a, a.b):
            wt[c] = Path(tmp) / c
            subprocess.run(["git", "worktree", "add", "--detach", "-f", str(wt[c]), c], cwd=ROOT, check=True,
                           capture_output=True)
        try:
            for i in range(a.ulang):
                for c in (a.a, a.b):
                    r = subprocess.run([sys.executable, str(wt[c] / "bench" / "w8_cycle.py"), "--trucks", str(a.truk),
                                        "--cycles", str(a.siklus)], capture_output=True, text=True, check=True)
                    h = json.loads(r.stdout.strip().splitlines()[-1])
                    hasil[c].append(h["siklus_median_s"])
                    status[c] = h["status_siklus_terakhir"]
                    print(f"ulang {i + 1} {c}: {h['siklus_median_s']:.3f} s", flush=True)
        finally:
            for c in (a.a, a.b):
                subprocess.run(["git", "worktree", "remove", "--force", str(wt[c])], cwd=ROOT, check=False,
                               capture_output=True)

    med = {c: statistics.median(v) for c, v in hasil.items()}
    out = {
        "workload": "W8", "uji": "A/B kode backend, mesin sama", "tag": a.tag, "waktu_utc": now_iso(),
        "git_runner": git_info(), "cpu": cpu_info(), "truk": a.truk, "siklus_per_run": a.siklus, "ulang": a.ulang,
        "urutan": "bergantian A,B per ulangan",
        "commit_a": a.a, "commit_b": a.b,
        "siklus_median_s": hasil, "median": med,
        "rasio_b_per_a": med[a.b] / med[a.a],
        "status_identik": status[a.a] == status[a.b], "status": status,
    }
    p = RESULTS_DIR / a.tag / "W8_ab_kode" / "ab.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"rasio B/A = {out['rasio_b_per_a']:.3f}; tersimpan {p.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
