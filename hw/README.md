# ColdTrack RTL

Chip ColdTrack untuk truk: segel data sensor (rantai SHA-256 + HMAC), mesin fisika (status
AMAN/WASPADA/KRITIS + TTB), dan diagnosis tree ensemble (XGBoost 420 pohon), di belakang slave AXI4-Lite
untuk ARM pada AMD Kria KV260. RTL ditulis dalam subset SystemVerilog tanpa primitive vendor, jadi bisa
disintesis Vivado maupun Yosys.

| Folder | Isi |
|---|---|
| `rtl/` | Modul sintesis |
| `tb/` | Testbench cocotb (`test_*.py`), dijalankan lewat pytest |
| `golden/` | Model acuan Python bilangan bulat; RTL harus sama bit per bit dengan model ini |
| `scripts/` | Ekspor model XGBoost beku ke berkas memori; vektor uji hasil edge untuk backend |
| `driver/` | Driver ARM: `chip.py` (`ChipAxi` lewat `/dev/mem`, belum diuji di board; `ChipGolden` identik bit per bit dengan RTL) dan `edge_driver.py` (sampel ke chip, kirim bacaan + hasil tersegel lewat MQTT) |
| `model/` | Hasil ekspor: `nodes.mem`, `trees.mem`, `base.mem` per model |
| `bd/` | Pembungkus Verilog AXI4-Lite (`coldtrack_axil.v`) untuk block design Vivado + pin alarm PMOD |
| `synth/` | Skrip Yosys (perkiraan) dan Vivado (implementasi out-of-context, block design KV260, laporan) |
| `docs/` | Gambar arsitektur (`rtl_architecture.png`) dan block design Vivado (`vivado_block_design.png`/`.svg`) |
| `results/` | Laporan paritas golden vs float (JSON) dan laporan Vivado (`results/vivado/`) |

## Arsitektur

![Arsitektur RTL ColdTrack di KV260](docs/rtl_architecture.png)

```
ARM KV260 (Linux, MQTT/TLS) --AXI4-Lite--> coldtrack_top
   tiap menit: tulis S_* lalu CTRL.sampel_go
     seal        rekaman 23 byte -> rantai SHA-256          (1 kompresi, 65 siklus)
     physics     aturan sensor, observer Tc, TTB T=0..60     (sekitar 75 siklus, perkalian dipipeline)
     features    ring buffer 256 menit -> 82 fitur bulat     (sekitar 650 siklus)
     tree_engine 420 pohon -> skor 7 kelas + argmax          (sekitar 3.800 siklus)
   STATUS.hasil_valid -> baca R_*; CTRL.mac_go -> HMAC {rantai, paket hasil 16 byte}
   pin alarm_waspada / alarm_kritis / alarm_sensor untuk sopir
```

Peta register dan format paket hasil: `golden/regmap.py`. Format rekaman segel: `golden/seal.py`.
Satuan semua masukan: suhu, kelembapan, kecepatan 0,01; radiasi 1/16 W/m2; siklus kerja 1/10000. Satuan
desimal membuat kelipatan 0,1 C data latih eksak, karena ambang pohon XGBoost sering tepat di nilai data.

## Status verifikasi

