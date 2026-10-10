"""Utilitas bersama harness: lokasi berkas, hash, info git, pemanggil perintah, penulis JSON.

Sengaja hanya memakai pustaka standar supaya bisa diimpor sebelum torch (lihat bench/run.py:
CUDA_VISIBLE_DEVICES harus diset sebelum torch di-import).
"""

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH_DIR = ROOT / "bench"
RESULTS_DIR = BENCH_DIR / "results"
DEVICES_DIR = BENCH_DIR / "devices"
DATA_PATH = ROOT / "data" / "processed" / "v4_seed1000_700trips.parquet"

# Dikunci sama di semua device (protokol bagian 5)
SEEDS = [1000, 1001, 1002, 1003, 1004]


def now_iso():
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


def stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def run_cmd(args, timeout=20):
    """Jalankan perintah, kembalikan stdout (str) atau None bila gagal/tidak ada."""
    if not args or shutil.which(args[0]) is None:
        return None
    try:
        r = subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def is_wsl():
    try:
        with open("/proc/version", encoding="utf-8") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


def powershell(command):
    """Jalankan PowerShell di Windows native, atau lewat interop dari WSL. None bila tidak bisa."""
    if sys.platform == "win32":
        exe = "powershell"
    elif is_wsl():
        exe = "powershell.exe"
    else:
        return None
    return run_cmd([exe, "-NoProfile", "-NonInteractive", "-Command", command])


def _git_exe():
    exe = shutil.which("git")
    if exe is None and sys.platform == "win32":
        cand = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "cmd" / "git.exe"
        exe = str(cand) if cand.exists() else None
    return exe


def git_info():
    exe = _git_exe()
    if exe is None:
        return {"commit": None, "branch": None, "dirty": None, "catatan": "git tidak ditemukan"}

    # Repo di disk Windows di-checkout dengan CRLF; git di WSL tanpa autocrlf menganggap SEMUA
    # berkas berubah (dirty palsu). autocrlf=true menormalkan perbandingan tanpa mengubah berkas.
    crlf = ["-c", "core.autocrlf=true"] if is_wsl() else []

    def g(*a):
        try:
            r = subprocess.run([exe, *crlf, "-C", str(ROOT), *a], check=False, capture_output=True, text=True,
                               timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return r.stdout.strip() if r.returncode == 0 else None

    status = g("status", "--porcelain", "--untracked-files=no")
    return {
        "commit": g("rev-parse", "HEAD"),
        "branch": g("rev-parse", "--abbrev-ref", "HEAD"),
        # dirty = ada perubahan pada berkas terlacak; hasil dari pohon kotor tidak bisa diulang persis
        "dirty": None if status is None else bool(status),
    }


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def data_info(path=DATA_PATH):
    path = Path(path)
    if not path.exists():
        return {"path": str(path.relative_to(ROOT)), "sha256": None, "catatan": "berkas tidak ada"}
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)
    return path


def rel(path):
    """Path relatif terhadap root repo (untuk pointer di JSON hasil)."""
    return Path(path).resolve().relative_to(ROOT).as_posix()


def ort_gpu_python():
    """Python di venv ONNX Runtime GPU (CUDA 13) yang terpisah dari venv torch (CUDA 12).

    Bisa diatur lewat COLDTRACK_ORT_PY. None bila tidak ada (mis. di d0-old yang CPU saja).
    """
    cand = os.environ.get("COLDTRACK_ORT_PY") or str(Path.home() / ".venvs" / "coldtrack-ort" / "bin" / "python")
    return cand if Path(cand).exists() else None
