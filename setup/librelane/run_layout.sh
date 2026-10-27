#!/usr/bin/env bash
# Layout penuh coldtrack_spi (RTL -> GDS) dengan LibreLane mode dockerized, PDK sky130A, sky130_fd_sc_hd.
# Template: belum pernah dijalankan. Jalankan hanya setelah
# keputusan memori dan pin diambil. Hasil di setup/librelane/runs/RUN_<waktu>/final/. Jalankan dari root repo.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
CFG=setup/librelane/config.json
HASH=$(cat hw/model/xgb_v5_context_duty/flash.sha256)
if ! grep -q "HASH_MODEL=256'h$HASH" "$CFG"; then
    echo "HASH_MODEL di $CFG tidak sama dengan hw/model/xgb_v5_context_duty/flash.sha256 ($HASH)."
    echo "Perbarui config dulu; chip dengan hash basi akan menolak model di flash."
    exit 1
fi

.venv/bin/python -m librelane --dockerized "$CFG"
