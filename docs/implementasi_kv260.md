# Implementasi di KV260: tahap 1, FPGA saja

Rencana dua tahap. Tahap 1 (dokumen ini): skrip Python membuat data per menit, chip di KV260 menghitung dan
menyegelnya, hasilnya dikirim ke cloud lewat MQTT. Tahap 2: sensor analog sungguhan, dibaca dan dikirim oleh ESP32.

Status: skrip dan skenario diuji dengan chip golden (bit-exact dengan RTL). Bitstream, pemuatan di board, dan
`ChipAxi` **belum pernah diuji di board**. Langkah di bagian 2 mengikuti pola dokumentasi AMD Kria dari ingatan,
jadi cocokkan dengan wiki Kria sebelum dijalankan.

## 1. Cek microSD dan Linux

Pasang microSD di laptop. Kartu Kria Ubuntu punya partisi `system-boot` dan `writable`. Kalau kartu kosong atau
isinya lain, tulis image Ubuntu 22.04 untuk Kria KV260 (cari di situs Canonical atau AMD), lalu boot. Akses lewat
Ethernet (SSH), kabel micro-USB serial, atau HDMI dengan keyboard. Login pertama biasanya `ubuntu`/`ubuntu`, lalu
diminta ganti sandi. Board butuh Ethernet ke jaringan yang sama dengan laptop yang menjalankan cloud.

## 2. Pasang bitstream (belum diuji)

Keluaran Vivado ada di `hw/results/vivado/` (`coldtrack_wrapper.bit`, `coldtrack_kv260.xsa`; berkas `*.bit` dan
`*.xsa` tidak ikut git). Desainnya memakai model #8 (`xgb_v5_context_duty`), clock PL 100 MHz, dan chip di
`0xA000_0000` (`hw/synth/kv260_bd.tcl`). Berkas paket ada di `hw/kv260/`.

1. Di mesin yang punya Vivado (Linux atau WSL, setelah `source <Vivado>/settings64.sh`): `hw/kv260/paket.sh`. Skrip ini
   menjalankan `bootgen` untuk mengubah `.bit` menjadi `coldtrack.bit.bin`, lalu mengumpulkan semuanya di
   `hw/kv260/paket/`. Di Windows tanpa WSL, jalankan perintah `bootgen` di komentar skrip.
2. Salin isi `hw/kv260/paket/` ke board (`scp -r`), lalu di board: `./pasang.sh`. Skrip ini mengompilasi overlay
   (`pl.dtsi`, perlu `dtc`), memasang aplikasi ke `/lib/firmware/xilinx/coldtrack/`, dan menjalankan
   `xmutil unloadapp` lalu `xmutil loadapp coldtrack`.

Overlay `pl.dtsi` ditulis tangan dan belum pernah dikompilasi atau dimuat. Kalau `dtc` atau `xmutil` menolaknya, buat
`pl.dtsi` dari `coldtrack_kv260.xsa` dengan device-tree-xlnx (`xsct`, `dt_overlay true`) sebagai gantinya.

## 3. Siapkan board

```bash
sudo apt install python3-numpy python3-yaml python3-paho-mqtt
# salin ke board: hw/ (tanpa hw/build), backend/config.yaml, dan untuk uji lawan golden satu berkas:
#   bench/results/local-cpu/B10/b9_xgb_chip_v5_context_synthetic_duty.json
```

## 4. Uji bertahap di board

```bash
sudo python -m hw.driver.uji_board --hanya-id --chip axi   # ID 0x43540001 dan bit STATUS
sudo python -m hw.driver.uji_board --chip axi              # chip vs golden, semua keluaran identik
sudo python -m hw.driver.fpga_only --skenario hw/driver/skenario/pintu_terbuka.csv --chip axi \
     --kunci <64 hex> --jeda 0 --tanpa-mqtt                # chip + log lokal, tanpa cloud
```

Kalau `uji_board` melaporkan BEDA, cek dulu model di bitstream sebelum mencurigai RTL.

## 5. Kirim ke cloud

Di laptop, isi `.env`: `SIM_SPEED=1` (bawaan 30, jam simulasi), `EDGE_KEYS="DEV-001=<64 hex>"` dengan kunci yang sama
dengan `--kunci`, dan `SIM_LEWATI="B 3036 WN"` supaya simulator tidak ikut memutar truk itu. Jalankan
`docker compose --profile dev up -d`. Di board:

```bash
export MQTT_HOST=<IP laptop> MQTT_USER=simulator MQTT_PASSWORD=<dari .env> API_URL=http://<IP laptop>:8000
sudo -E python -m hw.driver.fpga_only --skenario hw/driver/skenario/reefer_mati.csv --chip axi --kunci <64 hex>
```

Satu sampel per 60 detik. `--jeda` lebih kecil mempercepat demo, tetapi cap waktu bacaan tetap maju 60 detik per
sampel dan bisa melampaui jam dinding. Log lokal tersegel ada di `hw/driver/log/`.

## 6. Skenario data

`python -m hw.driver.skenario --semua` (di laptop) membuat lima CSV di `hw/driver/skenario/`: `normal`,
`pintu_terbuka`, `reefer_mati`, `prapendinginan_buruk`, `sensor_macet`. Suhu kabin memakai model termal sederhana
[SIM], sinyal kompresor memakai fungsi yang sama dengan data latih. Hasil di chip golden:

| Skenario | Status | Diagnosis |
|---|---|---|
| normal | AMAN | A0 (sebagian jendela masalah sensor) |
| pintu_terbuka | WASPADA dari menit 79 | A1 |
| reefer_mati | WASPADA menit 80, KRITIS menit 85 | A3 |
| prapendinginan_buruk | KRITIS sejak menit 0 | A8 |
| sensor_macet | WASPADA dari menit 69 | A1, lalu masalah sensor |

## 7. Batas yang diketahui

- Kecepatan di data latih hanya 0 atau 60 km/j. Nilai lain (mis. 50) membuat diagnosis model selalu A7, jadi skenario
  memakai 60 km/j. Ini juga berlaku saat sensor sungguhan dipakai di tahap 2.
- Kelas `masalah_sensor` dari model bisa muncul pada data normal. Cloud tidak memakainya sebagai label (sensor hanya
  dari aturan sensor).
- Sinyal kompresor (`duty`) di skenario sintetis. Di tahap 2 butuh sensor arus atau kopling.
- Forecast di chip (`PAKAI_RAMALAN`, B14) belum ada di bitstream ini; forecast tetap dari GRU cloud.
- Kunci HMAC di perintah dan `.env` hanya untuk pengembangan. Jangan dipakai untuk produksi.
