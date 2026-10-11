#!/usr/bin/env bash
# Jalankan perintah frontend di WSL dengan Node lokal (~/.local/node). Contoh: bash bench/fe.sh npm run build
set -euo pipefail
export PATH="$HOME/.local/node/bin:$PATH"
cd "$(dirname "$0")/../frontend"
exec "$@"
