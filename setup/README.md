# setup/: layout ASIC di laptop Windows (WSL2)

Panduan dari Windows kosong sampai siap menjalankan layout `coldtrack_spi` (RTL ke GDS) dengan LibreLane. Ditulis
untuk ASUS ROG Strix G16 (16 GB RAM), tapi berlaku untuk laptop Windows lain dengan WSL2. Hanya layout: tidak ada
simulasi RTL atau estimasi luas terpisah di sini. LibreLane mode Docker sudah membawa Yosys, OpenROAD, Magic,
KLayout, dan PDK sky130, jadi tidak ada tool EDA lain yang dipasang.

| Langkah | Berkas | Lama kira-kira |
|---|---|---|
| 1. WSL2, `.wslconfig`, Docker Desktop | `windows/install_wsl.ps1`, `windows/wslconfig.example` | 20 menit + restart |
| 2. Clone repo di dalam WSL | perintah di bawah | 2 menit |
| 3. Paket sistem Ubuntu | `wsl/01_system_packages.sh` | 3 menit |
| 4. LibreLane + smoke test | `wsl/02_librelane.sh` | 15 sampai 30 menit (unduh image Docker dan PDK) |
| 5. Layout | `librelane/config.json`, `librelane/run_layout.sh` | belum pernah dijalankan |

Kebutuhan: Windows 10 versi 2004 (build 19041) atau Windows 11, RAM 16 GB (minimal 8 GB), ruang disk kosong
sekitar 20 GB.

## Spesifikasi ASIC (yang dilayout)

Top yang dilayout adalah `coldtrack_spi` dengan `MODEL_FLASH=1` (`hw/rtl/coldtrack_spi.sv`). Semua angka di bawah
berasal dari RTL, simulasi, dan hasil Vivado di repo ini. **Luas die, jumlah gate, dan timing pada SKY130 belum
pernah diukur**: sintesis Yosys + SKY130 di laptop 8 GB belum selesai (satu modul masih berjalan lebih dari 18
menit), jadi tidak ada angka luas di dokumen ini.

```
MCU ──SPI 4 pin──► spi_axil_bridge ──AXI4-Lite──► coldtrack_top ──QSPI 6 pin──► flash eksternal (bobot pohon)
                                                     ├─ seal         rantai SHA-256 + HMAC
                                                     ├─ physics      status AMAN/WASPADA/KRITIS + TTB
                                                     ├─ features     ring buffer 256 menit -> 82 fitur bulat
                                                     └─ model_flash  baca flash, hash SHA-256 image, XGBoost 420 pohon
```

| Aspek | Nilai |
|---|---|
| Fungsi | Segel data sensor, status + TTB dari mesin fisika, diagnosis 7 kelas (XGBoost 420 pohon), alarm sopir |
| Clock | satu clock `clk`; target awal 50 MHz (`CLOCK_PERIOD` 20 ns). Di FPGA lolos 100 MHz (WNS +1,430 ns, Vivado OOC) |
| Reset | `rst_n` asinkron, aktif rendah |
| Frekuensi sampel | satu sampel per menit; satu inferensi 316.313 siklus (sekitar 6,3 ms pada 50 MHz) |
| Pin sinyal | `clk`, `rst_n`; SPI: `spi_sck`, `spi_cs_n`, `spi_mosi`, `spi_miso` (+ `spi_miso_oe`); QSPI: `qspi_sck`, `qspi_cs_n`, `qspi_io[3:0]` (masing-masing `_o`, `_oe`, `_i`; pad tiga keadaan di luar RTL); alarm: `alarm_waspada`, `alarm_kritis`, `alarm_sensor` |
| Antarmuka host | SPI mode 0, MSB dulu, frame tulis 6 byte dan baca 7 byte (`hw/golden/spi_frame.py`). SCK paling cepat clk/8; simulasi bebas kesalahan sampai clk/3 |
| Register map | sama dengan KV260 (`hw/golden/regmap.py`), lewat AXI4-Lite internal |
| Flash | perintah 0x6B (Fast Read Quad Output), mode SPI 0, mulai alamat 0, bit QE flash harus sudah 1. SCK flash = clk/2 pada `SETENGAH_SCK=1`, jadi 25 MHz pada clk 50 MHz; cek datasheet flash |
| Image flash | 78.714 byte (model dengan duty), 80.172 byte (tanpa duty); format di `hw/golden/flash_image.py` |
| Keamanan model | SHA-256 image dihitung tiap inferensi dan dibandingkan dengan `HASH_MODEL` yang ditanam saat sintesis (dicek dua kali sebagai pola 8 bit). Model tidak sah: diagnosis dibuang, status fisika, alarm, dan segel tetap jalan |
| Kunci HMAC | diisi lewat SPI lalu dikunci (`kunci_kunci`). Tidak ada OTP/eFuse di desain ini |

