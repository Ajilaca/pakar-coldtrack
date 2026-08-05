# ColdTrack AI — Context untuk R1 (AI Data Engineer)

Taruh file ini di root folder kerja kamu (atau paste ke awal sesi Claude Code / assistant coding kamu) supaya AI-nya langsung punya konteks penuh tanpa perlu dijelaskan ulang.

## Tentang proyek ini

- **Kompetisi:** AI Innovation Challenge (AIC) COMPFEST 18
- **Tema:** AI for Backbone Economy — sub-area Smart Logistics
- **Deadline resmi:** 25 Agustus 2026, 23:55 WIB. **Target internal tim: submit 24 Agustus** (buffer 1 hari).
- **Tim:** 4 orang — R1 (kamu, AI Data Engineer), R2 (AI Model Engineer), R3 (Backend & MLOps), R4 (Frontend & Demo)
- **Masalah yang diangkat:** biaya logistik Indonesia 14,29% dari PDB (target 8% di 2045); Food Loss & Waste 23–48 juta ton/tahun, mayoritas terjadi di tahap distribusi akibat manajemen rantai dingin (cold chain) yang buruk dan pemantauan yang pasif/manual.
- **Solusi — ColdTrack AI:** sistem yang mengubah telemetri IoT pasif menjadi keputusan proaktif. Tiga keluaran inti: prediksi suhu 15/30/60 menit ke depan, klasifikasi mode kegagalan, dan **Time-to-Breach (TTB)** — estimasi menit tersisa sebelum suhu keluar ambang aman.

## Batasan MVP (wajib dipatuhi, tidak bisa dinegosiasikan)

- **Frontend:** satu alur interaksi inti (satu input → satu output AI). Dilarang dashboard analitik kompleks, dilarang sistem otentikasi.
- **Backend:** pemrosesan sinkron saja. Dilarang background job, dilarang database terdistribusi. Wajib bisa dijalankan penuh via `docker compose up`.
- **AI:** fokus core inference, parameter statis saat demo. Boleh pakai pre-trained model/API, tapi **wajib di-fine-tune** — bukan sekadar dipanggil mentah dan bukan dilatih dari nol tanpa transfer learning.

## Peran & kepemilikan tim

| Area | Pemilik |
|---|---|
| Simulator & data sintetik | **R1 (kamu)** |
| Riset & unduh dataset publik | **R1 (kamu)** |
| Feature engineering & pembagian data | **R1 bersama R2** |
| Prapelatihan & fine-tuning model | R2 |
| API & mesin aturan | R3 |
| Docker & CI | R3 |
| Antarmuka & UX | R4 |
| Proposal §4.1 Alur Dataset | **R1 (kamu)** |
| Business Value & Governance AI | R1 bersama R4 |

## Misi kamu

Menghasilkan korpus data rantai dingin berlabel yang **dipercaya juri**, karena tidak ada dataset publik berisi telemetri truk berpendingin Indonesia dengan label mode kegagalan. Kamu membangun sumber datanya dari kombinasi dataset IoT publik nyata (untuk realisme statistik) dan simulator termal berbasis fisika (untuk label kontrafaktual yang tidak mungkin didapat dari lapangan, terutama Time-to-Breach).

**Kamu adalah orang pertama yang harus produktif.** Seluruh tim (terutama R2) menunggu output kamu. Kalau kamu telat, semua orang ikut telat.

## Sumber dataset publik yang dipakai

| Dataset | Peran |
|---|---|
| Temperature Readings: IoT Devices (Kaggle) | Korpus prapelatihan utama — dinamika suhu umum |
| Intel Berkeley Lab Data | Pola kegagalan sensor nyata (drift, stuck-at, packet loss) |
| Smart Manufacturing IoT-Cloud Monitoring (Kaggle) | Kalibrasi struktur label & rasio kelas |
| IoT T-Sensor Dataset for Anomaly Detection (Kaggle) | Set uji eksternal generalisasi |
| UAH-DriveSet (Universidad de Alcalá) | Statistik perilaku pengemudi (akselerasi, pengereman keras) |
| Taxi Service Trajectory — Porto (UCI ML Repo) | Realisme rute: kemacetan, berhenti, kecepatan |
| NASA POWER API | Suhu ambien & radiasi matahari per jam per koordinat |

