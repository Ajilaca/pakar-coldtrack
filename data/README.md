# data/

Dataset sintetis hasil simulator (`ml/simulator/`). Tidak ada data logger asli.

| Berkas | Isi |
|---|---|
| `processed/v1_seed1000_700trips.parquet` | Generasi 1 simulator |
| `processed/v1_seed1000_700trips_ttbfix.parquet` | v1 dengan perbaikan label TTB |
| `processed/v2_seed1000_700trips.parquet`, `v3_...` | Generasi 2 dan 3 |
| `processed/v4_seed1000_700trips.parquet` | Generasi terkini: 700 trip, 251.073 baris, split train/val/test per trip. Dipakai model v3 dan seluruh `bench/`, `hw/` |

Skema kolom, rumus simulator, dan keterbatasan data: `docs/train_ai.md`. Split test hanya dibuka
sekali per model; setiap pembukaan dicatat di `bench/results/test_access_log.json`.
