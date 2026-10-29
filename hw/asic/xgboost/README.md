# hw/asic/xgboost — versi ASIC (layout SKY130)

RTL FPGA di `hw/rtl` **tidak diubah**. Folder ini hanya berisi modul pengganti untuk chip ASIC, dengan nama
dan antarmuka modul yang sama, sehingga pemilihan versi cukup lewat daftar berkas:

| Berkas | Isi |
|---|---|
| `rtl/ring_sram.sv` | Pembungkus ring buffer 256 × 111 bit dari 4 makro DFFRAM `RAM256` (32 bit × 256, latch, 1RW) |
| `rtl/features.sv` | Pengganti `hw/rtl/features.sv`: array `mem` diganti `ring_sram`, 13 pengkuadrat paralel diganti 1 pengkuadrat bergiliran |
| `ram256/` | View makro DFFRAM hasil harden (GDS, LEF, liberty 9 corner, netlist, SPICE, SPEF) dan patch `dffram_coldtrack.diff`; asal-usul di bagian A |
| `sim/RAM256.v` | Model simulasi DFFRAM yang meniru register keluaran per blok 16 word dan mux keluaran beralamat langsung |
| `rtl/serial_mul.sv` | Pengali serial 41 × 82 bit (8 bit per siklus, 6 iterasi) |
| `rtl/physics.sv` | Pengganti `hw/rtl/physics.sv`: semua pengali besar lewat satu `serial_mul`, tanpa pipeline L=3, riwayat tanpa reset |
| `rtl/rst_sync.sv` | Sinkroniser reset 2 flip-flop (assert asinkron, deassert sinkron) |
| `rtl/model_flash.sv` | Pengganti `hw/rtl/model_flash.sv`: model di flash diverifikasi dengan tag HMAC, bukan hash tetap (lihat E) |
| `rtl/coldtrack_asic.sv` | Top layout: `rst_sync` + `coldtrack_spi` (dari `hw/rtl`) |
| `golden/flash_tag.py` | Pembuat kunci model dan image flash bertag |
| `sim/sky130_sram_1kbyte_1rw1r_32x256_8.v` | Model simulasi makro yang bersih (tanpa `$display`/delay), pin sama dengan model PDK |
| `tb/` | Tes cocotb versi ASIC (memakai modul tes dan golden dari `hw/tb`) |
| `layout/` | Config dan skrip LibreLane |

## Perubahan dari versi FPGA

