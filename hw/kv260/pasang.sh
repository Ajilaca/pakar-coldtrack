#!/usr/bin/env bash
# Jalankan di KV260 (Ubuntu Kria) dari folder berisi coldtrack.bit.bin, pl.dtsi, dan shell.json (hasil paket.sh).
# Membuat overlay, memasang aplikasi ke /lib/firmware/xilinx/coldtrack, lalu memuatnya dengan xmutil.
set -euo pipefail
cd "$(dirname "$0")"
APP=coldtrack
DEST=/lib/firmware/xilinx/$APP
command -v xmutil >/dev/null || { echo "xmutil tidak ada: ini bukan image Kria Ubuntu?" >&2; exit 1; }
command -v dtc >/dev/null || sudo apt-get install -y device-tree-compiler
dtc -@ -I dts -O dtb -o $APP.dtbo pl.dtsi
sudo mkdir -p "$DEST"
sudo cp $APP.bit.bin $APP.dtbo shell.json "$DEST/"
sudo xmutil unloadapp || true
sudo xmutil loadapp $APP
sudo xmutil listapps
echo "Selesai. Cek chip: sudo python -m hw.driver.uji_board --hanya-id --chip axi"
