# hw/asic: versi ASIC ColdTrack (SKY130)

Folder ini berisi bagian khusus ASIC, dipisah per mesin AI. RTL FPGA di `hw/rtl` tidak diubah.

| Folder | Isi | Status |
|---|---|---|
| [`xgboost/`](xgboost/README.md) | Chip ColdTrack: fisika, fitur, dan XGBoost (model di flash, tag HMAC). RTL pengganti khusus ASIC, makro DFFRAM, tes cocotb, config dan skrip LibreLane, wrapper Caravel | Layout final RUN_AK lolos signoff, GLS lulus, wrapper Caravel lolos precheck ChipFoundry |
| [`GRU/`](GRU/README.md) | Mesin GRU untuk forecast dan diagnosis, bobot dibaca dari flash. RTL, golden bit-exact, image model, tes cocotb | RTL terverifikasi, belum di-layout |

Struktur tiap folder:

```
<mesin>/
├── rtl/        modul khusus ASIC (top layout dan pembungkus, mis. xgboost/rtl/coldtrack_asic.sv)
├── golden/     model golden / pembuat image flash
├── tb/         tes cocotb (Verilator; GLS dengan SDF memakai Icarus)
├── layout/     config dan skrip LibreLane, hasil di layout/runs/ (tidak masuk git)
├── caravel/    wrapper Caravel (user_project_wrapper), skrip harden, log precheck
├── metrics.csv ringkasan metrik layout run final
└── laporan.pdf laporan layout
```

Saat ini `layout/` dan `caravel/` baru ada di `xgboost/`. Mesin GRU belum di-layout karena keterbatasan waktu:
waktu lomba habis untuk menutup timing dan signoff chip XGBoost, lalu integrasi Caravel. RTL GRU sudah
terverifikasi bit-exact terhadap golden, jadi layout-nya bisa menyusul dengan alur yang sama.

## Perintah

```bash
# dari root repo
hw/asic/xgboost/layout/run_layout.sh                              # layout XGBoost (RTL -> GDS)
cd hw/asic/xgboost/tb && ../../../../.venv/bin/python -m pytest -q # tes ASIC XGBoost
.venv/bin/python hw/asic/GRU/tb/runner_gru.py                     # tes GRU (bit-exact terhadap golden)
.venv/bin/python -m hw.asic.xgboost.golden.flash_tag --buat-kunci # kunci model (sekali, rahasia)
```

Folder `xgboost/layout/runs/`, `xgboost/build/`, dan config sementara berisi kunci model HMAC, jadi jangan dibagikan.
