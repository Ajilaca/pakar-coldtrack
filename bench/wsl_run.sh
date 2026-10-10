#!/usr/bin/env bash
# Pembungkus: jalankan perintah di venv benchmark WSL dari root repo.
#   wsl -e bash bench/wsl_run.sh python -m bench.run --tag g16-gpu --workloads smoke
set -euo pipefail
cd "$(dirname "$0")/.."
source "${COLDTRACK_VENV:-$HOME/.venvs/coldtrack}/bin/activate"
exec "$@"
