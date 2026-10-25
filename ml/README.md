# ml/

Kode latih dan eksperimen model awal (Fase 1 sampai 8). Latih ulang dan benchmark terbaru ada di
`bench/`; kode di sini dipertahankan karena `backend/` dan `bench/` masih mengimpornya.

| Path | Isi |
|---|---|
| `simulator/` | Notebook simulator termal yang membangkitkan data sintetis (lihat README di dalamnya) |
| `preprocess/` | Jendela 60 menit, korpus pretraining Berkeley, ekspor skenario demo dan seed armada, perbaikan label TTB v1 |
| `model.py`, `pretrain.py`, `finetune.py`, `train_gru.py` | GRU multi-tugas: pretraining, fine-tuning, latihan penuh |
| `run_train.py`, `prep_windows.py`, `scaler.py`, `ttb_features.py` | Alur latihan lokal dan fitur TTB |
| `export_onnx.py`, `export_ttb_xgboost.py` | Ekspor ONNX (GRU dan XGBoost TTB) |
| `evaluate.py`, `baselines.py`, `ablation.py`, `make_reports.py`, `make_loss_curves.py` | Metrik resmi, pembanding, ablation, laporan |
| `sensor_health/` | Model sensor-health dari data Intel Berkeley Lab |
| `reports/` | Metrik, grafik, dan ONNX hasil Fase 5 sampai 6 |
| `notebooks/` | Notebook eksplorasi |
| `tests/` | Tes kontrak data (label tidak boleh bocor jadi fitur) |
| `engine.py`, `observer.py`, `door_budget.py`, `sensor_rules.py`, `coldtrack_sim.py`, `prep_windows.py`, `ttb_features.py` | **Salinan lama** modul di `backend/app/core/`. `sensor_rules.py` dan `ttb_features.py` masih identik; `engine`, `observer`, `door_budget`, `coldtrack_sim`, `prep_windows` sudah berbeda dari backend. Sumber kebenaran adalah `backend/app/core/` |
| `coldtrack_gru.onnx`, `coldtrack_ttb.onnx`, `gru_v1.pt`, `scalers_v1.json`, `xgb_ttb.json`, `xgb_features.txt` | Artefak model generasi pertama |

Konteks Checkpoint 2: `CHECKPOINT2_CONTEXT.md`. Jalankan modul dari root repo, misalnya
`python -m ml.export_onnx`.
