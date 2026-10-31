# hw/asic/xgboost: versi ASIC (layout SKY130)

Folder ini berisi modul pengganti untuk chip ASIC. RTL FPGA di `hw/rtl` tidak diubah. Nama dan antarmuka modul
pengganti sama dengan versi FPGA, jadi versi yang dipakai cukup dipilih lewat daftar berkas.

| Berkas | Isi |
|---|---|
| `rtl/ring_sram.sv` | Pembungkus ring buffer 256 × 111 bit dari 4 makro DFFRAM `RAM256` (32 bit × 256, latch, 1RW) |
| `rtl/features.sv` | Pengganti `hw/rtl/features.sv`: array `mem` diganti `ring_sram`, 13 pengkuadrat paralel diganti 1 pengkuadrat bergiliran |
| `ram256/` | View makro DFFRAM hasil harden (GDS, LEF, liberty 9 corner, netlist, SPICE, SPEF) dan patch `dffram_coldtrack.diff`; asal-usulnya di bagian A |
| `sim/RAM256.v` | Model simulasi DFFRAM yang meniru register keluaran per blok 16 word dan mux keluaran beralamat langsung |
| `rtl/serial_mul.sv` | Pengali serial 41 × 82 bit (8 bit per siklus, 6 iterasi) |
| `rtl/physics.sv` | Pengganti `hw/rtl/physics.sv`: semua pengali besar lewat satu `serial_mul`, tanpa pipeline L=3, riwayat tanpa reset |
| `rtl/rst_sync.sv` | Sinkroniser reset 2 flip-flop (assert asinkron, deassert sinkron) |
| `rtl/model_flash.sv` | Pengganti `hw/rtl/model_flash.sv`: model di flash diverifikasi dengan tag HMAC sebagai ganti hash tetap (bagian E) |
| `rtl/coldtrack_asic.sv` | Top layout: `rst_sync` + `coldtrack_spi` (dari `hw/rtl`) |
| `golden/flash_tag.py` | Pembuat kunci model dan image flash bertag |
| `sim/sky130_sram_1kbyte_1rw1r_32x256_8.v` | Model simulasi makro yang bersih (tanpa `$display`/delay), pin sama dengan model PDK |
| `tb/` | Tes cocotb versi ASIC (memakai modul tes dan golden dari `hw/tb`) dan GLS netlist final |
| `layout/` | Config, SDC, dan skrip LibreLane; `layout/eco/` berisi skrip ECO (bagian Layout) |
| `caravel/` | Wrapper Caravel: config dan skrip harden, RTL wrapper, metrik signoff, log precheck |
| `gambar/` | Gambar penempatan sel `RUN_AK` dan layout wrapper WR4 (sama dengan Gambar 1 dan 3 di laporan) |
| `metrics.csv` | Metrik signoff layout final, GLS, dan Caravel |
| `laporan.pdf` | Laporan proses layout |

## Perubahan dari versi FPGA

### A. Ring buffer ke makro RAM

