# ColdTrack AI — Context untuk R2 (AI Model Engineer)

Taruh file ini di root folder kerja kamu (atau paste ke awal sesi Claude Code / assistant coding kamu) supaya AI-nya langsung punya konteks penuh tanpa perlu dijelaskan ulang.

## Tentang proyek ini

- **Kompetisi:** AI Innovation Challenge (AIC) COMPFEST 18
- **Tema:** AI for Backbone Economy — sub-area Smart Logistics
- **Deadline resmi:** 25 Agustus 2026, 23:55 WIB. **Target internal tim: submit 24 Agustus** (buffer 1 hari).
- **Tim:** 4 orang — R1 (AI Data Engineer), R2 (kamu, AI Model Engineer), R3 (Backend & MLOps), R4 (Frontend & Demo)
- **Masalah yang diangkat:** biaya logistik Indonesia 14,29% dari PDB (target 8% di 2045); Food Loss & Waste 23–48 juta ton/tahun akibat cold chain buruk dan pemantauan pasif/manual.
- **Solusi — ColdTrack AI:** mengubah telemetri IoT pasif menjadi keputusan proaktif. Tiga keluaran inti dari modelmu: prediksi suhu 15/30/60 menit ke depan, klasifikasi mode kegagalan, dan **Time-to-Breach (TTB)** — menit tersisa sebelum ambang terlampaui. TTB adalah fitur pembeda utama produk ini.

## Batasan MVP (wajib dipatuhi, tidak bisa dinegosiasikan)

- **Frontend:** satu alur interaksi inti. Dilarang dashboard analitik kompleks, dilarang otentikasi.
- **Backend:** pemrosesan sinkron saja. Dilarang background job, dilarang database terdistribusi. Wajib jalan via `docker compose up`.
- **AI — ini bagianmu:** fokus core inference, parameter statis saat demo. **Wajib di-fine-tune** — bukan sekadar memanggil API mentah, dan bukan dilatih dari nol tanpa transfer learning. Model harus ringan (target parameter puluhan ribu, bukan jutaan) agar inferensi CPU-only di laptop juri tetap cepat.

## Peran & kepemilikan tim

| Area | Pemilik |
|---|---|
| Simulator & data sintetik | R1 |
| Feature engineering & pembagian data | R1 bersama **R2 (kamu)** |
| Prapelatihan backbone | **R2 (kamu)** |
| Fine-tuning 3 head & tuning loss | **R2 (kamu)** |
| Baseline & ablation study | **R2 (kamu)** |
| Ekspor ONNX & kontrak model | **R2 (kamu)**, bersama R3 |
| API & mesin aturan | R3 |
| Docker & CI | R3 |
| Antarmuka & UX | R4 |
| Proposal §4.2 Alur Pengembangan Model | **R2 (kamu)** |

## Misi kamu

Menghasilkan satu berkas `coldtrack.onnx` yang bekerja, dapat direproduksi, dan metriknya jujur — bukan angka yang terlihat bagus tapi runtuh saat demo langsung. Kamu mengambil data dari R1 dan mengubahnya menjadi kemampuan prediktif lewat dua tahap pelatihan: prapelatihan pada data umum, lalu fine-tuning pada domain rantai dingin.

**Kamu baru benar-benar sibuk setelah R1 selesai (target akhir Minggu 1).** Sebelum itu, tugasmu adalah menyiapkan fondasi supaya tidak start dari nol saat data datang.

## Arsitektur model — WAJIB DIPAHAMI DI LUAR KEPALA

**Satu backbone bersama, tiga kepala tugas (multi-task learning):**

```
Input     : jendela geser 60 langkah x 12 fitur (interval 1 menit)
Backbone  : GRU 2 lapis, hidden 64, dropout 0.2   (~55 ribu parameter)

  head-1  Forecast     -> Dense(3)  : suhu pada t+15 / t+30 / t+60   [Loss: MAE]
  head-2  Failure Mode -> Dense(7)  : softmax 7 kelas                [Loss: CrossEntropy]
  head-3  Time-to-Breach -> Dense(1): menit hingga keluar ambang     [Loss: Huber]

Loss total = 1.0*MAE + 1.0*CE + 0.8*Huber   (bobot ditala di validasi)
Optimizer  = AdamW, lr 1e-3 (pretrain) -> 2e-4 (fine-tune)
```