Catat lisensi tiap sumber di `docs/dataset_card.md` sebelum dipakai.

## Spesifikasi simulator termal

Persamaan inti (hukum pendinginan Newton + sumber beban):

```
T[t+1] = T[t] + dt * (
      - k_cool  * u[t]        * (T[t] - T_setpoint)     # kapasitas pendinginan
      + k_leak  * (T_amb[t] - T[t])                     # rembesan lewat insulasi
      + k_door  * door_open[t] * (T_amb[t] - T[t])      # pertukaran udara pintu
      + k_solar * solar[t] * (1 - shade[t])             # beban radiasi
  ) / C_thermal
  + noise(sigma = 0.15 C)

u[t] in [0,1] = kondisi kesehatan kompresor (1 = prima)
C_thermal     = massa muatan x kalor jenis
```

Kalibrasi target: perjalanan sehat 8 jam tetap dalam pita ambang dengan riak ±0,4°C; skenario reefer mati total mencapai ambang dalam 40–90 menit.

**Profil muatan (`cargo_profiles.yaml`):**

| Profil | Ambang | Toleransi |
|---|---|---|
| vaksin_2_8C | 2.0–8.0°C | 30 menit |
| daging_beku | -20 s.d. -18°C | 120 menit |
| ikan_segar | 0.0–4.0°C | 45 menit |
| sayur_buah | 4.0–8.0°C | 90 menit |
| produk_susu | 2.0–6.0°C | 60 menit |

**Katalog 9 mode anomali (A0–A8) — semua wajib diimplementasikan:**

| Kode | Mode | Mekanisme | Tanda khas |
|---|---|---|---|
| A0 | Sehat | tanpa gangguan | riak kecil di sekitar setpoint |
| A1 | Pintu terbuka terlalu lama | k_door naik 15–40x, 5–40 menit | lonjakan tajam + pemulihan lambat |
| A2 | Degradasi kompresor | u[t] meluruh 1.0→0.3 selama 2–6 jam | drift naik perlahan, tak terlihat manusia |
| A3 | Kegagalan reefer total | u[t] → 0 mendadak | kenaikan monoton ke suhu ambien |
| A4 | Kebocoran refrigeran | k_cool -40%, amplitudo melebar | osilasi suhu makin lebar |
| A5 | Sensor macet (stuck-at) | nilai dibekukan, suhu asli tetap berubah | varians nol — paling berbahaya |
| A6 | Sensor berderau/paket hilang | impuls ±5°C, celah 2–15 menit | outlier terisolasi + celah waktu |
| A7 | Kejut suhu ambien | kecepatan=0 >20 menit + radiasi tinggi | kenaikan berkorelasi durasi berhenti |
| A8 | Prapendinginan buruk | T[0] sudah di atas setpoint | mulai dari zona berisiko |

## Alur kerja 10 langkah (ringkas)

1. Tetapkan profil muatan dan pita ambang.
2. Bangkitkan rute (dari dataset Porto atau OSRM), resample ke 1 menit, sisipkan peristiwa berhenti.
3. Suntikkan kondisi ambien dari NASA POWER (suhu + radiasi per jam, diinterpolasi ke menit).
4. Jalankan model termal (persamaan di atas).
5. Suntikkan anomali dari katalog A0–A8 (distribusi disarankan: 60% sehat, 40% anomali merata antar mode).
6. Bangkitkan label: `is_anomaly` (biner), `failure_mode` (kategorikal), `time_to_breach` (hitung mundur dari kebenaran masa depan — cari titik pertama setelah t di mana suhu keluar pita, hitung selisih menit; jika tidak pernah terjadi beri nilai sentinel 999 dan mask dari loss).
7. Tambahkan lapisan realisme sensor: kuantisasi 0.1°C, derau Gaussian σ≈0.15°C, packet loss 2–5% bursty, jitter timestamp ±10 detik, reboot perangkat sesekali.
8. Randomisasi domain: sampel acak insulasi truk, massa muatan, kesehatan kompresor awal, gaya mengemudi, kota, waktu berangkat. Target 600–900 perjalanan, durasi 4–8 jam, resolusi 1 menit (~250–400 ribu baris).
9. Validasi sim-to-real: uji Kolmogorov–Smirnov pada distribusi suhu & laju perubahan, perbandingan ACF hingga lag 60, perbandingan kepadatan spektral daya, uji generalisasi (latih sintetik → uji data IoT nyata).
10. Pembagian data **per `trip_id`, bukan per baris** — 70/15/15, stratifikasi per mode kegagalan. Simpan di `data/processed/` dengan seed tetap, nama file mencantumkan versi (`v1_seed42_900trips.parquet`).

