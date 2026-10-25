# ml/

Kode latih dan eksperimen model awal (Fase 1 sampai 8). Latih ulang dan benchmark terbaru ada di
`bench/`; kode di sini dipertahankan karena `bench/` dan `hw/` masih mengimpornya.

| Folder | Isi |
|---|---|
| `training/` | GRU multi-tugas: `model.py` (arsitektur), `scaler.py`, `pretrain.py`, `finetune.py` |
| `evaluation/` | `evaluate.py` (metrik resmi), `baselines.py`, `ablation.py`, `make_reports.py`, `make_loss_curves.py` |
| `export/` | `export_onnx.py` (GRU), `export_ttb_xgboost.py` (XGBoost TTB) |
| `preprocess/` | Jendela 60 menit, korpus pretraining Berkeley, ekspor skenario demo dan seed armada, perbaikan label TTB v1 |
| `sensor_health/` | Model sensor-health dari data Intel Berkeley Lab |
| `simulator/` | Notebook simulator termal yang membangkitkan data sintetis (lihat README di dalamnya) |
| `notebooks/` | Notebook eksplorasi |
| `reports/` | Metrik, grafik, dan ONNX hasil Fase 5 sampai 6 |
| `tests/` | Tes kontrak data (label tidak boleh bocor jadi fitur) |
| `legacy_colab/` | Alur latihan Colab awal yang saling mengimpor tanpa paket: `run_train.py`, `train_gru.py`, `prep_windows.py`, `ttb_features.py`, dan salinan lama modul `backend/app/core/` (`engine`, `observer`, `door_budget`, `sensor_rules`, `coldtrack_sim`). `sensor_rules.py` dan `ttb_features.py` masih identik dengan backend; lima lainnya sudah berbeda. Sumber kebenaran adalah `backend/app/core/` |

Artefak model generasi pertama di folder ini: `coldtrack_gru.onnx`, `coldtrack_ttb.onnx`, `gru_v1.pt`,
`scalers_v1.json`, `xgb_ttb.json`, `xgb_features.txt`. Konteks Checkpoint 2: `CHECKPOINT2_CONTEXT.md`.

Modul dijalankan dari root repo, misalnya `python -m ml.export.export_onnx`. Folder `legacy_colab/` dijalankan
dari dalam folder itu, mis. `python run_train.py --data dataset_v1.parquet`.