### Memori

| Memori | Ukuran | Jenis |
|---|---|---|
| Ring buffer `features` | 256 x 111 bit (3,5 KiB) | RAM tulis, baca sinkron dua register |
| Tabel fitur `tree_stream` | 82 x 48 bit (0,5 KiB) | RAM tulis, dibaca asinkron |
| Tabel K SHA-256 (dua inti) dan konstanta fisika | sekitar 0,5 KiB | ROM konstanta |

Total RAM tulis 3,9 KiB (turun dari 81,5 KiB di mode BRAM karena bobot pohon pindah ke flash). Tidak ada primitif
vendor; di ASIC memori tadi menjadi flip-flop kecuali diganti makro. Satu makro tersedia di PDK sky130 lokal:
`sky130_sram_1kbyte_1rw1r_32x256_8` (32 bit x 256, 479,78 x 397,5 um, sekitar 0,19 mm2). Ring buffer 111 bit
butuh 4 makro (128 bit) atau sekitar 0,76 mm2, dan tetap perlu pembungkus kecil serta tes ulang.

### Sebagai pembanding: hasil FPGA (mode BRAM, bukan ASIC)

Vivado KV260 post-route, 100 MHz, `MODEL_FLASH=0`: 11.802 LUT, 18.221 FF, 20 BRAM36, 74 DSP, daya PL 0,406 W.
Di ASIC 74 DSP menjadi pengali sel standar (pengali lebar di `physics` dan `features`); mode flash menghapus
18 dari 20 BRAM, tapi menambah inti SHA-256 kedua, pembaca QSPI, dan evaluator pohon.

### Status verifikasi RTL

12 tes cocotb di `hw/tb/` lolos (dijalankan berurutan): inti SHA-256 dan SHA-256 aliran identik `hashlib`,
mesin fisika dan fitur identik model golden bit per bit, top ASIC lewat SPI 150 menit identik golden termasuk
image flash yang dirusak dan frame SPI yang terputus. Detail di `hw/README.md`.

## 1. Windows: WSL2 dan Docker Desktop

PowerShell **sebagai Administrator**:

```powershell
wsl --install -d Ubuntu-24.04
```

Atau `powershell -ExecutionPolicy Bypass -File setup\windows\install_wsl.ps1` bila repo sudah ada di Windows
(sekaligus membuat `.wslconfig`). Batas memori WSL, di `%UserProfile%\.wslconfig`:

```
[wsl2]
memory=12GB
swap=8GB
```

Restart Windows, buka **Ubuntu 24.04** dari Start menu, buat user Linux, lalu cek dari PowerShell:

```powershell
wsl --list --verbose          # Ubuntu-24.04 harus VERSION 2
```

Pasang **Docker Desktop for Windows**: centang *Use WSL 2 instead of Hyper-V*, aktifkan *Start Docker Desktop when
you log in*, dan di Resources > WSL Integration aktifkan Ubuntu-24.04. LibreLane hanya mendukung Docker lewat
WSL2; VirtualBox mengganggu jalannya.

## 2. Clone repo di dalam WSL

Simpan repo di sistem berkas Linux (`~`), bukan di `/mnt/c/...`. Akses disk Windows dari WSL jauh lebih lambat.

```bash
mkdir -p ~/FPGA/Projects/Coldtrack && cd ~/FPGA/Projects/Coldtrack
git clone https://github.com/Ajilaca/pakar-coldtrack.git
cd pakar-coldtrack
git switch setup
```

## 3 dan 4. Paket sistem dan LibreLane

Dari root repo, satu per satu (Docker Desktop harus sudah menyala):

```bash
bash setup/wsl/01_system_packages.sh
bash setup/wsl/02_librelane.sh
```

Versi: LibreLane 3.0.17 (PyPI). Smoke test selesai tanpa galat berarti LibreLane siap.

## 5. Layout

`librelane/config.json` adalah titik awal untuk `coldtrack_spi`: mode flash, clock 20 ns (50 MHz), utilisasi core
40 %, `HASH_MODEL` dari `hw/model/xgb_v5_context_duty/flash.sha256`. **Belum pernah dijalankan.** Sebelum layout:

