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
| `scripts/` | Ekspor model XGBoost beku ke berkas memori |
| `model/` | Hasil ekspor: `simpul.mem`, `pohon.mem`, `base.mem` per model |
| `synth/` | Skrip sintesis Yosys untuk KV260 |
| `hasil/` | Laporan paritas golden vs float (JSON) |

## Arsitektur

```
ARM KV260 (Linux, MQTT/TLS) --AXI4-Lite--> coldtrack_top
   tiap menit: tulis S_* lalu CTRL.sampel_go
     segel       rekaman 23 byte -> rantai SHA-256          (1 kompresi, 65 siklus)
     fisika      aturan sensor, observer Tc, TTB T=0..60     (sekitar 66 siklus)
     fitur       ring buffer 256 menit -> 82 fitur bulat     (sekitar 650 siklus)
     tree_engine 420 pohon -> skor 7 kelas + argmax          (sekitar 3.800 siklus)
   STATUS.hasil_valid -> baca R_*; CTRL.mac_go -> HMAC {rantai, paket hasil 16 byte}
   pin alarm_waspada / alarm_kritis / alarm_sensor untuk sopir
```

Peta register dan format paket hasil: `golden/regmap.py`. Format rekaman segel: `golden/segel.py`.
Satuan semua masukan: suhu, kelembapan, kecepatan 0,01; radiasi 1/16 W/m2; siklus kerja 1/10000. Satuan
desimal membuat kelipatan 0,1 C data latih eksak, karena ambang pohon XGBoost sering tepat di nilai data.

## Menjalankan

Butuh OSS CAD Suite di `~/FPGA/tools/oss-cad-suite` (Verilator 5.05x, Yosys, Icarus) dan `.venv` repo dengan
`cocotb`, `pytest`, serta paket `backend/requirements.txt`.

```bash
cd hw
make test                       # 7 testbench, Verilator (SIM=icarus untuk Icarus)
make lint TOP=coldtrack_top     # verilator -Wall, setiap modul bersih
yosys -s synth/kv260.ys         # sintesis KV260 (sekitar 2 menit), laporan build/util_coldtrack_top.txt
cd .. && python -m hw.golden.uji_fisika   # paritas golden fisika vs backend/app/core/engine.py
python -m hw.golden.uji_pohon             # paritas golden pohon vs XGBoost float
python -m hw.scripts.ekspor_pohon         # ekspor ulang model beku ke hw/model/
```

## Status verifikasi

| Tahap | Modul | Hasil |
|---|---|---|
| M1 | `golden/fisika.py` vs `engine.py` | 214.406 menit (594 trip train/val + 5 skenario). 5 skenario 100 % identik; dari 195 menit berbeda, 193 adalah seri tepat di ambang (float memutus acak), 2 karena sebab lain; tidak ada menit KRITIS float tapi AMAN golden |
| M1 | `golden/pohon.py` vs XGBoost float | val 16.414 jendela: kelas sama 99,80 % (#7), 99,90 % (#8); Macro F1 0,848 vs 0,852 dan 0,930 vs 0,933 |
| M2 | `sha256_core`, `segel` | NIST FIPS 180-4 + 31 pesan acak; rantai + HMAC identik `hashlib`/`hmac`; kunci terkunci; manipulasi terdeteksi |
| M3 | `tree_engine` | 240 jendela val, skor 7 kelas + argmax identik golden; model dari berkas dan dimuat host |
| M4 | `bagi_floor`, `fitur` | 609 kasus pembagian; 825 jendela lengkap (1.997 menit, 6 trip) 82 fitur identik |
| M5 | `fisika` | 7.136 menit (2 trip per mode A0-A8 + 5 skenario) identik semua keluaran |
| M6 | `coldtrack_top` (AXI4-Lite) | 709 menit dua trip penuh: fisika, rantai, 296 diagnosis, 26 HMAC identik golden |
| M7 | Sintesis Yosys KV260 | lihat tabel di bawah; timing belum (butuh Vivado) |

Catatan dari verifikasi: aturan "pintu terbuka, sisa waktu terburuk <= 30 menit" (alasan 4) di `engine.py`
tidak pernah bisa menentukan status. Saat pintu terbuka kabin = max(ts10, suhu luar) >= suhu luar dan
(x - t_hi)/(x - Tc) naik terhadap x, sehingga TTB biasa selalu <= TTB kasus terburuk dan aturan TTB lebih
dulu memicu dengan status yang sama atau lebih tinggi. RTL tetap memuat aturan itu agar setara backend.

## Resource KV260 (Yosys `synth_xilinx -family xcup`, model #8)

| Modul | LUT | FF | BRAM36 | DSP |
|---|---|---|---|---|
| `fisika` | 4.436 | 3.076 | 0 | 37 |
| `fitur` | 3.980 | 2.315 | 2 | 38 |
| `bagi_floor` | 405 | 296 | 0 | 0 |
| `tree_engine` | 1.124 (+288 LUTRAM) | 481 | 18 | 0 |
| `sha256_core` | sekitar 1.880 | 1.289 | 0 | 0 |
| `segel` (tanpa SHA) | 724 | 1.738 | 0 | 0 |
| `coldtrack_top` (AXI + sequencer) | 1.503 | 1.207 | 0 | 0 |
| **Total** | **14.054 (+288 LUTRAM)** | **10.402** | **20** | **75** |
| Kapasitas K26 | 117.120 | 234.240 | 144 | 1.248 |
| Porsi | 12 % | 4,4 % | 14 % | 6 % |

Angka Yosys adalah perkiraan sebelum place-and-route. Jalur kombinasional terpanjang yang perlu dicek di
Vivado untuk 100 MHz: perkalian 82 bit di pencarian TTB `fisika` dan perkalian varians di keluaran `fitur`.
