# ColdTrack AI — Context untuk R3 (Backend & MLOps Engineer)

Taruh file ini di root folder kerja kamu (atau paste ke awal sesi Claude Code / assistant coding kamu) supaya AI-nya langsung punya konteks penuh tanpa perlu dijelaskan ulang.

## Tentang proyek ini

- **Kompetisi:** AI Innovation Challenge (AIC) COMPFEST 18
- **Tema:** AI for Backbone Economy — sub-area Smart Logistics
- **Deadline resmi:** 25 Agustus 2026, 23:55 WIB. **Target internal tim: submit 24 Agustus** (buffer 1 hari).
- **Tim:** 4 orang — R1 (AI Data Engineer), R2 (AI Model Engineer), R3 (kamu, Backend & MLOps), R4 (Frontend & Demo)
- **Masalah yang diangkat:** biaya logistik Indonesia 14,29% dari PDB (target 8% di 2045); Food Loss & Waste 23–48 juta ton/tahun akibat cold chain buruk.
- **Solusi — ColdTrack AI:** telemetri IoT pasif diubah jadi keputusan proaktif. Keluaran: prediksi suhu, klasifikasi mode kegagalan, dan Time-to-Breach (menit tersisa sebelum ambang terlampaui).

## Batasan MVP — ini terutama tanggung jawabmu untuk dijaga

- **Frontend:** satu alur interaksi inti (satu input → satu output AI). Dilarang dashboard analitik kompleks, dilarang otentikasi.
- **Backend — ini bagianmu:** **pemrosesan sinkron saja.** Dilarang keras: background job (Celery/RQ/cron/webhook), database terdistribusi, atau database sama sekali. Sistem harus **stateless**. Wajib bisa dijalankan penuh via satu perintah `docker compose up`, tanpa langkah manual tambahan.
- **AI:** fokus core inference, parameter statis saat demo (dibaca dari `config.yaml`, dibekukan saat rilis). Wajib di-fine-tune (tanggung jawab R2, tapi kamu yang mengintegrasikan hasilnya).

## Peran & kepemilikan tim

| Area | Pemilik |
|---|---|
| Simulator & data sintetik | R1 |
| Prapelatihan & fine-tuning model | R2 |
| Ekspor ONNX & kontrak model | R2, bersama **R3 (kamu)** |
| API & mesin aturan | **R3 (kamu)** |
| Docker & CI | **R3 (kamu)** |
| Antarmuka & UX | R4 |
| Kebersihan repo & rilis | **R3 (kamu)** |
| Proposal §4.3 Alur Integrasi | **R3 (kamu)** |

## Misi kamu

Memastikan `docker compose up` berhasil di komputer mana pun, sekali jalan, tanpa penjelasan tambahan. Kamu adalah orang yang membuka jalan bagi R4 (lewat kontrak API & mock) dan menjaga repo tetap rapi sejak hari pertama. **Kamu punya dua deadline di hari-hari awal yang memblokir orang lain — jangan telat di sana.**

## Kontrak API — bekukan ini di hari ke-2, jangan molor

Satu endpoint inti saja. Endpoint tambahan = permukaan risiko tambahan yang tidak perlu.

```
POST /api/v1/analyze

Request:
{
  "shipment_id": "TRK-JKT-0417",
  "cargo_profile": "vaksin_2_8C",
  "readings": [
    { "ts": "2026-08-20T07:00:00+07:00", "temp_c": 4.2, "humidity": 71.5,
      "ambient_c": 31.4, "door_open": false, "reefer_on": true,
      "lat": -6.2118, "lon": 106.8456, "speed_kmh": 24.0,
      "harsh_events": 0 }
  ]
}

Response 200 OK (target latensi < 1000 ms):
{
  "status": "KRITIS",
  "risk_index": 0.87,
  "time_to_breach_min": 23.4,
  "failure_mode": { "label": "degradasi_kompresor", "confidence": 0.91 },
  "forecast": { "t15": 6.9, "t30": 8.4, "t60": 11.2 },
  "drivers": [
    { "feature": "laju_kenaikan_suhu", "value": "+0.13 C/mnt", "contribution": 0.44 },
    { "feature": "delta_suhu_ambien",  "value": "27.2 C",      "contribution": 0.31 },
    { "feature": "durasi_reefer_aktif","value": "196 mnt",     "contribution": 0.18 }
  ],
  "actions": [
    { "priority": 1, "text": "Hubungi pengemudi: hentikan di titik teduh terdekat, periksa kondensor.", "eta_min": 5 },
    { "priority": 2, "text": "Siapkan truk pengganti dari Depo Cakung (11 km, ~19 menit).", "eta_min": 19 },
    { "priority": 3, "text": "Beri tahu penerima; siapkan berita acara ekskursi suhu sesuai CDOB.", "eta_min": 10 }
  ],
  "model_version": "coldtrack-gru-v1.3",
  "inference_ms": 187
}
```