12 fitur input (dari `docs/feature_schema.md`, dibekukan bersama R1): suhu ruang, kelembapan, suhu ambien, selisih suhu-ambien, laju perubahan suhu, status pintu, status reefer, kecepatan kendaraan, durasi berhenti berjalan, jumlah pengereman keras, jam dalam hari, indeks profil muatan.

Sembilan mode anomali dari R1 (A0–A8) dipetakan ke 7 kelas untuk head-2 — putuskan pemetaan (misal gabungkan A2+A4 sebagai "degradasi bertahap", A5+A6 sebagai "masalah sensor") sekali dan konsisten, dokumentasikan di model card.

## Strategi pelatihan dua tahap — ini inti "fine-tuning" yang disyaratkan lomba

**Tahap 1 — Prapelatihan.** Latih backbone GRU hanya dengan head-1 (forecast) di atas dataset deret waktu suhu IoT publik berskala besar (misal "Temperature Readings: IoT Devices" di Kaggle). Model belajar dinamika suhu umum: inersia termal, siklus harian, karakteristik derau sensor. Perkirakan 2–4 jam di Colab T4 gratis. Simpan sebagai `backbone_pretrained.pt`.

**Tahap 2 — Fine-tuning.** Muat bobot itu, pasang head-2 dan head-3 baru, bekukan lapisan GRU pertama selama 3 epoch pertama (cegah catastrophic forgetting), lalu buka semua lapisan dengan learning rate kecil (2e-4). Latih pada korpus cold chain sintetik dari R1. Di sinilah model belajar tanda tangan termal spesifik domain: pintu terbuka, degradasi kompresor, sensor macet.

**Cara menjelaskan ke juri:** "Kami tidak melatih dari nol dan tidak sekadar memanggil API. Kami mengambil representasi dinamika termal umum dari data IoT publik, lalu menalanya ke domain rantai dingin dengan korpus yang kami bangun sendiri." Siapkan grafik perbandingan kurva loss (fine-tune vs dari-nol) sebagai bukti visual — ini penting untuk proposal §4.2 dan video PoW.

## Baseline & evaluasi (wajib, jangan dilewati)

Juri akan bertanya "kenapa harus deep learning?" — siapkan jawabannya lewat eksperimen, bukan klaim:

- Baseline pembanding: regresi linear, **XGBoost**, dan **Isolation Forest** (untuk deteksi anomali murni) pada fitur agregat.
- Jika GRU tidak mengalahkan XGBoost, laporkan jujur dan pertimbangkan pakai XGBoost sebagai model produksi. Kejujuran menambah nilai kredibilitas.
- Ablation study: ukur kontribusi fine-tuning vs training dari nol; kontribusi multi-task learning vs single-task.
- Kalibrasi kepercayaan (temperature scaling) pada head-2 agar skor keyakinan tidak menyesatkan.

**Target metrik minimal:**

| Head | Metrik utama | Target |
|---|---|---|
| Forecast suhu | MAE @ t+30 menit | < 0.8°C |
| Mode kegagalan | Macro F1 | > 0.80 |
| Time-to-Breach | MAE | < 8 menit |
| Deteksi anomali | PR-AUC | > 0.85 (bukan akurasi — kelas tidak seimbang) |

## Ekspor ke produksi

- Ekspor ke **ONNX**, verifikasi kesetaraan numerik dengan output PyTorch (toleransi 1e-4).
- Target ukuran & latensi: inferensi < 300ms di CPU biasa (image backend tanpa PyTorch, hanya `onnxruntime`).
- Serahkan `coldtrack.onnx` + `labels.json` ke R3 untuk diintegrasikan ke endpoint FastAPI.

## Opsional — Tingkat C, jangan disentuh sebelum di atas selesai

