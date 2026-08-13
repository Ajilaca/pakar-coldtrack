# Update Tugas R2 — AI Model Engineer

**Per 13 Agustus 2026** · Deadline internal tim: **24 Agustus** — sisa **11 hari**
Disusun berdasarkan audit repositori terhadap `role/context-r2-ai-model.md`.

---

## Yang sudah selesai

Seluruh artefak wajib tersedia dan sudah masuk `main` lewat PR #9 dan #10.

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

Integrasi ke backend sudah diverifikasi: kedua model termuat benar di `main`, daftar 7 kelas
terbaca dari `labels.json`, dan ketiga bug yang dilaporkan ke R3 sudah diperbaiki.

---

## Tiga keputusan yang perlu dibawa ke tim

Belum dijawab, dan memengaruhi tulisan orang lain.

| Keputusan | Rekomendasi |
|---|---|
| Apakah tim setuju menulis terbuka bahwa **XGBoost mengungguli GRU** dan **prapelatihan merugikan**? | pertahankan — lebih aman daripada ketahuan saat sesi tanya jawab juri |
| Narasi §4.2 berubah dari rencana awal; R4 perlu tahu sebelum menulis naskah video | wajib disampaikan |
| Macro F1 (0,573) dan PR-AUC (0,691) belum tercapai — dilaporkan apa adanya, atau target direvisi? | laporkan apa adanya; menurunkan target setelah melihat hasil akan terbaca sebagai menyesuaikan ukuran |

---

## Tugas yang masih berjalan

### Mendukung video PoW (R4)

Segmen "Model & fine-tuning" berdurasi 90 detik. Materi siap pakai: `loss_curves.png`,
`confusion_matrix.png`, `ttb_by_horizon.png`, `ablation_results.json`, `baseline_metrics.json`.
Perlu dijadwalkan sesi rekaman penjelasan teknisnya.

### Ikut uji Docker klon segar (M6)

Verifikasi kedua model termuat benar di dalam kontainer dan keluarannya sesuai.

### Menjaga kesesuaian bila dataset berubah

R1 akan menyediakan lima skenario demo baru berisi ≥ 60 bacaan. Itu **tidak** memerlukan pelatihan
ulang — skenario hanya dipakai saat inferensi.

Tetapi bila R1 membangkitkan ulang **dataset pelatihan** (misal untuk memperbaiki ketimpangan split
TTB), seluruh pipeline perlu dijalankan ulang:

```bash
python -m ml.preprocess.build_windows
python -m ml.finetune               # ~35 menit
python -m ml.export_onnx
python -m ml.export_ttb_xgboost
python -m ml.make_reports
```

Angka di `model_card.md`, `metrics.json`, dan §4.2 wajib diperbarui setelahnya.

---

## Hasil audit lintas peran (13 Agustus)

R2 menelusuri jalur permintaan dari frontend sampai model dan menemukan dua masalah yang **belum
pernah muncul** karena frontend masih memakai data tiruan:

1. **Nama field tidak cocok.** Frontend mengirim `temperature_c`/`ambient_temp_c`; backend meminta
   `temp_c`/`ambient_c` plus enam field lain yang tidak dikirim sama sekali. Setiap permintaan akan
   ditolak 422 begitu `USE_MOCK=false`.
2. **Skenario demo terlalu pendek.** Backend mewajibkan ≥ 60 bacaan; skenario frontend punya 31,
   skenario backend punya 3–5.

Sudah dilaporkan ke R3 dan R4 lewat `update-r3-backend.md` dan `update-r4-frontend.md`, serta
permintaan skenario baru ke R1 lewat `update-r1-ai-data.md`.

**Status proposal tim: baru 1 dari 8 bagian terisi** (§4.2 milik R2), dengan bagian Latar Belakang
milik R4 sudah lewat tenggat. Ini risiko terbesar tim saat ini — bukan lagi kode.

---

## Karena pekerjaan R2 sudah selesai

Waktu paling bernilai sekarang dipakai membantu bagian yang tertinggal:

- **Bantu R1 membuat grafik sim-to-real** — angkanya sudah ada di `dataset_card.md`, datanya ada di
  repositori, dan alatnya sudah tersedia di `ml/`
- **Bantu menyusun kerangka §4.1 dan §4.3** — bukan mengisi, cukup judul bagian dan poin yang perlu
  dijawab, supaya R1 dan R3 tinggal menulis
- **Bantu R1 mengekspor skenario demo dari dataset v4** — pekerjaan ini paling dekat dengan
  perkakas yang sudah dikuasai R2
