# Update Tugas R2 — AI Model Engineer

**Per 7 Agustus 2026** · Deadline internal tim: **24 Agustus** (sisa 17 hari)
Disusun berdasarkan audit repositori terhadap `role/context-r2-ai-model.md`.

---

## Yang sudah selesai

Seluruh artefak wajib tersedia dan sudah masuk `main`.

| Artefak | Status |
|---|---|
| `ml/notebooks/02_pretrain.ipynb`, `03_finetune.ipynb`, `04_eval.ipynb` | selesai |
| `ml/reports/coldtrack.onnx` + `labels.json` | selesai |
| `ml/reports/coldtrack_ttb.onnx` (model Time-to-Breach) | selesai |
| `ml/reports/metrics.json` | selesai |
| `loss_curves.png`, `confusion_matrix.png`, `ttb_by_horizon.png` | selesai |
| `docs/model_card.md` (267 baris) | selesai |
| `docs/feature_schema.md` (bersama R1) | selesai |
| `docs/proposal_4_2_alur_pengembangan_model.md` | selesai |
| Baseline pembanding + dua ablation study | selesai |

### Hasil akhir (split test)

| Head | Metrik | Hasil | Target | Status |
|---|---|---|---|---|
| Prediksi suhu | MAE @ t+30 | **0,202 °C** | < 0,8 °C | tercapai |
| Mode kegagalan | Macro F1 | 0,573 | > 0,80 | belum |
| Time-to-Breach | MAE (≤ 30 menit) | **7,60 menit** | < 8 menit | tercapai |
| Deteksi anomali | PR-AUC | 0,691 | > 0,85 | belum |

Dua dari empat target tercapai. Sistem final memakai dua model: GRU untuk prediksi suhu dan
klasifikasi, XGBoost untuk Time-to-Breach.

---

## Yang masih menunggu keputusan tim

### 1. Nada penyampaian keterbatasan di model card dan §4.2

Tiga hal ditulis terbuka:

- XGBoost mengungguli GRU pada seluruh metrik
- Prapelatihan tidak memberi manfaat dan justru merugikan
- Model belum pernah divalidasi terhadap perjalanan truk sungguhan

Perlu dikonfirmasi tim apakah tingkat keterbukaan ini disepakati. Rekomendasi R2:
**dipertahankan.** Batasan yang dinyatakan sendiri lebih aman daripada ketahuan saat sesi tanya
jawab juri, dan menunjukkan tim yang menguji asumsinya sendiri.

### 2. Narasi §4.2 berbeda dari rencana awal

`context-r2` baris 67 menyiapkan kalimat: *"Kami tidak melatih dari nol... kami mengambil
representasi dinamika termal umum dari data IoT publik, lalu menalanya ke domain rantai dingin."*

**Kalimat itu tidak lagi akurat.** Eksperimen membuktikan prapelatihan merugikan, sehingga model
produksi dilatih dari nol. §4.2 ditulis dengan narasi pengganti: *"Kami merencanakan transfer
learning, mengujinya secara serius, menemukan bahwa pendekatan itu tidak berhasil pada domain ini,
dan menjelaskan mengapa."*

R4 perlu tahu ini karena memengaruhi naskah video PoW segmen "Model & fine-tuning" (menit 2:30–4:00).

### 3. Target metrik yang belum tercapai

Macro F1 (0,573 vs 0,80) dan PR-AUC (0,691 vs 0,85) belum tercapai, dan sudah mentok setelah
serangkaian perbaikan. Perlu diputuskan tim: dilaporkan apa adanya sebagai belum tercapai, atau
target di dokumen internal direvisi ke angka yang dapat dipertanggungjawabkan.

Rekomendasi R2: **laporkan apa adanya.** Menurunkan target setelah melihat hasil akan terbaca
sebagai menyesuaikan ukuran agar terlihat berhasil.

---

## Tugas yang masih berjalan

### Mendukung video PoW (R4)

Segmen "Model & fine-tuning" berdurasi 90 detik. Materi siap pakai:

- `ml/reports/loss_curves.png` — bukti visual prapelatihan tidak membantu
- `ml/reports/confusion_matrix.png` — akurasi per kelas
- `ml/reports/ttb_by_horizon.png` — batas kegunaan Time-to-Breach
- `ml/reports/ablation_results.json` dan `baseline_metrics.json` — seluruh angka pembanding

Perlu dijadwalkan bersama R4 untuk merekam penjelasan teknisnya.

### Ikut uji Docker klon segar (M6)

Seluruh tim, dijadwalkan Rabu Sprint 2. R2 memverifikasi bahwa kedua model termuat benar di dalam
kontainer dan keluarannya sesuai.

### Menjaga kesesuaian bila dataset berubah

Bila R1 membangkitkan ulang dataset (misal untuk memperbaiki ketimpangan split TTB), seluruh
pipeline perlu dijalankan ulang:

```bash
python -m ml.preprocess.build_windows
python -m ml.finetune               # ~35 menit
python -m ml.export_onnx
python -m ml.export_ttb_xgboost
python -m ml.make_reports
```

Angka di `model_card.md`, `metrics.json`, dan §4.2 wajib diperbarui setelahnya.

---

## Catatan untuk R3

Ketiga bug integrasi yang dilaporkan sudah diperbaiki di branch `feat/r3-sprint-0` — gerbang TTB
pada `failure_prob`, penamaan A8, dan sinkronisasi `cargo_profiles`. Sudah diverifikasi R2.

**Empat commit tersebut belum masuk `main`.** Selama belum di-merge, `main` masih berisi versi
backend yang menampilkan Time-to-Breach palsu untuk truk sehat. Ini perlu diselesaikan sebelum
demo apa pun dijalankan dari `main`.
