# Update Tugas R3 — Backend & MLOps Engineer

**Per 13 Agustus 2026** · Deadline internal tim: **24 Agustus** — sisa **11 hari**
Disusun R2 berdasarkan audit repositori terhadap `role/context-r3-backend.md`.

---

## Yang sudah selesai

| Artefak | Status |
|---|---|
| `backend/app/` — `main`, `schemas`, `preprocess`, `inference`, `rules`, `explain`, `scenarios` | selesai |
| Endpoint `POST /api/v1/analyze`, `GET /health`, `GET /api/v1/scenarios` | selesai |
| `docker-compose.yml` + healthcheck | selesai |
| `.github/workflows/ci.yml` + `commitlint.yml` | selesai |
| 22 tes pytest | melampaui syarat minimal 8 |
| Branch `feat/r3-sprint-0` (PR #8) | sudah masuk `main` |

Integrasi model diverifikasi R2 dan hasilnya baik: 12 kolom fitur urut persis sesuai kontrak, rumus
turunan benar, nilai dikirim mentah tanpa normalisasi ganda, daftar kelas dibaca dari `labels.json`
alih-alih ditulis tetap di kode, dan kedua model ONNX (`coldtrack.onnx` + `coldtrack_ttb.onnx`)
termuat benar.

Tiga bug yang dilaporkan R2 juga sudah diperbaiki, ditambah penolakan payload di bawah 60 bacaan
yang menjawab kekhawatiran soal padding.

---

## Mendesak — temuan uji integrasi end-to-end

R2 menelusuri jalur permintaan dari frontend sampai model. **Frontend dan backend belum pernah
benar-benar saling bicara**, dan kontraknya tidak cocok. Ini belum ketahuan karena frontend masih
memakai data tiruan (`NEXT_PUBLIC_USE_MOCK` bernilai `true` secara default).

### Masalah 1 — nama field tidak cocok

Frontend mengirim:

```
{ timestamp?, temperature_c, ambient_temp_c?, door_open? }
```

Backend mewajibkan (`schemas.py`, kelas `TelemetryReading`):

```
{ ts, temp_c, humidity, ambient_c, door_open, reefer_on, lat, lon, speed_kmh, harsh_events }
```

Hampir seluruh nama berbeda, dan **enam field wajib tidak dikirim sama sekali**. Setiap permintaan
akan ditolak dengan galat 422.

**Perlu diputuskan bersama R4:** frontend menyesuaikan diri ke skema backend, atau backend
melonggarkan field yang sebenarnya tidak dipakai model?

Sebagai bahan pertimbangan — dari 12 fitur model, yang benar-benar dipakai: `temp_c`, `humidity`,
`ambient_c`, `door_open`, `reefer_on`, `speed_kmh`, `harsh_events`. Sedangkan `lat` dan `lon`
**tidak masuk sebagai fitur model sama sekali** dan bisa dijadikan opsional tanpa memengaruhi
prediksi.

### Masalah 2 — skenario demo lebih pendek dari syarat minimum

| Sumber | Jumlah bacaan | Syarat |
|---|---|---|
| `backend/data/scenarios/*.json` | 3–5 | ≥ 60 |
| Skenario di frontend (`N = 31`) | 31 | ≥ 60 |

Berkas tes sudah mencatat bahwa skenario JSON memang pendek dan di-*pad* jadi 60 saat pengujian —
tetapi jalur demo sungguhan belum dibereskan. Akibatnya **seluruh skenario demo akan ditolak.**

R2 sudah meminta R1 menyediakan lima skenario pengganti berisi minimal 60 bacaan, diambil dari
dataset v4 dengan format mengikuti `TelemetryReading`. Perlu dikoordinasikan agar tidak ada dua
pihak yang mengerjakan hal sama.

### Uji ulang setelah diperbaiki

Jalankan dengan `NEXT_PUBLIC_USE_MOCK=false` **minggu ini**, jangan tunggu M6. Kalau ada yang rusak,
lebih baik ketahuan sekarang.

---

## Yang masih kurang

### 1. Proposal §4.3 Alur Integrasi — belum ditulis

Tenggat menurut jadwal R4 adalah **16 Agustus**.

Kerangka yang disarankan:

1. **Arsitektur end-to-end** — Next.js → FastAPI → ONNX Runtime → respons JSON
2. **Kepatuhan batasan MVP** — sinkron, tanpa database, tanpa background job, satu endpoint inti
3. **Alur pemrosesan** — validasi Pydantic, preprocessing, inferensi dua model, skoring risiko,
   mesin aturan, lapisan penjelasan
4. **Integrasi model hibrida** — mengapa dua model ONNX, dan bagaimana kontrak masukan yang identik
   membuat integrasinya tetap sederhana
5. **Rekayasa** — Docker multi-stage, healthcheck, CI, cakupan pengujian
6. **Latensi** — angka p50/p95 terukur

Contoh format ada pada `docs/proposal_4_2_alur_pengembangan_model.md`.

### 2. `docs/architecture.md` masih kerangka kosong

18 baris, sebagian besar komentar HTML. Bagian "Overview" dan "Data Flow" masih kosong. Dipakai pada
video PoW segmen "Arsitektur" (menit 0:40–1:20). Sertakan diagram alur — cukup ASCII.

### 3. Laporan latensi p50/p95

Artefak wajib di `context-r3` baris 191. Cukup satu tabel p50/p95/p99 untuk kelima skenario demo.

Sebagai acuan, pengukuran R2 di tingkat model: `coldtrack.onnx` 1,1 ms dan `coldtrack_ttb.onnx`
0,09 ms — jadi hampir seluruh waktu respons berasal dari preprocessing dan serialisasi, bukan
inferensi.

### 4. Tabel kepatuhan batasan MVP

Juga artefak wajib. Dipakai di video PoW menit 0:40–1:20.

| Batasan | Status | Bukti |
|---|---|---|
| Pemrosesan sinkron saja | patuh | tidak ada Celery/RQ/cron di `requirements.txt` |
| Tanpa database | patuh | skenario disimpan sebagai berkas JSON statis |
| Tanpa otentikasi | patuh | tidak ada endpoint login/session |
| Satu perintah `docker compose up` | patuh | uji klon segar M6 |
| Parameter statis saat demo | patuh | seluruhnya dari `config.yaml` |

### 5. Uji Docker klon segar (M6)

Kriterianya: klon segar di laptop anggota lain, `docker compose up --build`, buka `localhost:3000`,
dapatkan hasil. **Bila butuh langkah manual apa pun, itu dihitung sebagai bug.**

### 6. Tag rilis

`context-r3` baris 197 menyebut `v0.1.0`, `v0.5.0`, `v1.0.0`. Belum ada tag sama sekali. Minimal
`v1.0.0` perlu dibuat saat code freeze.

---

## Catatan dari R2 soal Time-to-Breach

| TTB sebenarnya | MAE |
|---|---|
| ≤ 10 menit | 3,46 menit |
| ≤ 30 menit | 7,60 menit |
| seluruh rentang | 53,45 menit |

Model andal sebagai alarm jangka pendek, tidak andal sebagai hitung mundur jarak jauh.

**Saran tampilan:** tampilkan angka TTB hanya bila di bawah ~30 menit. Di atas itu cukup status
risiko tanpa angka spesifik. Perlu dikoordinasikan dengan R4.

---

## Urutan prioritas

1. **Sepakati kontrak field dengan R4** — memblokir demo end-to-end
2. **Proposal §4.3** — tenggat 16 Agustus
3. **Uji dengan `USE_MOCK=false`** minggu ini
4. **`docs/architecture.md`** — dibutuhkan video PoW
5. Laporan latensi + tabel kepatuhan MVP
6. Uji Docker klon segar, lalu tag `v1.0.0`