- **A. Ring buffer ke makro RAM.** Di FPGA array `mem` menjadi BRAM. Di ASIC tanpa makro, array itu menjadi
  28.416 flip-flop dan mux baca yang besar. Sekarang ring buffer memakai 4 makro DFFRAM `RAM256`
  ([AUCOHL/DFFRAM](https://github.com/AUCOHL/DFFRAM), dari sel standar sky130): satu port, alamat tulis saat
  `wr_en`, selain itu alamat baca; 17 bit atasnya diisi nol. Latensi bacanya sama dengan register `rd_r` versi
  FPGA. Mux keluaran DFFRAM antar-blok 16 word memakai alamat saat itu, jadi alamat baca harus tetap satu siklus
  sesudah dicuplik: lintasan konteks di `features` membaca satu entri per dua siklus (+±240 siklus per sampel).

  Dibanding SRAM OpenRAM yang dipakai sebelumnya, DFFRAM punya liberty di semua corner (OpenRAM hanya TT),
  tidak ada aturan DRC khusus makro (Magic DRC SRAM melaporkan 11,3 juta error bitcell), dan pin masukannya
  tidak dibatasi slew 0,04 ns. Gantinya lebih luas: 809,6 × 533,1 µm per makro (SRAM 479,8 × 397,5 µm).

  **Asal-usul makro `ram256/`.** DFFRAM commit `ba5268492ab1e6135329d571cf9724766233a230`
  (10 Nov 2025), LibreLane 2.4.2, PDK sky130A `8afc8346`, ditambah patch ColdTrack `ram256/dffram_coldtrack.diff`:

  - Mux keluaran `Do` tingkat atas memakai `mux2_4` (MUX2x1_X4): slew pin `Do` turun dari 1,79 ns (`Do0[17]`) menjadi
    < 0,75 ns di STA makro.
  - Semua pin masukan di-buffer dekat pin (DIBUF/A0BUF/WEBUF/EN0BUF/CLKBUF, ditambah dioda di DI/A0/CLK): kapasitansi
    pin `A0[7]` turun dari 0,332 menjadi 0,031 pF, dan semua pin masukan < 0,2 pF.
  - `GRT_REPAIR_ANTENNAS=True` (tidak berefek pada flow DFFRAM 2.4.2).

  Hasilnya: ukuran tetap 809,6 × 533,12 µm; DRC, LVS, dan XOR bersih; antena pasca-routing 16 net internal (versi
  asli 32). Ringkasan metrik harden ada di `ram256/metrics.json`.

  View besar (`gds`, `spef`, `spice`, `nl`, `pnl`, ±155 MB) tidak disimpan di git. Unduh dari aset GitHub Release
  layout ASIC lalu ekstrak ke `ram256/`, atau bangun ulang. Yang ada di git: `lef`, `lib`, `metrics.json`,
  dan patch.

  Membangun ulang makro:

  ```bash
  # di clone DFFRAM (commit di atas) setelah git apply dffram_coldtrack.diff; DFFRAM butuh LibreLane 2.x
  docker run --rm -u $(id -u):$(id -g) -e HOME=/tmp -v $PWD:/dffram -v <pdk sky130 8afc8346>:/pdk:ro -w /dffram \
    ghcr.io/librelane/librelane:2.4.2 python3 dffram.py -p sky130A -s sky130_fd_sc_hd -b ram \
    --manual-pdk --pdk-root /pdk 256x32
  # salin products/RAM256/{gds,lef,lib,nl,pnl,spice,spef} ke hw/asic/xgboost/ram256/
  ```
- **B. Pengali diserialkan.** Di `physics`, empat perkalian lebar (update tc, `p·(cab−tc)`, `p·ek`,
  `p30·d_at`) memakai satu `serial_mul`. Di `features`, 13 pengkuadrat paralel diganti satu pengkuadrat yang
  dipakai bergantian selama 13 siklus per sampel. Setiap jendela jadi lebih lama beberapa siklus, tetapi tetap
  jauh di bawah batas waktu: sampel datang tiap menit, dan clock 10 MHz.
- **C. Pipeline L=3 di physics dihapus**, karena clock 10 MHz tidak memerlukannya.
- **D. Reset.** Pin `rst_n` melewati `rst_sync` lebih dulu, sehingga reset dilepas sinkron dengan clock.
  Shift register riwayat di `physics` (`raw_sr`, `amb_sr`, `clean_sr`, `s10_sr`) dan datapath `serial_mul`
  tidak lagi memakai reset: flip-flop tanpa reset (`dfxtp`) lebih kecil daripada versi dengan reset (`dfrtp`),
  dan nilainya selalu ditulis sebelum dibaca.
  Akumulator di `features` dan inti SHA tetap memakai reset karena penghematannya hanya sekitar 0,01 mm².
- **E. Model bisa diganti tanpa chip baru.** Versi FPGA hanya menerima satu model: SHA-256 image harus sama
  dengan `HASH_MODEL` yang ditanam saat sintesis. Versi ASIC menanam **kunci** 32 byte (`KUNCI_MODEL`), dan
  flash berisi image diikuti tag 32 byte:

  ```
  tag = HMAC-SHA256(kunci, SHA256(image))
  ```

  Chip membaca tag sesudah image, lalu menghitung HMAC dengan `sha256_stream` yang sama (dua putaran tambahan:
  `K^ipad || digest`, lalu `K^opad || dalam`). Diagnosis hanya sah bila HMAC sama dengan tag. Image yang
  diubah, tag yang diubah, atau tag dari kunci lain ditolak. Model baru dengan tag dari kunci yang benar
  diterima. Tambahannya sekitar 530 flip-flop (tag dan pesan) dan kurang dari 1.000 siklus per inferensi
  (baca tag 32 byte dan dua putaran HMAC), di bawah 0,3% dari ±316 ribu siklus per inferensi.

  Menerbitkan model baru:

  ```bash
  .venv/bin/python -m hw.golden.flash_image                                   # nodes/trees/base.mem -> image
  .venv/bin/python -m hw.asic.xgboost.golden.flash_tag hw/model/<folder>              # -> hw/asic/xgboost/build/flash/<folder>.bin
  # tulis .bin itu ke flash QSPI mulai alamat 0
  ```

  Batas hardware tetap berlaku: 82 fitur, 7 kelas, maksimal 1.024 pohon dan 16.384 simpul.

  **Kunci.** Kunci dibuat sekali (`python -m hw.asic.xgboost.golden.flash_tag --buat-kunci`) dan disimpan di luar repo,
  di `~/.coldtrack/kunci_model.hex` (bisa diganti lewat env `CT_KUNCI_MODEL`). Kunci tidak bisa diubah setelah
  chip dibuat. Jika hilang, model baru tidak bisa diterbitkan lagi. Jika bocor, siapa pun bisa menerbitkan
  model, jadi cadangkan dan rahasiakan. Kunci ikut tertanam di netlist dan GDS (konstanta logika), jadi
  keamanannya bergantung pada GDS yang tidak dipublikasikan. Untuk shuttle yang mewajibkan GDS terbuka, perlu
  skema tanda tangan berbasis kunci publik.

Hasil keluarannya **bit-exact** dengan golden dan RTL FPGA.

## Tes

```bash
cd hw/asic/xgboost/tb
../../../.venv/bin/python -m pytest -q test_asic.py
```

Lima tes:

| Tes | Isi |
|---|---|
| `test_features_asic` | features: 6 perjalanan × 300 menit, bit-exact |
| `test_physics_asic` | physics: semua skenario |
| `test_model_flash_asic` | model_flash ASIC: model asli dan model pengganti bertag diterima dan bit-exact; byte image, byte tag, tag kunci lain, dan header buruk ditolak |
| `test_coldtrack_top_flash_asic` | `coldtrack_top` lewat AXI dengan flash QSPI bertag |
| `test_coldtrack_asic` | top layout lewat SPI, termasuk `rst_sync` |

Tes memakai kunci uji yang tetap (`bytes(range(0xA0, 0xC0))`), bukan kunci produksi.

Verilator mengisi register tanpa reset dengan nilai acak (`--x-initial unique`, `+verilator+rand+reset+2`),
jadi logika yang diam-diam bergantung pada nilai awal nol akan gagal.

Batas siklus tunggu `done` dinaikkan lewat env (`BATAS_DONE_FISIKA`, `BATAS_DONE_FITUR`), karena versi
serial perlu lebih banyak siklus. Default di `hw/tb` tidak berubah.

## Layout

```bash
# dari root repo, setelah setup/wsl/02_librelane.sh
hw/asic/xgboost/layout/run_layout.sh                      # alur lengkap RTL -> GDS
hw/asic/xgboost/layout/run_layout.sh --to Yosys.Synthesis # sintesis saja
```

`run_layout.sh` membaca kunci model dari `~/.coldtrack/kunci_model.hex` dan berhenti bila berkas itu tidak ada.
Kunci tidak ditulis ke `config.json`; skrip membuat config sementara `.config_kunci.json` yang dihapus setelah
run. Folder `runs/` tetap memuat kunci (netlist, GDS, `resolved.json`) dan diabaikan git.

Hasil ditulis ke `hw/asic/xgboost/layout/runs/RUN_<waktu>/final/`. Isi `layout/config.json`:

- **Clock** 10 MHz (`CLOCK_PERIOD` 100 ns).
- **Die** 2000 × 2000 µm. Versi tanpa SRAM memakai 2631 × 2642 µm.
- **Penempatan makro**: 4 makro (masing-masing 479,78 × 397,5 µm) membentuk blok 2×2 di tengah die.
  Pin port 0 ada di sisi bawah/kiri makro, pin port 1 di sisi atas/kanan, jadi di antara kedua baris
  disisakan celah untuk routing.
- **Power makro**: pin `vccd1`/`vssd1` disambungkan ke `VPWR`/`VGND` lewat `PDN_MACRO_CONNECTIONS`.
- **Hold**: margin perbaikan hold diturunkan dari 0,1 ns ke 0,01 ns. Clock uncertainty 0,25 ns di
  `base.sdc` tetap berlaku. Pada versi tanpa SRAM, margin 0,1 ns menambah ±44 ribu buffer tanpa
  memperbaiki pelanggaran yang nyata.
- **Batasan**: liberty makro hanya tersedia untuk corner TT (1,8 V, 25 °C). Corner lain memakai liberty TT
  untuk makro, jadi analisis timing di sekitar SRAM pada corner ss/ff hanya perkiraan.

### Luas hasil sintesis Yosys (sky130_fd_sc_hd, TT)

| | Sel standar | Flip-flop | Makro |
|---|---|---|---|
| Versi FPGA apa adanya (`hw/rtl`) | ±2,75 mm² | ±46.000 | — |
| Versi ASIC (`hw/asic`) | 0,93 mm² | ±17.200 | 4 × 0,19 mm² SRAM |