| Tahap | Modul | Hasil |
|---|---|---|
| M1 | `golden/physics.py` vs `engine.py` | 214.406 menit (594 trip train/val + 5 skenario). 5 skenario 100 % identik; dari 195 menit berbeda, 193 adalah seri tepat di ambang (float memutus acak), 2 karena sebab lain; tidak ada menit KRITIS float tapi AMAN golden |
| M1 | `golden/trees.py` vs XGBoost float | val 16.414 jendela: kelas sama 99,80 % (#7), 99,90 % (#8); Macro F1 0,848 vs 0,852 dan 0,930 vs 0,933 |
| M2 | `sha256_core`, `seal` | NIST FIPS 180-4 + 31 pesan acak; rantai + HMAC identik `hashlib`/`hmac`; kunci terkunci; manipulasi terdeteksi |
| M3 | `tree_engine` | 240 jendela val, skor 7 kelas + argmax identik golden; model dari berkas dan dimuat host |
| M4 | `floor_div`, `features` | 609 kasus pembagian; 825 jendela lengkap (1.997 menit, 6 trip) 82 fitur identik |
| M5 | `physics` | 7.136 menit (2 trip per mode A0-A8 + 5 skenario) identik semua keluaran |
| M6 | `coldtrack_top` (AXI4-Lite) | 709 menit dua trip penuh: fisika, rantai, 296 diagnosis, 26 HMAC identik golden |
| M7 | Sintesis Yosys KV260 | perkiraan resource, lihat tabel di bawah |
| M8 | Vivado KV260 (block design, place-and-route) | lolos 100 MHz, WNS +0,777 ns, WHS +0,012 ns; bitstream + `.xsa` dibuat. Belum diuji di board |

Catatan dari verifikasi: aturan "pintu terbuka, sisa waktu terburuk <= 30 menit" (alasan 4) di `engine.py`
tidak pernah bisa menentukan status. Saat pintu terbuka kabin = max(ts10, suhu luar) >= suhu luar dan
(x - t_hi)/(x - Tc) naik terhadap x, sehingga TTB biasa selalu <= TTB kasus terburuk dan aturan TTB lebih
dulu memicu dengan status yang sama atau lebih tinggi. RTL tetap memuat aturan itu agar setara backend.

## Vivado KV260 (post-route, model #8)

![Block design Vivado KV260](docs/vivado_block_design.png)

Block design: Zynq UltraScale+ PS (preset board `kv260_som`) -> SmartConnect -> `coldtrack_axil` di
`0xA000_0000` (4 KB), clock `pl_clk0` 100 MHz, alarm ke PMOD J2 (`bd/kv260_alarm.xdc`, cocokkan pin dengan
UG1089 sebelum dipakai).

| Resource | Terpakai | Porsi K26 |
|---|---|---|
| LUT | 27.248 (12.069 sebagai memori) | 23,3 % |
| FF | 18.862 | 8,0 % |
| BRAM36 | 0 | 0 % |
| DSP | 70 | 5,6 % |

Tabel simpul `tree_engine` (8.704 x 72) dan ring buffer `features` (256 x 111) jatuh ke LUTRAM: Vivado
menolak `ram_style = "block"` ("infeasible") untuk kedua memori ini, padahal pola yang sama di modul kecil
terpetakan ke 18 BRAM. Penyebab belum ditemukan; desain tetap muat.

Timing `coldtrack_top` out-of-context per frekuensi (`synth/kv260_vivado.tcl`, laporan di
`results/vivado/sweep/`). Daya adalah logika PL saja; daya total block design (termasuk PS) 2,88 W.

| Clock | WNS | Daya PL total / dinamis |
|---|---|---|
| 10 MHz | +85,68 ns | 0,303 W / 0,014 W |
| 25 MHz | +24,55 ns | 0,324 W / 0,035 W |
| 50 MHz | +9,41 ns | 0,360 W / 0,072 W |
| 100 MHz | +0,777 ns (block design) | |

Sebelum perbaikan, 100 MHz gagal tipis (WNS -0,146 ns) di pencarian TTB `physics` (selisih -> perkalian 82 bit
-> bandingkan, 23 level). Perkalian TTB dan aturan pintu kini melewati 3 register pipeline, jumlah `features`
dihitung satu siklus sebelum digeser, dan `flat` diregister sebelum aturan sensor.

## Resource KV260 (Yosys `synth_xilinx -family xcup`, model #8, sebelum pipeline)

| Modul | LUT | FF | BRAM36 | DSP |
|---|---|---|---|---|
| `physics` | 4.436 | 3.076 | 0 | 37 |
| `features` | 3.980 | 2.315 | 2 | 38 |
| `floor_div` | 405 | 296 | 0 | 0 |
| `tree_engine` | 1.124 (+288 LUTRAM) | 481 | 18 | 0 |
| `sha256_core` | sekitar 1.880 | 1.289 | 0 | 0 |
| `seal` (tanpa SHA) | 724 | 1.738 | 0 | 0 |
| `coldtrack_top` (AXI + sequencer) | 1.503 | 1.207 | 0 | 0 |
| **Total** | **14.054 (+288 LUTRAM)** | **10.402** | **20** | **75** |
| Kapasitas K26 | 117.120 | 234.240 | 144 | 1.248 |
| Porsi | 12 % | 4,4 % | 14 % | 6 % |

Angka Yosys adalah perkiraan sebelum place-and-route; Yosys memetakan kedua memori ke BRAM, Vivado tidak.