Endpoint pendukung: `GET /health` (probe untuk Docker healthcheck), `GET /api/v1/scenarios` (daftar 5 skenario demo). **Tidak ada endpoint lain.**

## Tumpukan teknologi

| Lapisan | Teknologi | Alasan |
|---|---|---|
| Web framework | FastAPI + Uvicorn (1 worker) | Sinkron, dokumentasi OpenAPI otomatis di `/docs` |
| Validasi | Pydantic v2 | Skema input/output eksplisit, error 422 informatif |
| Numerik | NumPy + Pandas | Preprocessing deret waktu |
| Runtime model | `onnxruntime` (CPU) | Tanpa PyTorch di image produksi — image turun dari ~2.5GB ke ~450MB |
| Konfigurasi | `config.yaml` + `pydantic-settings` | Semua parameter statis terpusat, dapat diaudit juri |
| Penyimpanan | **Tidak ada database** | Skenario demo = file CSV statis di `/app/data/scenarios/` |
| Logging | `structlog` ke stdout (JSON) | Terlihat di `docker compose logs` — bukti "jejak audit" saat demo |
| Pengujian | pytest + httpx TestClient | Minimal 8 tes: skema, 5 skenario, latensi, penanganan CSV rusak |

## Alur pemrosesan yang kamu bangun

```
[ WEB Next.js ] --POST /api/v1/analyze--> [ API FastAPI ]
   a. Validasi skema (Pydantic v2)
   b. Preprocessing: resample 1 menit, imputasi, windowing
   c. Inferensi ONNX Runtime -> forecast | mode kegagalan | TTB   (dari model R2)
   d. Skoring Cargo Risk Index (bobot statis dari config.yaml)
   e. Mesin aturan deterministik -> tiga tindakan berprioritas
   f. Lapisan penjelasan (kontribusi fitur, pendekatan permutasi sudah cukup)
   -> satu respons JSON, target < 1 detik
```

Mesin aturan dan lapisan penjelasan adalah **jalur utama produk** — jangan bergantung pada komponen AI opsional (LoRA) milik R2 sebagai jalur kritis. Kalau R2 memutuskan mengerjakan LoRA, sediakan env var `ENABLE_LLM=false` sebagai default dan fallback otomatis ke template kalau LLM gagal/lambat.

## Dockerisasi

```yaml
services:
  api:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      - CONFIG_PATH=/app/config.yaml
      - ENABLE_LLM=false
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      retries: 5

  web:
    build: ./frontend
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      api: { condition: service_healthy }
```

- Backend: multi-stage build dari `python:3.11-slim`. Bobot `.onnx` **disalin ke dalam image**, bukan diunduh saat runtime — jangan asumsikan laptop juri punya internet.
- Frontend: multi-stage dengan `output: "standalone"` di `next.config.js`.
- `.dockerignore` wajib buang `node_modules`, `.venv`, `notebooks/`, `data/raw/`.
- **Uji penerimaan wajib** (Rabu, akhir Sprint 2 — M6): klon segar di laptop anggota lain, `docker compose up --build`, buka localhost:3000, dapatkan hasil. Kalau butuh langkah manual apa pun, itu bug.

## Setup repo GitHub (kamu yang memegang ini di hari pertama)

Struktur folder:

```
coldtrack-ai/
  README.md  LICENSE  .gitignore  docker-compose.yml
  .github/workflows/ci.yml
  backend/  Dockerfile  requirements.txt  config.yaml
    app/ main.py schemas.py preprocess.py inference.py rules.py explain.py
    models/coldtrack.onnx  labels.json
    data/scenarios/*.csv
    tests/
  frontend/  Dockerfile  package.json  next.config.js
  ml/  simulator/  notebooks/  export_onnx.py  reports/
  docs/  architecture.md  dataset_card.md  model_card.md  ai_governance.md  feature_schema.md
```

GitHub Actions CI: `ruff check` + `pytest` pada perubahan di `backend/**`, plus validasi Conventional Commits pada setiap PR (misal via `wagoid/commitlint-github-action`).

## Timeline tugas kamu per sprint

**Sprint 0 — Minggu 1 (3–9 Agustus): dua deadline pertamamu memblokir seluruh tim**

- Sen: **setup repo GitHub, invite semua orang, aktifkan CI dasar (M0)**
- Sel: **bekukan kontrak API v0, publikasikan ke tim, buat endpoint tiruan (mock)** — R4 menunggu ini
- Rab: kerangka FastAPI dasar (`/health`, skema Pydantic)
- Kam: modul preprocessing (resample, imputasi)
- Jum: sambungkan endpoint tiruan supaya R4 bisa integrasi penuh
- Sab: mesin aturan v1 dari `config.yaml`
- Min: pimpin sesi integrasi Jumat sore + demo internal, retrospektif; **M2 — cek apakah rangka end-to-end sudah hidup**

**Sprint 1 — Minggu 2 (10–16 Agustus): ganti mock dengan model asli**

- Sen: bungkus ONNX Runtime + pemuat model
- Sel: skoring risiko + lapisan penjelasan
- Rab: uji pytest untuk 5 skenario
- Kam: sambungkan ONNX (dari R2) ke endpoint asli — mock resmi dipensiunkan
- Jum: optimasi latensi (target p95 < 1 detik)
- Sab: perbaikan bug integrasi
- Min: **M5** — cek lima skenario berjalan dengan AI asli, tidak ada mock tersisa

**Sprint 2 — Minggu 3 (17–23 Agustus): kemasan final**

- Sen (Kemerdekaan, kapasitas separuh): ringan saja
- Sel: Dockerfile multi-stage + compose final
- Rab: **M6 — uji Docker di 2 laptop berbeda, seluruh tim ikut**
- Kam: README + tangkapan layar arsitektur + **tulis §4.3 proposal**
- Jum: bekukan `config.yaml` & parameter statis final
- Sab: **M9 code freeze — tag rilis v1.0.0**
- Min: cek semua deliverable final bersama tim

## Artefak wajib kamu

`backend/`, `docker-compose.yml`, `.github/workflows/ci.yml`, laporan latensi p50/p95, riwayat commit bersih, bagian §4.3 proposal, tabel kepatuhan batasan MVP.

## Repo & konvensi

- Commit: **Conventional Commits** — `feat(api): tambah endpoint analyze dengan skema pydantic`, scope: `api, model, sim, ui, docker, ci, docs, rules, preprocess`
- Branch: `main` dilindungi (branch protection rule di GitHub Settings), kerja di `feat/<nama-singkat>`, PR minimal 1 approval + CI hijau sebelum merge
- Tag rilis: `v0.1.0` (M2), `v0.5.0` (M5), `v1.0.0` (M9 code freeze)
- **Definition of Done:** merged via PR dengan CI hijau, commit conventional, terbukti jalan via `docker compose up` (bukan cuma di mesin sendiri), ada test/screenshot bukti, dokumentasi terkait diupdate, sudah dicoba anggota lain

## Siapa yang menunggumu, siapa yang kamu tunggu

- **Kamu memblokir:** seluruh tim (repo, Senin), R4 (kontrak API & mock, Selasa)
- **Kamu diblokir oleh:** R2 (butuh `coldtrack.onnx` untuk integrasi endpoint asli, target Kamis Sprint 1)

Kamu tidak boleh telat di dua hari pertama sprint — itu titik di mana seluruh tim menunggumu.
