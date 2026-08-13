# Update Tugas R3 — Backend & MLOps Engineer

**Per 7 Agustus 2026** · Deadline internal tim: **24 Agustus** (sisa 17 hari)
Disusun R2 berdasarkan audit repositori terhadap `role/context-r3-backend.md`.

---

## Yang sudah selesai

| Artefak | Status |
|---|---|
| `backend/app/` — `main`, `schemas`, `preprocess`, `inference`, `rules`, `explain`, `scenarios` | selesai |
| Endpoint `POST /api/v1/analyze`, `GET /health`, `GET /api/v1/scenarios` | selesai |
| 5 skenario demo di `backend/data/scenarios/` | selesai |
| `docker-compose.yml` + healthcheck | selesai |
| `.github/workflows/ci.yml` + `commitlint.yml` | selesai |
| 22 tes pytest (`test_analyze` 8, `test_rules` 5, `test_preprocess` 3, `test_scenarios` 3, `test_inference` 2, `test_health` 1) | melampaui syarat minimal 8 |

Integrasi model diverifikasi R2 dan hasilnya baik: 12 kolom fitur urut persis sesuai kontrak, rumus
turunan benar, nilai dikirim mentah tanpa normalisasi ganda, dan daftar kelas dibaca dari
`labels.json` alih-alih ditulis tetap di kode.

Tiga bug yang dilaporkan R2 juga **sudah diperbaiki** di branch `feat/r3-sprint-0`, ditambah
penolakan payload di bawah 60 bacaan yang menjawab kekhawatiran soal padding.

---

Branch `feat/r3-sprint-0` sudah di-merge ke `main` lewat PR #8, termasuk keempat commit perbaikan
bug. Sudah diverifikasi R2 — tidak ada yang tertunda.

---

## Yang paling mendesak

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

18 baris, sebagian besar komentar HTML. Bagian "Overview" dan "Data Flow" masih kosong. Dokumen ini
dirujuk di struktur repositori dan dipakai pada video PoW segmen "Arsitektur" (menit 0:40–1:20).

Sertakan diagram alur — cukup ASCII atau gambar sederhana.

---

## Yang masih kurang

### 3. Laporan latensi p50/p95

Disebut sebagai artefak wajib di `context-r3` baris 191. Ada 5 rujukan latensi di berkas tes, tetapi
belum ada laporan terpisah.

Cukup satu tabel: p50, p95, p99 untuk kelima skenario demo, diukur setelah kedua model ONNX
terpasang. Sebagai acuan, pengukuran R2 di tingkat model: `coldtrack.onnx` 1,1 ms dan
`coldtrack_ttb.onnx` 0,09 ms — jadi sebagian besar waktu respons berasal dari preprocessing dan
serialisasi, bukan inferensi.

### 4. Tabel kepatuhan batasan MVP

Juga artefak wajib. Formatnya sederhana:

| Batasan | Status | Bukti |
|---|---|---|
| Pemrosesan sinkron saja | patuh | tidak ada Celery/RQ/cron di `requirements.txt` |
| Tanpa database | patuh | skenario disimpan sebagai berkas JSON statis |
| Tanpa otentikasi | patuh | tidak ada endpoint login/session |
| Satu perintah `docker compose up` | patuh | uji klon segar M6 |
| Parameter statis saat demo | patuh | seluruhnya dari `config.yaml` |

Tabel ini juga dipakai di video PoW menit 0:40–1:20.

### 5. Uji Docker klon segar (M6)

Dijadwalkan Rabu Sprint 2, seluruh tim ikut. Kriterianya: klon segar di laptop anggota lain,
`docker compose up --build`, buka `localhost:3000`, dapatkan hasil. **Bila butuh langkah manual apa
pun, itu dihitung sebagai bug.**

### 6. Tag rilis

`context-r3` baris 197 menyebut `v0.1.0` (M2), `v0.5.0` (M5), `v1.0.0` (M9 code freeze). Belum ada
tag sama sekali di repositori. Minimal `v1.0.0` perlu dibuat saat code freeze.

---

## Catatan dari R2 soal Time-to-Breach

Akurasi TTB sangat bergantung jaraknya:

| TTB sebenarnya | MAE |
|---|---|
| ≤ 10 menit | 3,46 menit |
| ≤ 30 menit | 7,60 menit |
| seluruh rentang | 53,45 menit |

Model andal sebagai alarm jangka pendek, tidak andal sebagai hitung mundur jarak jauh.

**Saran tampilan:** tampilkan angka TTB hanya bila bernilai di bawah ~30 menit. Di atas itu cukup
tampilkan status risiko tanpa angka spesifik, agar tidak memberi kesan presisi yang tidak dimiliki
model. Perlu dikoordinasikan dengan R4 karena menyangkut tampilan.

---

## Urutan prioritas

1. **Proposal §4.3** — tenggat 16 Agustus
2. **`docs/architecture.md`** — dibutuhkan video PoW
3. Laporan latensi + tabel kepatuhan MVP
4. Uji Docker klon segar bersama tim
5. Tag rilis `v1.0.0` saat code freeze
