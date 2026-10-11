"""B3 -- latensi inferensi CPU EP: model proposal vs kandidat B3 (bench/ort_bench.py, batch 1 & 1024).

Indikasi biaya inferensi kandidat yang lebih besar (hidden 128 x 3 lapis). Bukan bagian W7 resmi;
W7 penuh untuk kandidat dijalankan di B5.

  python -m bench.b3_latensi_kandidat     (jalankan dengan GPU disembunyikan: CPU EP)

Hasil: bench/results/g16-cpu/B3/latensi_kandidat.json
"""

import json
import os
import subprocess
import sys

from bench.common import RESULTS_DIR, ROOT, git_info, now_iso, write_json

MODELS = {"proposal": "ml/reports/coldtrack.onnx", "kandidat_b3": "backend/models/candidates/coldtrack_gru_b3.onnx"}


def main():
    env = os.environ | {"CUDA_VISIBLE_DEVICES": ""}
    win = ROOT / "data" / "processed" / "windows" / "windows_val.npz"
    hasil = {"waktu_utc": now_iso(), "git": git_info(), "ep": "cpu", "model": {}}
    for nama, m in MODELS.items():
        hasil["model"][nama] = {"path": m}
        for b in (1, 1024):
            r = subprocess.run([sys.executable, str(ROOT / "bench" / "ort_bench.py"), "--model", str(ROOT / m),
                                "--ep", "cpu", "--batch", str(b), "--windows", str(win)],
                               check=True, capture_output=True, text=True, env=env)
            hasil["model"][nama][f"b{b}"] = json.loads(r.stdout.strip().splitlines()[-1])
            print(nama, b, hasil["model"][nama][f"b{b}"]["latensi_ms"])
    print("Tersimpan:", write_json(RESULTS_DIR / "g16-cpu" / "B3" / "latensi_kandidat.json", hasil))


if __name__ == "__main__":
    main()
