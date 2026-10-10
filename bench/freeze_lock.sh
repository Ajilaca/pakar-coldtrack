#!/usr/bin/env bash
# Kunci versi paket G16 (jalankan di G16 setelah setup_wsl.sh cuda). d0-old memakai berkas ini.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
{ echo "# Dibangkitkan bench/freeze_lock.sh di G16 -- venv utama (torch cu128 + onnxruntime CPU)"
  uv pip freeze --python "$HOME/.venvs/coldtrack/bin/python"; } > bench/requirements.lock.txt
{ echo "# Dibangkitkan bench/freeze_lock.sh di G16 -- venv ORT GPU (CUDA 13), khusus jalur cuda"
  uv pip freeze --python "$HOME/.venvs/coldtrack-ort/bin/python"; } > bench/requirements-ort-gpu.lock.txt
wc -l bench/requirements*.lock.txt
