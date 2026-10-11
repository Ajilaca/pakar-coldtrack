#!/usr/bin/env bash
# Siapkan lingkungan benchmark di WSL2 Ubuntu (atau Linux lain). Jalankan dari root repo:
#   bash bench/setup_wsl.sh cuda    # G16 (RTX 5070, butuh CUDA 12.8+)
#   bash bench/setup_wsl.sh cpu     # d0-old / device tanpa CUDA
# Venv dibuat di sistem berkas Linux (~/.venvs/coldtrack), bukan di /mnt/c, supaya import cepat.
set -euo pipefail

JALUR="${1:?pakai: bash bench/setup_wsl.sh cuda|cpu}"
VENV="${COLDTRACK_VENV:-$HOME/.venvs/coldtrack}"

if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

[ -x "$VENV/bin/python" ] || uv venv --python 3.11 "$VENV"
PY="$VENV/bin/python"

LOCK="bench/requirements.lock.txt"
# Versi torch dikunci dari lock G16 (tanpa sufiks +cu128/+cpu) agar semua device sama
TORCH="torch"
[ -f "$LOCK" ] && TORCH="torch==$(grep -E '^torch==' "$LOCK" | sed -E 's/^torch==([^+]+).*/\1/')"
if [ "$JALUR" = "cuda" ]; then
    uv pip install --python "$PY" "$TORCH" --index-url https://download.pytorch.org/whl/cu128
else
    uv pip install --python "$PY" "$TORCH" --index-url https://download.pytorch.org/whl/cpu
fi
# Venv utama memakai onnxruntime (CPU) yang SAMA di semua device, supaya W7 CPU EP membandingkan
# biner identik. onnxruntime-gpu hanya di venv ORT terpisah (jalur cuda, lihat bawah).
ORT=onnxruntime

if [ -f "$LOCK" ]; then
    # Samakan versi dengan G16 (torch & onnxruntime dikunci terpisah karena paketnya beda per jalur)
    grep -viE '^(torch|onnxruntime|onnxruntime-gpu|nvidia-|triton)' "$LOCK" > /tmp/coldtrack_lock.txt
    uv pip install --python "$PY" -r /tmp/coldtrack_lock.txt
else
    uv pip install --python "$PY" -r bench/requirements.txt
fi
# backend/requirements.txt memuat `onnxruntime` (CPU). Paket itu dan onnxruntime-gpu berbagi modul
# yang sama, jadi yang terpasang belakangan menimpa yang lain -> buang dari daftar backend, lalu
# pasang varian ORT yang benar paling akhir.
grep -viE '^onnxruntime' backend/requirements.txt > /tmp/coldtrack_backend.txt
uv pip install --python "$PY" -r /tmp/coldtrack_backend.txt
uv pip uninstall --python "$PY" onnxruntime onnxruntime-gpu 2>/dev/null || true
uv pip install --python "$PY" "$ORT"
"$PY" -c "import onnxruntime as o; print('ONNX Runtime EP:', o.get_available_providers())"

# Jalur cuda: venv ORT GPU TERPISAH. onnxruntime-gpu 1.31 butuh CUDA 13, torch cu128 memakai CUDA 12;
# pustaka CUDA 13 di venv torch menimpa libcudnn.so.9 milik torch (terbukti 2026-10-10).
if [ "$JALUR" = "cuda" ]; then
    ORT_VENV="${COLDTRACK_ORT_VENV:-$HOME/.venvs/coldtrack-ort}"
    [ -x "$ORT_VENV/bin/python" ] || uv venv --python 3.11 "$ORT_VENV"
    uv pip install --python "$ORT_VENV/bin/python" "onnxruntime-gpu[cuda,cudnn]==$("$PY" -c 'import onnxruntime as o; print(o.__version__)')" numpy
    "$ORT_VENV/bin/python" -c "import onnxruntime as o; o.preload_dlls(cuda=True, cudnn=True, msvc=False); print('venv ORT GPU EP:', o.get_available_providers())"
fi

echo
echo "Selesai. Aktifkan dengan: source $VENV/bin/activate"
