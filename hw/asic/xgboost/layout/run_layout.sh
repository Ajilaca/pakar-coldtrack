#!/usr/bin/env bash
# Layout coldtrack_asic (RTL -> GDS) dengan LibreLane mode dockerized, PDK sky130A, sky130_fd_sc_hd, dan 4 makro SRAM
# sky130_sram_1kbyte_1rw1r_32x256_8 untuk ring buffer. Hasil di hw/asic/xgboost/layout/runs/RUN_<waktu>/final/.
# Jalankan dari root repo setelah setup/wsl/02_librelane.sh. Argumen tambahan diteruskan ke LibreLane
# (mis. --to Yosys.Synthesis untuk sintesis saja, atau --last-run --from <langkah> untuk melanjutkan).
#
# Kunci HMAC model (KUNCI_MODEL, lihat hw/asic/xgboost/rtl/model_flash.sv) dibaca dari $CT_KUNCI_MODEL, bawaan
# ~/.coldtrack/kunci_model.hex (buat sekali: python -m hw.asic.xgboost.golden.flash_tag --buat-kunci). Kunci tidak ditulis ke
# config.json; config sementara berisi kunci dibuat di folder ini selama run lalu dihapus. Netlist, GDS, dan folder
# runs/ tetap memuat kunci, jadi jangan dibagikan sembarangan.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
CFG=hw/asic/xgboost/layout/config.json
KUNCI_BERKAS=${CT_KUNCI_MODEL:-$HOME/.coldtrack/kunci_model.hex}
if [ ! -r "$KUNCI_BERKAS" ]; then
    echo "Berkas kunci model $KUNCI_BERKAS tidak ada. Buat sekali dengan:"
    echo "  .venv/bin/python -m hw.asic.xgboost.golden.flash_tag --buat-kunci"
    exit 1
fi
KUNCI=$(tr -d ' \r\n' < "$KUNCI_BERKAS")
if ! [[ $KUNCI =~ ^[0-9a-fA-F]{64}$ ]] || [[ $KUNCI =~ ^0+$ ]]; then
    echo "Isi $KUNCI_BERKAS harus 64 digit hex dan tidak nol."
    exit 1
fi

# di folder yang sama dengan config.json supaya path dir:: dan folder runs/ tetap sama
CFG_KUNCI=hw/asic/xgboost/layout/.config_kunci.json
trap 'rm -f "$CFG_KUNCI"' EXIT
(umask 077; python3 - "$CFG" "$CFG_KUNCI" "$KUNCI" <<'EOF'
import json, sys
cfg = json.load(open(sys.argv[1]))
cfg["SYNTH_PARAMETERS"] = [f"KUNCI_MODEL=256'h{sys.argv[3].lower()}"]
json.dump(cfg, open(sys.argv[2], "w"), indent=2)
EOF
)

.venv/bin/python -m librelane --dockerized "$@" "$CFG_KUNCI"