**Jebakan yang wajib dihindari:** jangan pernah memasukkan `is_anomaly` atau suhu masa depan sebagai fitur input model — itu kebocoran target. Tulis satu tes otomatis yang memeriksa daftar kolom fitur terhadap daftar terlarang.

## Titik serah terima paling kritis: skema fitur

Selasa (hari ke-2 sprint), kamu dan R2 **wajib** duduk bersama dan sepakati 12 kolom fitur input model. Tulis hasilnya di `docs/feature_schema.md` dan bekukan — jangan diubah sepihak setelahnya. Ini titik paling rawan di seluruh proyek karena seluruh kerja R2 bergantung pada bentuk data ini.

Fitur yang disarankan (12 kolom): suhu ruang, kelembapan, suhu ambien, selisih suhu-ambien, laju perubahan suhu, status pintu, status reefer, kecepatan kendaraan, durasi berhenti berjalan, jumlah peristiwa pengereman keras, jam dalam hari, indeks profil muatan.

## Timeline tugas kamu per sprint

**Sprint 0 — Minggu 1 (3–9 Agustus): kamu adalah prioritas tertinggi tim**

- Sen: unduh & EDA dataset publik
- Sel: **skema fitur dibekukan bersama R2** (M1a) — jangan molor dari hari ini
- Rab: bangun model termal inti
- Kam: katalog anomali A0–A8 selesai (M1b)
- Jum: bangkitkan 900 perjalanan, validasi grafik
- Sab: pembagian per trip_id, tes anti-kebocoran target
- Min: retrospektif; M2 (rangka end-to-end hidup) dicek tim

**Sprint 1 — Minggu 2 (10–16 Agustus): beban menurun, mulai bantu narasi**

- Sen: lapisan realisme sensor
- Sel: validasi sim-to-real (KS test, ACF)
- Rab: perbaiki simulator dari temuan validasi
- Kam: bangkitkan 5 CSV skenario demo untuk R3/R4
- Jum: hasilkan Gambar 4.1 (grafik sim-to-real)
- Sab: **tulis §4.1 proposal**
- Min: mulai bantu R4 di Business Value & Governance AI

**Sprint 2 — Minggu 3 (17–23 Agustus): dokumentasi & QA**

- Sen (Kemerdekaan, kapasitas separuh): rapikan notebook, mulai `dataset_card.md`
- Sel: draf Business Value bersama R4
- Rab: ikut uji Docker klon segar (M6, seluruh tim)
- Kam: draf Governance AI bersama R4
- Jum: baca ulang proposal sebagai penyunting
- Sab–Min: code freeze, cek deliverable final

## Artefak wajib kamu

`ml/simulator/`, `data/processed/*.parquet`, notebook `01_eda.ipynb`, grafik validasi sim-to-real, `docs/dataset_card.md`, `docs/feature_schema.md` (bersama R2), bagian §4.1 proposal.

## Repo & konvensi

- Struktur: `backend/`, `frontend/`, `ml/` (rumahmu), `docs/`
- Commit: **Conventional Commits** — `feat(sim): tambah katalog anomali degradasi kompresor`, scope yang dipakai: `api, model, sim, ui, docker, ci, docs, rules, preprocess`
- Branch: `main` dilindungi, kerja di `feat/<nama-singkat>`, PR minimal 1 approval + CI hijau sebelum merge
- **Definition of Done:** merged via PR dengan CI hijau, commit conventional, terbukti jalan (test/screenshot), dokumentasi terkait diupdate, sudah dicoba anggota lain

## Siapa yang menunggumu, siapa yang kamu tunggu

- **Kamu memblokir:** R2 (butuh skema fitur Selasa, data penuh akhir minggu)
- **Kamu diblokir oleh:** tidak ada — kamu jalur paling independen. Tidak ada alasan telat.
