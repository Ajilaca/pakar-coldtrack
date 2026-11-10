#!/usr/bin/env bash
# Jalankan di mesin ber-Vivado (Linux atau WSL; source <Vivado>/settings64.sh dulu): .bit -> .bit.bin untuk KV260.
# Hasil di hw/kv260/paket/: coldtrack.bit.bin, pl.dtsi, shell.json, pasang.sh. Salin seluruh isinya ke board.
#   ./paket.sh [berkas.bit]          bawaan ../results/vivado/coldtrack_wrapper.bit
# Di Windows tanpa WSL: salin .bit ke folder kerja sebagai coldtrack.bit, lalu jalankan
#   bootgen -w -arch zynqmp -image coldtrack.bif -process_bitstream bin
set -euo pipefail
cd "$(dirname "$0")"
BIT=${1:-../results/vivado/coldtrack_wrapper.bit}
command -v bootgen >/dev/null || { echo "bootgen tidak ditemukan: source settings64.sh Vivado dulu" >&2; exit 1; }
[ -f "$BIT" ] || { echo "bitstream tidak ada: $BIT" >&2; exit 1; }
rm -rf paket && mkdir paket
cp "$BIT" paket/coldtrack.bit
cp coldtrack.bif pl.dtsi shell.json pasang.sh paket/
(cd paket && bootgen -w -arch zynqmp -image coldtrack.bif -process_bitstream bin)
rm paket/coldtrack.bit paket/coldtrack.bif
ls -l paket
