# hw/asic — versi ASIC ColdTrack (SKY130)

RTL FPGA di `hw/rtl` **tidak diubah**. Folder ini hanya berisi bagian khusus ASIC, dipisah per mesin AI:

| Folder | Isi | Status |
|---|---|---|
| [`xgboost/`](xgboost/README.md) | Chip ColdTrack: fisika + fitur + XGBoost (model di flash, tag HMAC). RTL pengganti khusus ASIC, makro DFFRAM, tes cocotb, config dan skrip LibreLane | Layout lengkap sampai signoff (RUN_A sampai RUN_U) |
| [`GRU/`](GRU/README.md) | Mesin GRU forecast + diagnosis, bobot dibaca dari flash. RTL, golden bit-exact, image model, tes cocotb | RTL terverifikasi, belum di-layout |

Setiap folder punya struktur yang sama:

```
<mesin>/
├── rtl/        modul khusus ASIC (top layout dan pembungkus, mis. xgboost/rtl/coldtrack_asic.sv)
├── golden/     model golden / pembuat image flash
├── tb/         tes cocotb (Verilator)
├── layout/     config dan skrip LibreLane, hasil di layout/runs/ (tidak masuk git)
├── metrics.csv ringkasan metrik layout run final 
└── laporan.pdf laporan layout
```

`wrapper/` untuk pembungkus Caravel (`user_project_wrapper`) ditambahkan di tiap folder saat integrasi Caravel.

## Perintah

```bash
# dari root repo
hw/asic/xgboost/layout/run_layout.sh                              # layout XGBoost (RTL -> GDS)
cd hw/asic/xgboost/tb && ../../../../.venv/bin/python -m pytest -q # tes ASIC XGBoost
.venv/bin/python hw/asic/GRU/tb/runner_gru.py                     # tes GRU (bit-exact terhadap golden)
.venv/bin/python -m hw.asic.xgboost.golden.flash_tag --buat-kunci # kunci model (sekali, rahasia)
```

Folder `xgboost/layout/runs/`, `xgboost/build/`, dan config sementara berisi kunci model HMAC; jangan dibagikan.