Lapisan narasi LoRA pada LLM kecil (Qwen2.5-0.5B-Instruct / Llama-3.2-1B-Instruct) untuk mengubah rekomendasi jadi bahasa natural. Ini bonus presentasi, bukan jalur kritis — rule engine R3 tetap jalur utama. Keputusan dikerjakan atau tidak diambil di titik keputusan 16 Agustus (akhir Sprint 1), tergantung sisa waktu.

## Titik serah terima paling kritis: skema fitur

Selasa (hari ke-2 sprint), kamu dan R1 **wajib** duduk bersama sepakati 12 kolom fitur. Tulis di `docs/feature_schema.md`, bekukan. Posisimu di sesi ini: menguji apakah 12 kolom itu cukup untuk model, bukan sekadar menyetujui pasif.

## Timeline tugas kamu per sprint

**Sprint 0 — Minggu 1 (3–9 Agustus): siapkan fondasi, jangan menganggur**

- Sen: setup Colab (GPU aktif), kuasai arsitektur GRU 3-head
- Sel: sesi skema fitur bersama R1 (M1a)
- Rab–Kam: tulis kerangka kode training pakai data dummy, cari dataset publik untuk prapelatihan
- Jum: baseline XGBoost pertama sebagai jaring pengaman
- Sab: begitu data R1 keluar, uji pipeline loading (belum training penuh, cukup pastikan tidak error)
- Min: retrospektif bersama tim

**Sprint 1 — Minggu 2 (10–16 Agustus): jalur kritismu**

- Sen: latih backbone GRU (prapelatihan Tahap 1)
- Sel: **M3** backbone siap; mulai fine-tune (Tahap 2)
- Rab: tala bobot loss, latih baseline pembanding
- Kam: **M4** model v1 selesai + ekspor ONNX + verifikasi kesetaraan
- Jum: ablation study + confusion matrix
- Sab: uji generalisasi ke dataset IoT nyata (sim-to-real check dari sisi model)
- Min: **M5** — retrospektif, titik keputusan LoRA (kerjakan atau potong)

**Sprint 2 — Minggu 3 (17–23 Agustus): dokumentasi & kredibilitas ilmiah**

- Sen (Kemerdekaan, kapasitas separuh): mulai `model_card.md`
- Sel: finalisasi `metrics.json` & semua grafik
- Rab: ikut uji Docker klon segar (M6, seluruh tim)
- Kam: **tulis §4.2 proposal** + latihan penjelasan teknis untuk video
- Jum: rekam segmen model untuk video PoW
- Sab–Min: code freeze, cek deliverable final

## Artefak wajib kamu

`02_pretrain.ipynb`, `03_finetune.ipynb`, `04_eval.ipynb`, `coldtrack.onnx`, `reports/metrics.json`, `loss_curves.png`, `confusion_matrix.png`, `docs/model_card.md`, `docs/feature_schema.md` (bersama R1), bagian §4.2 proposal.

## Repo & konvensi

- Struktur: `backend/`, `frontend/`, `ml/` (rumahmu bersama R1), `docs/`
- Commit: **Conventional Commits** — `feat(model): tambah head time-to-breach pada backbone gru`, scope yang dipakai: `api, model, sim, ui, docker, ci, docs, rules, preprocess`
- Branch: `main` dilindungi, kerja di `feat/<nama-singkat>`, PR minimal 1 approval + CI hijau sebelum merge
- Colab → GitHub: clone repo di sel pertama (`!git clone https://github.com/<user>/coldtrack-ai.git`), commit & push balik pakai Personal Access Token (Settings → Developer settings → Personal access tokens di GitHub, centang akses `repo`)
- **Definition of Done:** merged via PR dengan CI hijau, commit conventional, terbukti jalan, dokumentasi terkait diupdate, sudah dicoba anggota lain

## Siapa yang menunggumu, siapa yang kamu tunggu

- **Kamu memblokir:** R3 (butuh `coldtrack.onnx` untuk integrasi endpoint asli, target Kamis Sprint 1)
- **Kamu diblokir oleh:** R1 (skema fitur Selasa Sprint 0, data penuh akhir Sprint 0). Kalau R1 telat, kabari PM (R4) hari itu juga — jangan diam menunggu.
