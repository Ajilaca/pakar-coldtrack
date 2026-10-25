# backend/

API FastAPI, worker armada, dan mesin aturan. Mesin aturan (`app/core/engine.py`) memutuskan status
AMAN/WASPADA/KRITIS dan TTB; model ML hanya mengusulkan diagnosis.

| Path | Isi |
|---|---|
| `app/core/` | Mesin fisika dan aturan: `engine.py` (status, TTB), `observer.py` (suhu muatan), `door_budget.py`, `sensor_rules.py`, `coldtrack_sim.py` |
| `app/inference.py`, `app/preprocess.py` | Jalur `/analyze`: fitur, ONNX, penjaga label |
| `app/models/` | Orkestrator armada: `condition` (engine + v3) dan `sensor_health` |
| `app/workers/` | `ingest` (MQTT ke TimescaleDB), `infer` (jendela 1 menit), `virtual_trucks` (memutar ulang trip v4 val; `SIM_LEWATI` melewati truk ber-chip) |
| `app/edge.py` | Hasil chip edge (KV260): verifikasi HMAC dan rantai hash per bacaan, lalu dipakai `infer` sebagai status, TTB, dan diagnosis tanpa hitung ulang (provider `edge_kv260`) |
| `app/routers/` | REST `/api/v1/fleet/*`, insiden, SSE `/stream`, webhook vendor |
| `app/fleet/`, `app/db/`, `app/ingest/`, `app/adapters/` | Logika armada, akses database, penerima telemetri, adaptor vendor |
| `migrations/` | Skema TimescaleDB 001 sampai 006 (`006`: tabel `edge_results`) |
| `models/` | ONNX yang dilayani: `coldtrack_v3.onnx` (GRU, default), `coldtrack_ttb_window.onnx` (XGBoost TTB), kandidat di `candidates/` |
| `data/fleet/`, `data/scenarios/` | Seed 24 truk virtual dan 5 skenario demo |
| `config.yaml` | Pilihan provider model, profil kargo, parameter armada |
| `tests/` | Tes pytest |

```bash
cd backend && ruff check . && pytest
```

Seluruh armada dijalankan dari root repo dengan `docker compose --profile dev up -d --build`.
