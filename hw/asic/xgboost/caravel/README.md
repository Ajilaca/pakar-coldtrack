<!-- SPDX-FileCopyrightText: 2026 Faza Dzil -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ColdTrack di Caravel (sky130A)

Proyek user Caravel untuk chip **ColdTrack**: pemantau rantai dingin yang menjalankan model fisika termal, inferensi
XGBoost (model dibaca dari flash QSPI luar dan diverifikasi tag HMAC-SHA256), dan segel data berantai SHA-256/HMAC.
Inti chip adalah makro `coldtrack_asic` dari repo pakar-coldtrack (`hw/asic/xgboost`, layout RUN_AK), di sini
ditempatkan di `user_project_wrapper` Caravel untuk shuttle ChipFoundry (sky130A, Caravel Lite tag `CC2509`).

> **Kunci HMAC model.** Netlist dan GDS memuat kunci HMAC model yang tertanam di gerbang. Untuk lomba dan verifikasi,
> kunci ini diperlakukan sebagai kunci uji dan dibuka (open source). Tapeout sungguhan wajib memakai kunci baru dan
> mengulang layout makro dari awal (lihat README `hw/asic/xgboost` di pakar-coldtrack).

## Isi wrapper

| Bagian | Keterangan |
|---|---|
| `u_ct` (`coldtrack_asic`) | 2200 x 2200 um, di (360,18; 1098,88), orientasi N; 4 makro DFFRAM RAM256 di dalamnya |
| Glue logic | inverter `io_oeb`/reset, tie cell untuk keluaran yang tidak dipakai |
| `g_clkbuf` | rantai 6 `clkbuf_8` dari `wb_clk_i` (kiri bawah) ke pin clk makro (sisi atas, ~4 mm) |
| Repeater | dipasang resizer pada kabel panjang (reset, IO, `user_irq`) |

Clock dari `wb_clk_i` (target 10 MHz, `CLOCK_PERIOD` 100 ns), reset dari `wb_rst_i` (aktif tinggi, dibalik ke `rst_n`).
Wishbone dan logic analyzer tidak dipakai (keluaran diikat 0). Alarm juga dikirim ke `user_irq[2:0]`.

| mprj_io | Sinyal | Mode GPIO (`user_defines.v`) |
|---|---|---|
| 25 | `spi_sck` | masukan |
| 24 | `spi_cs_n` | masukan |
| 23 | `spi_mosi` | masukan |
| 22 | `spi_miso` (tri-state, `spi_miso_oe`) | dua arah |
| 21 / 20 / 19 | `alarm_waspada` / `alarm_kritis` / `alarm_sensor` | keluaran |
| 18 / 17 | `qspi_sck` / `qspi_cs_n` | keluaran |
| 13..16 | `qspi_io[0..3]` (`qspi_io_oe`) | dua arah |
| 5..12, 26..37 | tidak dipakai | manajemen, masukan |

`user_irq[0..2]` = `alarm_kritis`, `alarm_waspada`, `alarm_sensor`.

## Layout wrapper

LibreLane 3.0.17 (image `ghcr.io/librelane/librelane:3.0.17`), PDK open_pdks `8afc8346` (sama dengan layout makro).
Jalankan `openlane/user_project_wrapper/harden.sh <run_tag>`; view final disalin ke `gds/`, `lef/`, `def/`, `mag/`,
`verilog/gl/`, `spef/`, `lib/`, laporan signoff ke `signoff/user_project_wrapper/`.

Hal yang berbeda dari template:

- **PDN berimpit dengan grid makro.** Makro memakai PDN met4 + met5 (`PDN_MULTILAYER`) dan OBS met5 mengisi celah antar
  strapnya, jadi strap wrapper vccd1/vssd1 dibuat dengan lebar, jarak, pitch, dan offset yang sama dengan grid makro
  (met4 1,6/1,7/153,6 um, met5 1,6/1,7/153,18 um) sehingga jatuh tepat di pin VPWR/VGND makro (`pdn_ct.tcl`). Domain
  vccd2/vdda1/vdda2 hanya lewat core ring. pdngen menghentikan strap 0,6 um (met4) dan 3,2 um (met5) sebelum ujung pin
  makro; `pdn_bridge.tcl` menutup celah itu (120 sambungan) sebelum flow dilanjutkan, sesudahnya PSM: semua shape vccd1
  dan vssd1 tersambung.
- **Baris sel standar dibatasi** (`FP_OBSTRUCTIONS`): hanya pita bawah, kanal kiri, kanal kanan, dan pita atas, karena
  glue logic hanya ~400 sel; tanpa ini fill/tap memenuhi seluruh area (1,4 juta sel) dan Magic kehabisan memori.
- **Clock dibuffer di RTL** (`g_clkbuf`, dont-touch): CTS tidak mengenali pin clk makro sebagai sink.

Hasil signoff (run WR4):

| Pemeriksaan | Hasil |
|---|---|
| DRC Magic / KLayout / route | 0 / 0 / 0 |
| LVS (makro sebagai black box) | lulus |
| XOR | 0 |
| Antena | 0 |
| Slew / cap / fanout | 0 di 9 corner |
| Setup WS / hold WS | +50,23 ns / +4,86 ns |
| Sel standar | 15 buffer, 6 inverter, 222 gerbang, 143 repeater, 1 dioda |

## Precheck

CF Precheck v1.3.7 (`chipfoundry/mpw_precheck`, repo `9ed31213`, image 2026-09-15) dengan PDK open_pdks
`3e0e31dc` (sesuai Makefile), dijalankan lokal 2026-10-31 (57 menit): **13/13 lulus**.

| Pemeriksaan | Hasil | Waktu |
|---|---|---|
| Top Cell | lulus | 1 s |
| GPIO Defines | lulus | 0,5 s |
| XOR | lulus | 100 s |
| KLayout FEOL / BEOL / Offgrid | lulus | 294 / 929 / 188 s |
| KLayout Metal Density / Pin Label / ZeroArea | lulus | 86 / 47 / 6 s |
| Spike Check / Illegal Cellname | lulus | 16 / 4 s |
| LVS (penuh: wrapper + `coldtrack_asic` + RAM256, `lvs/user_project_wrapper/lvs_config.json`) | lulus | 1752 s |
| OEB | lulus | 19 s |

Log lengkap di `precheck_results/`. Cek OEB (CVC) lulus dengan empat peringatan, semuanya sesuai desain:

- GPIO 14 (`qspi_io[1]`) `oeb` selalu 1: perintah flash 0x6B (Fast Read Quad Output) hanya mengemudikan IO0;
  IO1..3 hanya menerima data.
- GPIO 15, 16 (`qspi_io[2..3]`) keluaran tetap 1: WP#/HOLD# ditahan tinggi saat chip mengemudikannya.
- GPIO 22 (`spi_miso`) tanpa masukan: MISO hanya keluaran tri-state; mode dua arah dipakai supaya `oeb` dikendalikan
  `spi_miso_oe`.

## Verifikasi

Verifikasi fungsional dan gate-level ada di pakar-coldtrack (`hw/asic/xgboost/tb`): RTL, GLS netlist final
(Verilator, skenario ujung-ke-ujung identik dengan golden), dan GLS dengan SDF pasca-layout (Icarus). Testbench Caravel
(`verilog/dv`) masih bawaan template dan belum disesuaikan.

## Lisensi

Apache 2.0 (`LICENSE`).