1. putuskan ring buffer `features`: flip-flop (bawaan), makro SRAM `sky130_sram_1kbyte_1rw1r_32x256_8` x4, atau PSRAM;
2. pilih shuttle dan batas luasnya;
3. tambahkan pad I/O dan penempatan pin sesuai shuttle.

```bash
bash setup/librelane/run_layout.sh
```

Hasil di `runs/RUN_<waktu>/`, tiap langkah punya subfolder dan hasil akhir ada di `final/`. Lihat layout:

```bash
.venv/bin/python -m librelane --dockerized --last-run --flow openinklayout setup/librelane/config.json
```

`run_layout.sh` menolak jalan bila `HASH_MODEL` di config berbeda dari `flash.sha256`. Kalau Yosys bawaan gagal
membaca SystemVerilog, tambahkan `"USE_SLANG": true` di config. Pengali lebar di `physics` dan `features` membuat
sintesis lama (satu core per modul); di laptop 8 GB satu modul sudah lebih dari 18 menit.

### Keputusan yang belum diambil sebelum layout

| Keputusan | Opsi | Catatan |
|---|---|---|
| Ring buffer `features` | flip-flop (bawaan), 4 makro SRAM, atau PSRAM di bus QSPI | PSRAM menambah 1 pin CS tapi riwayat sensor keluar chip. Makro SRAM butuh pembungkus dan tes ulang |
| Pengali lebar | pengali penuh (bawaan), atau diserialkan (1 sampai 2 pengali dipakai bergantian) | Latency longgar (satu sampel per menit), jadi serial aman; mengubah RTL berarti tes ulang |
| Inti SHA-256 | dua inti (bawaan), atau satu inti dibagi `seal` dan `model_flash` | Dibagi menghemat luas, tapi menyentuh `seal` yang sudah terverifikasi |
| Kunci HMAC | diisi lewat SPI saat boot (bawaan) | Klaim "terkunci" melemah tanpa OTP; cukup dicatat sebagai keterbatasan, atau cari jalan lain |
| Pembaruan model | hash tertanam (bawaan) | Model bisa diganti di lapangan hanya dengan tanda tangan digital, yang belum dibuat |
| Shuttle dan PDK | SKY130 (sekarang), GF180MCU, atau IHP SG13G2 | Menentukan batas luas, jumlah pin, dan makro SRAM yang tersedia |

### Yang masih harus ditambahkan untuk layout

- Penempatan pin dan pad I/O sesuai shuttle (belum ada); pad tiga keadaan untuk `qspi_io` dan `spi_miso`.
- Batasan timing (clock 50 MHz sudah di `config.json`; periode SCK SPI/QSPI diturunkan dari `clk`, bukan clock sendiri).
- Penentuan ukuran die: `FP_CORE_UTIL` bawaan 50 %, di sini 40 %. Alternatifnya `FP_SIZING` absolut dengan
  `DIE_AREA`. Kepadatan penempatan (`PL_TARGET_DENSITY_PCT`) kalau tidak diisi = `FP_CORE_UTIL + 5 * GPL_CELL_PADDING + 10`.
- Opsi sintesis yang relevan di config: `SYNTH_STRATEGY` (AREA 0..3 atau DELAY 0..4), `SYNTH_HIERARCHY_MODE`
  (`flatten`, `deferred_flatten`, `keep`), `USE_SLANG` untuk parser SystemVerilog lain.

### Urutan flow LibreLane (umum, sesuai dokumentasi)

Sintesis (Yosys) → floorplan → placement → CTS → routing → signoff (DRC, LVS, STA). Tiap langkah punya subfolder di
`runs/RUN_<waktu>/`, hasil akhir di `final/`. Setelah tiap run, cek laporan luas dan timing sebelum lanjut ke
iterasi berikutnya; satu run penuh di laptop 16 GB sebaiknya dijalankan sendirian, tanpa aplikasi berat lain.

## Masalah umum

| Gejala | Penyebab dan solusi |
|---|---|
| Docker tidak terjangkau dari WSL, atau `permission denied` | Docker Desktop belum menyala, atau WSL Integration untuk Ubuntu-24.04 belum aktif |
| Proses mati tiba-tiba saat layout | Memori WSL habis: naikkan `memory` di `.wslconfig`, lalu `wsl --shutdown` dari PowerShell |
| Semua langkah sangat lambat | Repo ada di `/mnt/c/...`; clone ulang di `~` |