Di FPGA, array `mem` menjadi BRAM. Di ASIC tanpa makro, array itu menjadi 28.416 flip-flop dan mux baca yang
besar. Ring buffer sekarang memakai 4 makro DFFRAM `RAM256` ([AUCOHL/DFFRAM](https://github.com/AUCOHL/DFFRAM),
dari sel standar sky130). Makro ini punya satu port: alamat tulis dipakai saat `wr_en`, selain itu alamat baca.
17 bit atasnya diisi nol. Latensi bacanya sama dengan register `rd_r` versi FPGA. Mux keluaran DFFRAM antar-blok
16 word memakai alamat saat itu, jadi alamat baca harus tetap satu siklus sesudah dicuplik. Karena itu lintasan
konteks di `features` membaca satu entri per dua siklus (tambahan ±240 siklus per sampel).

SRAM OpenRAM yang dipakai sebelumnya hanya punya liberty TT, Magic DRC-nya melaporkan 11,3 juta error bitcell,
dan pin masukannya dibatasi slew 0,04 ns. DFFRAM punya liberty di semua corner, tanpa aturan DRC khusus makro dan
tanpa batas slew itu. Harganya luas: 809,6 × 533,12 µm per makro, dibanding 479,8 × 397,5 µm untuk SRAM.

Makro `ram256/` (versi v6) dibuat dari DFFRAM commit `ba5268492ab1e6135329d571cf9724766233a230` (10 Nov 2025),
di-harden dengan LibreLane 3.0.17 (image `ghcr.io/librelane/librelane:3.0.17`) dan PDK sky130A `8afc8346`, ditambah
patch ColdTrack `ram256/dffram_coldtrack.diff`:

- Mux keluaran `Do` tingkat atas memakai `mux2_4` (MUX2x1_X4). Slew pin `Do` turun dari 1,79 ns (`Do0[17]`)
  menjadi < 0,75 ns di STA makro.
- Langkah baru `DFFRAM.PinBufPlace` (`scripts/odbpy/pinbuf.py`) berjalan setelah penempatan pin, diikuti
  `OpenROAD.DetailedPlacement`. PlaceRAM menaruh sel tambahan berderet di pojok makro, jadi langkah ini memindahkan
  buffer pin masukan (DIBUF/A0BUF/WEBUF/EN0BUF/CLKBUF beserta diodanya) dan mux keluaran `Do0MUX` (beserta dioda
  di masukannya) ke baris terdekat dari pinnya. Kapasitansi pin yang terlihat dari top-level: `Di` maksimal
  0,019 pF (sebelumnya sampai 0,18 pF), `Do` maksimal 0,0011 pF.
- Antena: `OpenROAD.RepairAntennas` setelah GRT (`GRT_REPAIR_ANTENNAS=True`), `DRT_ANTENNA_REPAIR_ITERS=5`,
  `OpenROAD.CheckAntennas` setelah DRT, dan `OpenROAD.FillInsertion` dipindah ke setelah DRT supaya dioda dan
  jumper punya tempat. Pelanggaran antena di dalam makro 0 (versi asli 32 net).

Hasil harden: ukuran 809,6 × 533,12 µm, 72.537 sel, DRC Magic 0, LVS 0, XOR 0, antena 0. Pin LEF sama dengan
versi sebelumnya, jadi makro bisa ditukar tanpa mengubah top-level. Ringkasan metrik harden ada di
`ram256/metrics.json`. Angka timing di sana memakai constraint bawaan DFFRAM; timing makro di dalam chip dianalisis
ulang di STA top-level (clock 100 ns).

View besar (`gds`, `spef`, `spice`, `nl`, `pnl`, ±155 MB) tidak disimpan di git. Ambil `ram256_views.tar.gz` dari
GitHub Release `asic-v1.0` dan ekstrak di folder ini (arsipnya sudah berisi path `ram256/...`), atau bangun ulang.
Yang ada di git hanya `lef`, `lib`, `metrics.json`, dan patch.

Membangun ulang makro:

```bash
# di clone DFFRAM (commit di atas) setelah git apply dffram_coldtrack.diff
docker run --rm -u $(id -u):$(id -g) -e HOME=/tmp -v $PWD:/dffram -v <pdk sky130 8afc8346>:/pdk:ro -w /dffram \
  ghcr.io/librelane/librelane:3.0.17 python3 dffram.py -p sky130A -s sky130_fd_sc_hd -b ram \
  --manual-pdk --pdk-root /pdk 256x32
# salin products/RAM256/{gds,lef,lib,nl,pnl,spice,spef} ke hw/asic/xgboost/ram256/
```

### B. Pengali diserialkan

Di `physics`, empat perkalian lebar (update tc, `p·(cab−tc)`, `p·ek`, `p30·d_at`) memakai satu `serial_mul`. Di
`features`, 13 pengkuadrat paralel diganti satu pengkuadrat yang dipakai bergantian selama 13 siklus per sampel.
Setiap jendela bertambah beberapa siklus. Itu masih jauh di bawah batas waktu, karena sampel datang tiap menit
dan clock 10 MHz.

### C. Pipeline L=3 di physics dihapus

Clock 10 MHz tidak memerlukannya.

### D. Reset

Pin `rst_n` melewati `rst_sync` lebih dulu, sehingga reset dilepas sinkron dengan clock. Shift register riwayat
di `physics` (`raw_sr`, `amb_sr`, `clean_sr`, `s10_sr`) dan datapath `serial_mul` tidak memakai reset, karena
nilainya selalu ditulis sebelum dibaca dan flip-flop tanpa reset (`dfxtp`) lebih kecil daripada versi dengan
reset (`dfrtp`). Akumulator di `features` dan inti SHA tetap memakai reset; penghematannya hanya sekitar 0,01 mm².

### E. Model bisa diganti tanpa chip baru

Versi FPGA hanya menerima satu model: SHA-256 image harus sama dengan `HASH_MODEL` yang ditanam saat sintesis.
Versi ASIC menanam kunci 32 byte (`KUNCI_MODEL`), dan flash berisi image diikuti tag 32 byte:

```
tag = HMAC-SHA256(kunci, SHA256(image))
```

Chip membaca tag sesudah image, lalu menghitung HMAC dengan `sha256_stream` yang sama (dua putaran tambahan:
`K^ipad || digest`, lalu `K^opad || dalam`). Diagnosis hanya sah bila HMAC sama dengan tag. Image atau tag yang
diubah ditolak, begitu juga tag dari kunci lain; model baru dengan tag dari kunci yang benar diterima. Biayanya
sekitar 530 flip-flop (tag dan pesan) dan kurang dari 1.000 siklus per inferensi untuk membaca tag 32 byte dan
dua putaran HMAC, di bawah 0,3% dari ±316 ribu siklus per inferensi.

Menerbitkan model baru:

```bash
.venv/bin/python -m hw.golden.flash_image                                   # nodes/trees/base.mem -> image
.venv/bin/python -m hw.asic.xgboost.golden.flash_tag hw/model/<folder>      # -> hw/asic/xgboost/build/flash/<folder>.bin
# tulis .bin itu ke flash QSPI mulai alamat 0
```

Batas hardware tetap berlaku: 82 fitur, 7 kelas, maksimal 1.024 pohon dan 16.384 simpul.

Kunci dibuat dengan `python -m hw.asic.xgboost.golden.flash_tag --buat-kunci` dan dibaca dari
`~/.coldtrack/kunci_model.hex` (bisa diganti lewat env `CT_KUNCI_MODEL`). Kunci ikut tertanam di netlist dan GDS
sebagai konstanta logika, jadi siapa pun yang memegang GDS atau netlist bisa membacanya.

> **Kunci layout ini adalah kunci lomba yang dipublikasikan.** Layout di folder ini dibuat untuk lomba dan
> verifikasi. Kunci yang tertanam di layout final sengaja dipublikasikan bersama GDS, netlist, dan berkas layout
> lain, agar juri dan siapa pun bisa memeriksa tag model dan mengulang verifikasinya. Akibatnya chip dari layout
> ini tidak melindungi model: siapa pun bisa menerbitkan model bertag yang akan diterima.
>
> Untuk tapeout sungguhan, buat kunci rahasia baru (`--buat-kunci`), lalu ulangi sintesis dan layout penuh beserta
> ECO-nya. Kunci mengubah logika, sehingga netlist, routing, dan timing ikut berubah. GDS, netlist, DEF, dan SPEF
> hasilnya tidak boleh dipublikasikan. Kunci lomba ini juga tidak boleh dipakai di perangkat lain, termasuk board
> FPGA.

Keluaran versi ASIC bit-exact dengan golden dan RTL FPGA.

## Tes

```bash
cd hw/asic/xgboost/tb
../../../.venv/bin/python -m pytest -q test_asic.py
```

| Tes | Isi |
|---|---|
| `test_features_asic` | features: 6 perjalanan × 300 menit, bit-exact |
| `test_physics_asic` | physics: semua skenario |
| `test_model_flash_asic` | model_flash ASIC: model asli dan model pengganti bertag diterima dan bit-exact; byte image, byte tag, tag kunci lain, dan header buruk ditolak |
| `test_coldtrack_top_flash_asic` | `coldtrack_top` lewat AXI dengan flash QSPI bertag |
| `test_coldtrack_asic` | top layout lewat SPI, termasuk `rst_sync` |

Tes memakai kunci uji tetap (`bytes(range(0xA0, 0xC0))`), bukan kunci layout.

Verilator mengisi register tanpa reset dengan nilai acak (`--x-initial unique`, `+verilator+rand+reset+2`), jadi
logika yang diam-diam bergantung pada nilai awal nol akan gagal.

Versi serial perlu lebih banyak siklus, jadi batas siklus tunggu `done` dinaikkan lewat env (`BATAS_DONE_FISIKA`,
`BATAS_DONE_FITUR`). Default di `hw/tb` tetap.

## Layout

```bash
# dari root repo; butuh Docker dan LibreLane 3.0.17 di .venv (pip install librelane==3.0.17)
hw/asic/xgboost/layout/run_layout.sh                      # alur lengkap RTL -> GDS
hw/asic/xgboost/layout/run_layout.sh --to Yosys.Synthesis # sintesis saja
```

`run_layout.sh` membaca kunci dari `~/.coldtrack/kunci_model.hex` dan berhenti bila berkas itu tidak ada. Kunci
tidak ditulis ke `config.json`; skrip membuat config sementara `.config_kunci.json` yang dihapus setelah run.
Folder `runs/` memuat kunci (netlist, GDS, `resolved.json`) dan diabaikan git. Hasil ditulis ke
`hw/asic/xgboost/layout/runs/<tag>/final/`.

### Parameter

| Kelompok | Nilai |
|---|---|
| Alat | LibreLane 3.0.17 (Docker), OpenROAD 2026-02-17, PDK sky130A `8afc8346`, sel `sky130_fd_sc_hd` |
| Clock | `clk`, 10 MHz (`CLOCK_PERIOD` 100 ns) |
| Die / core | 2200 × 2200 µm (4,84 mm²) / 4,76 mm², 800 baris `unithd` |
| Makro | 4 × `RAM256` 809,6 × 533,12 µm di pojok die: `u_ram0` (40, 80) N, `u_ram1` (1350, 80) FN, `u_ram2` (40, 1586) FS, `u_ram3` (1350, 1586) S |
| Halo makro | horizontal 45 µm, vertikal 40 µm |
| Power makro | `PDN_MACRO_CONNECTIONS` ke `VPWR`/`VGND` |
| Penempatan | `PL_TARGET_DENSITY_PCT` 62 |
| SDC | `pnr.sdc` (fanout maksimal 9, satu di bawah batas signoff, karena dioda dari DRT dihitung sebagai beban) dan `signoff.sdc` (fanout 10); slew maksimal 0,75 ns; clock uncertainty 0,25 ns; transisi clock 0,15 ns; derate ±5 % |
| CTS | `clkbuf_16/8/4/2`, cluster 10 sink, kabel clock maksimal 600 µm |
| Perbaikan desain | sebelum GRT: slew 40 %, cap 40 %, kabel maksimal 600 µm; `RUN_POST_GRT_DESIGN_REPAIR` dan `RUN_POST_GRT_RESIZER_TIMING` dimatikan dan diganti ECO (di bawah) |
| Hold | margin resizer PL 0,01 ns, GRT 0 ns, buffer hold maksimal 5 % |
| Antena | jumper di tahap GRT (`RUN_ANTENNA_REPAIR=true`, `GRT_ANTENNA_REPAIR_JUMPER_ONLY=true`), sisanya dioda oleh DRT (`DRT_ANTENNA_REPAIR_ITERS` 6, margin rasio 10 %) |
| STA | 9 corner (ff/tt/ss × RC min/nom/max), `STA_MACRO_PRIORITIZE_NL` |
| GDS | KLayout |

### Alur dan ECO

Layout final (tag `RUN_AK`) dibuat dengan alur LibreLane penuh, lalu beberapa putaran ECO dengan skrip di
`layout/eco/`:

| Skrip | Fungsi |
|---|---|
| `eco_all.tcl` | ECO OpenROAD (env): repeater di tengah net panjang, penyeimbangan dioda, pemecahan net, buffer di belakang driver lemah, sel hold; `POST_ROUTE=1` untuk layout yang sudah di-route |
| `ecolist.py` | Menyusun daftar ECO dari pelanggar slew/fanout STA pasca-route |
| `diodenets.py` | Jumlah dioda dan beban per net (pelanggar fanout berasal dari dioda antena) |
| `holdall.tcl` | Disisipkan ke STA (`-c STA_EXTRA_CORNER_TCL_FILE=...`): semua endpoint hold dengan slack < 0,05 ns di corner ff ditulis ke `runs/_hold/` (laporan bawaan hanya 2.000 jalur) |

Urutannya:

1. Alur penuh RTL → GDS dengan `run_layout.sh`.
2. ECO sebelum GRT pada ODB hasil penempatan dan CTS: buffer di belakang driver lemah (driver ukuran 1 dan 2,
   dlygate, `clkbuf_2` dengan kabel panjang), repeater di tengah net panjang, pemecahan net dengan beban banyak,
   dan sel hold untuk jalur makro `Do` → flop. Dioda antena tidak dihapus, karena menghapusnya membuat
   `repair_antennas` crash. Driver tidak diperbesar, karena itu mempercepat jalur dan bisa merusak hold.
3. Routing ulang dari GRT dengan jumper antena di tahap GRT. Net antena setelah GRT turun dari 927 ke 101, dan
   dioda dari DRT turun dari 1.655 ke 654. STA menghitung dioda sebagai beban, jadi dioda inilah sumber utama
   pelanggaran fanout.
4. ECO inkremental setelah DRT (2 putaran). Sel lama dikunci (`FIRM`), sel baru ditaruh di slot kosong, dan kabel
   hanya dihapus pada net yang diubah. GRT lalu hanya me-route net tersebut (sekitar 10 sampai 66 mm, beberapa
   detik), dan DRT mempertahankan routing net lain (DRT ±7 menit, bukan ±30 menit). Cara ini dipakai karena ECO
   yang diikuti routing ulang penuh tidak konvergen: routing ulang menggeser ribuan net lain. Run ini dimulai dari
   ODB hasil ECO dengan
   `--with-initial-state <state> --from OpenROAD.GlobalRouting --to OpenROAD.STAPostPNR -c RUN_ANTENNA_REPAIR=false`.
   Jumper GRT tidak dipakai lagi karena net lama sudah di-route dan net baru pendek.
   - Putaran 1: 870 `dlygate4sd1_1` untuk endpoint hold < 0,022 ns, 51 buffer slew, 18 repeater, 1 net dipecah.
   - Putaran 2: dioda di 8 repeater diseimbangkan antara net masukan dan keluaran, 7 buffer slew, 13 sel hold.
5. Signoff dilanjutkan dari state STA (`--from OpenROAD.IRDropReport`).

Margin hold dibatasi +0,022 ns. Menaikkan targetnya butuh ribuan sel tunda di area rantai flop yang sudah padat:
7.170 sel untuk +0,05 ns membuat GRT overflow 2.529, dan 3.287 sel untuk +0,03 ns sudah overflow. Slack hold di
STA sudah termasuk clock uncertainty 0,25 ns dan derate 5 %.

### Hasil signoff (`RUN_AK`)

| Pemeriksaan | Hasil |
|---|---|
| DRC Magic / KLayout / routing | 0 / 0 / 0 |
| LVS (error, device, net, pin, property) | 0 |
| XOR Magic vs KLayout | 0 |
| Antena (net / pin) | 0 / 0 |
| Illegal overlap, pin terputus, pelanggaran power grid | 0 |
| Setup WNS (ss / tt / ff) | +36,13 / +42,77 / +45,38 ns |
| Hold WNS (ff / tt / ss) | +0,022 / +0,188 / +0,650 ns |
| Slew, cap, fanout top-level (9 corner) | 0 |
| IR drop terburuk | 0,11 mV (VPWR 0,106 mV, VGND 0,111 mV) |
| Daya (nom tt) | 28,8 mW (internal 18,6, switching 10,2, bocor 0,0045) |

Metrik `design__max_slew/cap/fanout_violation__count` di `metrics.json` LibreLane tidak nol (misalnya slew 34.060
di nom tt). Semuanya berasal dari bagian dalam makro DFFRAM: bus bit dibaca lewat buffer tri-state dari banyak
word, sehingga transisinya lambat. Makro sudah dikarakterisasi lengkap, dan timing yang melewatinya terpenuhi di
STA top-level. Daftar lengkap ada di `metrics.csv`.

### Luas

| | Nilai |
|---|---|
| Sel standar | 1,561 mm² (utilisasi 51,4 %), 165.585 sel logika |
| Makro | 4 × 0,4316 mm² = 1,726 mm² |
| Flip-flop | 17.795 |
| Buffer perbaikan timing / hold | 22.834 / 640 dari resizer, ditambah sel ECO |
| Dioda antena | 1.862 sel |
| Total sel (termasuk filler 302.384 dan tap 36.851) | 467.973 |
| Panjang kabel / via | 5,64 m / 980.471 |

Sebagai pembanding, versi FPGA apa adanya (`hw/rtl`) menghasilkan sekitar 2,75 mm² sel standar dengan ±46.000
flip-flop setelah sintesis.

## Gate-level simulation (netlist final `RUN_AK`)

```bash
cd hw/asic/xgboost/tb
../../../../.venv/bin/python -m pytest -q -s test_gls.py -k fungsional              # Verilator, tanpa delay
GLS_CORNER=max_ss_100C_1v60 ../../../../.venv/bin/python -m pytest -q -s test_gls.py -k sdf   # Icarus + SDF
```

`test_gls.py` memakai netlist `layout/runs/RUN_AK/final/nl` dengan model Verilog sel sky130 dari PDK. Image flash
ditandai dengan kunci layout (`~/.coldtrack/kunci_model.hex`), karena kunci sudah tertanam di gerbang.
`coldtrack_asic_tb.sv` memilih DUT netlist lewat `` `define GLS `` dan anotasi SDF lewat `` `define GLS_SDF ``.

| Tes | DUT dan simulator | Skenario | Hasil |
|---|---|---|---|
| `test_gls_fungsional` | netlist tanpa sel fisik + RAM256 perilaku, Verilator 5.053, tanpa delay | sama dengan `test_coldtrack_asic` (SPI): 2 trip × 75 menit, 15 diagnosis, 8 HMAC, image flash rusak ditolak | lulus, bit-exact dengan golden (43 menit) |
| `test_gls_sdf`, nom_tt | netlist + netlist gerbang RAM256, Icarus 14 + SDF pasca-layout, clock 100 ns, SCK = clk/8 | `sdf_singkat`: ID, frame terputus diabaikan, kunci sesi, 3 menit fisika + rantai segel + HMAC | lulus (2 jam 20 menit) |
| `test_gls_sdf`, max_ss | idem | idem | lulus (1 jam 58 menit) |
| `test_gls_sdf`, min_ff | idem | idem | lulus (1 jam 48 menit) |

Catatan GLS dengan SDF:

- SDF final dibuat STA dengan netlist gerbang makro (`STA_MACRO_PRIORITIZE_NL`), jadi SDF itu berisi delay sel dan
  kabel di dalam RAM256. GLS SDF karenanya memakai netlist gerbang RAM256 (`ram256/nl`), bukan model perilaku.
- Parser SDF Icarus tidak mengenali titik ber-escape di path hierarki (`u_chip\.u_ct...`) dan crash pada
  INTERCONNECT. Nama escaped di netlist dan SDF diganti secara konsisten (`.` → `__`, `[`/`]` → `_`).
- Icarus mencari tiap nama instance secara linear di scope top (±230 ribu instance), sehingga 555 ribu entri
  INTERCONNECT butuh lebih dari 1 jam anotasi per corner. Delay kabel dilipat ke IOPATH sel penggeraknya (delay
  terpanjang di net itu). Delay kabel kecil dibanding delay sel: di tt median 0,001 ns, p99 0,029 ns, maksimal
  0,326 ns, sedangkan median delay sel 0,279 ns. `GLS_SDF_INTERCONNECT=1` mempertahankan INTERCONNECT asli.
- Icarus tidak menjalankan TIMINGCHECK SDF (setup/hold), jadi pemeriksaan itu tetap bersandar pada STA signoff.
  GLS SDF memeriksa bahwa logika berjalan benar dengan delay nyata: glitch, latch dan clock gating di DFFRAM, dan
  reset asinkron.
- Sel fisik (decap, fill, tap) dibuang sebelum kompilasi. Dioda antena dibuang di GLS fungsional, tetapi
  dipertahankan di GLS SDF karena SDF menganotasi kabel ke pin dioda.

Dua "floating net" di `metrics.json` (`timing__drv__floating__nets`) berasal dari langkah `repair_design` di awal
alur. Pada ODB final, `report_floating_nets` kosong, dan tidak ada net tanpa driver maupun multi-driver.

## Integrasi Caravel (ChipFoundry chipIgnite)

Makro `coldtrack_asic` ditempatkan di `user_project_wrapper` Caravel (sky130A, Caravel Lite `CC2509`) dengan
templat ChipFoundry `caravel_user_project`. Sumber kecilnya disalin ke `caravel/`: konfigurasi dan skrip harden,
RTL wrapper, `user_defines.v`, konfigurasi LVS, metrik signoff, dan log precheck. View besar (GDS 166 MB, SPEF,
netlist) tidak masuk git; arsipnya ada di GitHub Release `asic-v1.0` (`coldtrack_caravel_tapeout.tar.gz` dan
`coldtrack_caravel_spef.tar.gz`). Rinciannya di `caravel/README.md`.

| | |
|---|---|
| Clock / reset | `wb_clk_i` (10 MHz) / `wb_rst_i`, lewat rantai 6 `clkbuf_8` di RTL karena CTS tidak mengenali pin clk makro |
| Pin | 13 `mprj_io` (13 sampai 25): SPI slave, flash QSPI, 3 alarm; alarm juga ke `user_irq[2:0]` |
| Penempatan makro | (360,18; 1098,88) N di area 2920 × 3520 µm |
| PDN | strap vccd1/vssd1 berimpit dengan grid daya makro (met4 + met5), celah di ujung pin makro ditutup `pdn_bridge.tcl` |
| Baris sel standar | dibatasi ke pita dan kanal tepi (`FP_OBSTRUCTIONS`), sel fill turun dari 1,4 juta ke 185 ribu |
| Signoff wrapper (run 4 dari 5) | DRC 0, LVS lulus, XOR 0, antena 0, slew/cap/fanout 0, setup +50,2 ns, hold +4,86 ns |
| Precheck | CF Precheck v1.3.7: 13/13 lulus, termasuk LVS penuh (wrapper + makro + RAM256) |
