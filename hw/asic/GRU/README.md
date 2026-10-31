# hw/asic/GRU — mesin GRU di chip (Fase 2, eksperimen)

Mesin inferensi untuk GRU forecast + diagnosis (kontrak `backend/models/coldtrack_v5.onnx`) yang bobotnya dibaca dari
flash. Folder ini **terpisah** dari chip ColdTrack (`hw/asic/xgboost/rtl`, layout RUN_A sampai RUN_T) dan belum masuk
layout; rencananya menjadi macro kedua di `user_project_wrapper` Caravel.

| Berkas | Isi |
|---|---|
| `rtl/gru_engine.sv` | Mesin GRU: 1 MAC int8 x int16 per byte bobot, aktivasi LUT + interpolasi, statistik jendela, kepala linear |
| `rtl/gru_lut.svh` | ROM sigmoid/tanh 257 titik (dibangkitkan oleh golden, jangan diedit) |
| `golden/gru_golden.py` | Golden bit-exact, kuantisasi, format image flash, pembaca image, pembuat LUT |
| `golden/make_image.py` | ONNX → `model/coldtrack_v5_gru.bin` (butuh paket `onnx`) |
| `model/coldtrack_v5_gru.bin` | Image flash GRU v5 INT8 (264.357 byte), info di `.json` |
| `model/coldtrack_v6_gru.bin` | Image flash kandidat GRU v6 (B14, forecast residual: host menambahkan temp_c terakhir) |
| `tb/` | Testbench Verilator + cocotb: `runner_gru.py`, `gru_tb.sv`, `test_gru.py`, `vectors/v5_val.npz` |

## Cara kerja

- **Bobot tidak disimpan di chip.** Satu langkah waktu membaca 261.888 byte bobot (3 lapis × 128 neuron × 3 gerbang)
  dari flash, dan dibaca ulang tiap langkah. Di chip hanya ada hidden state 3 × 128 × 16 bit, buffer 128 × 16 bit,
  statistik jendela, dan konstanta header.
- **Model diganti lewat flash.** Dimensi (L, H, NI, NC, T, NO), normalisasi masukan, dan konstanta statistik ada di
  header image. Batas build ini: `L ≤ LMAX = 3`, `H ≤ HMAX = 128`, `NI ≤ 16`, `NC ≤ 8`, `NO ≤ 16`, `T ≤ 255`.
  Model di luar batas itu atau arsitektur selain GRU butuh RTL dan layout baru.
- **Aritmetika:** bobot int8 per baris dengan skala (M, S) per baris, aktivasi int16 Q5.10, pembulatan
  `(x*M + 2^(S-1)) >>> S`. Rincian dan layout image di docstring `golden/gru_golden.py`.
- **Antarmuka:** aliran byte bobot (`ws_start/ws_addr`, `ws_valid/ws_data/ws_ready`) dan memori masukan baca sinkron
  (`xin_addr` → `xin_data`, int32 Q15.16). Keluaran 11 × int32 Q5.10 lewat `out_idx/out_data`:
  `0..2` forecast t+15/30/60 ternormalisasi (°C = v/1024 × 10,1709 − 1,2106), `3..9` logit 7 kelas, `10` TTB mentah.

## Akurasi INT8 (split val, 16.414 jendela, tidak memakai split test)

| | ONNX float | Golden INT8 (= RTL) |
|---|---|---|
| Macro F1 (label v5) | 0,8746 | 0,8748 |
| PR-AUC anomali | 0,8679 | 0,8691 |
| MAE forecast t+15 / t+30 / t+60 (°C) | 0,157 / 0,208 / 0,246 | 0,155 / 0,213 / 0,248 |
| Argmax kelas sama dengan ONNX | – | 99,9 % |

## Verifikasi

```bash
.venv/bin/python hw/asic/GRU/tb/runner_gru.py               # 25 model acak + header rusak + 3 jendela val v5
.venv/bin/python hw/asic/GRU/tb/runner_gru.py --tanpa-v5    # cepat (± 1 menit)
.venv/bin/python hw/asic/GRU/tb/runner_gru.py --acak 0 --image coldtrack_v6_gru.bin   # model lain, RTL sama
```

Setiap kasus membandingkan semua keluaran RTL dengan golden secara bit-exact. Aliran flash diberi jeda acak (0–59 %),
dan register tanpa reset diisi acak oleh Verilator.

## Yang belum

- Integrasi: pembaca QSPI, verifikasi HMAC image (pakai ulang `qspi_reader`/`sha256_stream`), dan sumber masukan
  dari ring buffer ColdTrack atau dari host.
- Layout macro (LibreLane) dan penempatan di wrapper Caravel.
- Waktu inferensi dibatasi flash: sekitar 15,7 MB per inferensi. Pada QSPI 25 MHz (12,5 MB/s) sekitar 1,3 s, dan
  pada clock chip 10 MHz (flash 5 MHz) sekitar 6 s. Masih cukup untuk sampel per menit.
