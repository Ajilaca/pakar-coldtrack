# ColdTrack AI — Context untuk R4 (Frontend & Demo Engineer / PM)

Taruh file ini di root folder kerja kamu (atau paste ke awal sesi Claude Code / assistant coding kamu) supaya AI-nya langsung punya konteks penuh tanpa perlu dijelaskan ulang.

## Tentang proyek ini

- **Kompetisi:** AI Innovation Challenge (AIC) COMPFEST 18
- **Tema:** AI for Backbone Economy — sub-area Smart Logistics
- **Deadline resmi:** 25 Agustus 2026, 23:55 WIB. **Target internal tim: submit 24 Agustus** (buffer 1 hari).
- **Tim:** 4 orang — R1 (AI Data Engineer), R2 (AI Model Engineer), R3 (Backend & MLOps), R4 (kamu, Frontend & Demo, merangkap koordinasi tim)
- **Masalah yang diangkat:** biaya logistik Indonesia 14,29% dari PDB (target 8% di 2045); Food Loss & Waste 23–48 juta ton/tahun akibat cold chain buruk dan pemantauan pasif/manual.
- **Solusi — ColdTrack AI:** mengubah telemetri IoT pasif menjadi keputusan proaktif. Keluaran AI: prediksi suhu, klasifikasi mode kegagalan, dan **Time-to-Breach (TTB)** — menit tersisa sebelum ambang terlampaui. Pergeseran nilai: dari "muatan sudah rusak" menjadi "muatan aman 23 menit lagi, ini tiga hal yang harus dilakukan."

## Batasan MVP — terutama tanggung jawabmu untuk dijaga di sisi tampilan

- **Frontend — ini bagianmu:** **satu alur interaksi inti** (satu input → satu output AI). **Dilarang keras** dashboard analitik kompleks (tanpa filter tanggal, tanpa agregasi lintas armada, tanpa papan KPI), **dilarang keras** sistem otentikasi (tanpa login/session/JWT). Godaan terbesar adalah menambah tab "Armada" berisi daftar semua truk — itu melanggar aturan, tahan diri.
- **Backend:** pemrosesan sinkron saja, tanpa background job/database (tanggung jawab R3).
- **AI:** wajib fine-tuned, parameter statis saat demo (tanggung jawab R1+R2).

## Peran & kepemilikan tim

| Area | Pemilik |
|---|---|
| Simulator & data sintetik | R1 |
| Prapelatihan & fine-tuning model | R2 |
| API & mesin aturan | R3 |
| Docker & CI | R3 |
| Antarmuka & UX | **R4 (kamu)** |
| Skenario demo & narasi | R4 bersama R1 |
| Video PoW & Promosi | **R4 (kamu) — editor utama** |
| Proposal — Latar Belakang, Tujuan, Kesimpulan | **R4 (kamu)** |
| Business Value & Governance AI | R4 bersama R1 |
| Perakitan proposal & QA final | **R4 (kamu)** |
| Koordinasi jadwal & papan risiko | **R4 (kamu)** |

## Misi kamu

Dua misi paralel: (1) membuat momen "wah" dalam sepuluh detik pertama demo — juri menilai apa yang mereka lihat, bukan apa yang berjalan di balik layar; (2) memastikan pekerjaan teknis yang bagus benar-benar memenangkan lomba lewat proposal, video, dan koordinasi tim yang rapi. Peran kedua ini sering diremehkan padahal paling menentukan selisih nilai pada lomba dengan bobot proposal dan video yang besar.

## Anatomi satu halaman (jangan lebih dari ini)

- **Header:** nama produk, satu kalimat positioning, badge "Mode Demo — parameter statis"
- **Zona input:** dropdown 5 skenario pra-set (Sehat / Pintu terbuka / Kompresor melemah / Sensor macet / Kejut suhu ambien saat macet) + tombol unggah CSV
- **Tombol tunggal:** "Analisis Perjalanan" dengan skeleton loader saat menunggu
- **Kartu hasil — ini bintang demonya:**
  - Lampu status besar: AMAN / WASPADA / KRITIS
  - Angka raksasa Time-to-Breach: "Muatan aman 23 menit lagi"
  - Diagnosis mode kegagalan + skor keyakinan
  - Tiga langkah tindakan berurutan dengan estimasi dampak
  - Baris "Mengapa AI berpikir begini": 3 fitur pendorong teratas
  - Grafik suhu: garis aktual (solid) + garis prediksi (putus-putus) + pita ambang

## Tumpukan teknologi

| Komponen | Pilihan | Catatan |
|---|---|---|
| Framework | Next.js 14 (App Router), TypeScript | Output mode `standalone` agar image Docker kecil |
| Styling | Tailwind CSS + shadcn/ui | Komponen siap pakai, hemat waktu desain |
| Grafik | Recharts — satu LineChart | Deret suhu input + garis prediksi + pita ambang |
| Peta | React-Leaflet + tile OpenStreetMap | Opsional — potong dulu kalau waktu mepet |
| State | `useState` lokal | Tanpa Redux/Zustand, **tanpa localStorage** |
| Panggilan API | `fetch()` langsung ke service `api` | Base URL dari `NEXT_PUBLIC_API_URL` |

## Kontrak API yang kamu konsumsi (dari R3)

```
POST /api/v1/analyze

Request minimal:
{ "shipment_id": "...", "cargo_profile": "vaksin_2_8C", "readings": [ {...} ] }

Response yang kamu render ke kartu hasil:
{
  "status": "KRITIS",                    -> lampu status
  "time_to_breach_min": 23.4,            -> angka raksasa TTB
  "failure_mode": { "label": "...", "confidence": 0.91 },  -> diagnosis
  "forecast": { "t15": 6.9, "t30": 8.4, "t60": 11.2 },     -> garis prediksi di grafik
  "drivers": [ { "feature": "...", "value": "...", "contribution": 0.44 } ],  -> baris "mengapa"
  "actions": [ { "priority": 1, "text": "...", "eta_min": 5 } ]  -> tiga langkah tindakan
}
```

Sebelum R3 selesai bangun endpoint asli (target Kamis Sprint 1), kamu integrasi ke **endpoint tiruan (mock)** yang R3 siapkan Selasa Sprint 0 — jadi kamu tidak pernah menunggu tanpa kerjaan.

## Lima skenario demo (dari R1, jadi CSV statis)

1. Sehat — perjalanan normal
2. Pintu terbuka terlalu lama
3. Kompresor melemah (degradasi bertahap — paling dramatis untuk TTB)
4. Sensor macet (stuck-at)
5. Kejut suhu ambien saat macet

Skenario #3 adalah yang paling baik untuk demo utama karena menunjukkan nilai TTB secara jelas: kenaikan suhu yang halus, tidak terlihat manusia, tapi terdeteksi dan diberi estimasi waktu oleh model.

## Timeline tugas kamu per sprint

**Sprint 0 — Minggu 1 (3–9 Agustus): bangun rangka + mulai proposal paralel**

- Sen: **pimpin kick-off 2 jam** (kunci lingkup, sepakati stack, bagi porsi proposal, sepakati jam stand-up); setup Next.js + Tailwind + shadcn
- Sel: wireframe halaman tunggal (menunggu kontrak API dari R3)
- Rab: bangun zona input + 5 skenario pra-set
- Kam: bangun kartu hasil pakai data statis dulu
- Jum: sambungkan frontend ke endpoint tiruan R3 — titik pertama rangka end-to-end hidup; pimpin **integrasi mingguan + demo internal**
- Sab: grafik Recharts + pita ambang
- **Paralel sepanjang minggu:** draf Latar Belakang + Tujuan & Manfaat (tidak butuh hasil teknis, bisa dikerjakan kapan saja)
- Min: **M2** — cek rangka end-to-end hidup; retrospektif + mulai isi papan risiko

**Sprint 1 — Minggu 2 (10–16 Agustus): poles + mulai narasi bisnis**

- Sen: tangani kondisi memuat/galat/kosong
- Sel: poles kartu hasil, tipografi TTB dibesarkan
- Rab: peta Leaflet (opsional, potong jika mepet)
- Kam: uji dengan respons API asli (bukan mock lagi)
- Jum: responsif + uji resolusi 1366×768 (resolusi proyektor umum); pimpin integrasi + demo internal
- Sab: rekam GIF demo untuk README; mulai kumpulkan gambar untuk proposal
- Min: **M5**; retrospektif; rakit bagian proposal yang sudah masuk dari R1/R2/R3

**Sprint 2 — Minggu 3 (17–23 Agustus): kemasan final — fokus utama di sini**

- Sen (Kemerdekaan, kapasitas separuh): ringan saja
- Sel: draf Business Value bersama R1; poles visual akhir
- Rab: ikut uji Docker klon segar (M6, seluruh tim)
- Kam: **M7 — rakit proposal, sisipkan gambar, seragamkan gaya bahasa**; siapkan aset video promosi
- Jum: **M8 — rekam & susun Video PoW**
- Sab: **M9 code freeze**; sunting kedua video
- Min: **M10** — cek semua deliverable final; minta orang di luar tim membaca proposal & nonton video promosi

**Buffer (24–25 Agustus):** Senin 24 — checklist submission lengkap, unggah, kirim, simpan bukti. Selasa 25 — cadangan murni, jangan rencanakan kerja di hari ini.

## Kerangka Video PoW (maks 7 menit)

| Waktu | Segmen | Isi |
|---|---|---|
| 0:00–0:40 | Masalah & solusi | Angka Food Loss & Waste + biaya logistik; satu kalimat solusi |
| 0:40–1:20 | Arsitektur | Diagram alur; tabel kepatuhan batasan MVP |
| 1:20–2:30 | Pabrik data | Simulator berjalan, grafik anomali, alasan sintetik |
| 2:30–4:00 | Model & fine-tuning | Kurva loss pretrain vs fine-tune, confusion matrix, ablation |
| 4:00–5:30 | Demo langsung | `docker compose up` nyata, jalankan skenario kompresor melemah, soroti TTB |
| 5:30–6:20 | Rekayasa & tata kelola | Latensi p95, CI hijau, commit history, fallback, human-in-the-loop |
| 6:20–7:00 | Keterbatasan & rencana | Akui kesenjangan sim-to-real, langkah uji lapangan |

## Kerangka Video Promosi (maks 5 menit)

Tanpa kode, tanpa istilah teknis. Cerita nyata (truk vaksin, kompresor melemah siang hari macet Jakarta) → skala masalah (23–48 juta ton, 14,29% PDB) → solusi bekerja (tunjukkan antarmuka, angka TTB) → nilai bisnis (1 insiden dicegah = 1 tahun langganan) → visi (kontribusi target 8% logistik 2045) → penutup.

## Artefak wajib kamu

`frontend/`, GIF demo, kedua video final, proposal terakit lengkap, papan risiko, daftar periksa submission.

## Repo & konvensi

- Commit: **Conventional Commits** — `feat(ui): tambah kartu hasil dengan indikator status`, scope: `api, model, sim, ui, docker, ci, docs, rules, preprocess`
- Branch: `main` dilindungi, kerja di `feat/<nama-singkat>`, PR minimal 1 approval + CI hijau sebelum merge
- **Definition of Done:** merged via PR dengan CI hijau, commit conventional, terbukti jalan via `docker compose up`, ada screenshot bukti, dokumentasi terkait diupdate, sudah dicoba anggota lain, **dan paragraf proposal terkait sudah ditulis di hari yang sama** (khusus untukmu sebagai perakit — kejar semua orang untuk update potongan mereka)

## Pembagian penulisan proposal (kamu yang menagih tenggatnya)

| Bagian | Penulis | Tenggat draf |
|---|---|---|
| Judul, Latar Belakang, Tujuan & Manfaat | **R4** | 8 Agu |
| §4.1 Alur Dataset | R1 | 14 Agu |
| §4.2 Alur Model | R2 | 16 Agu |
| §4.3 Alur Integrasi | R3 | 16 Agu |
| Business Value | R4 + R1 | 18 Agu |
| Governance AI | R1 + R4 | 18 Agu |
| Kesimpulan | **R4** | 20 Agu |
| Perakitan & penyeragaman gaya | **R4** | 20 Agu |

## Ritual yang kamu pimpin

- Stand-up harian 15 menit (kemarin/hari ini/hambatan)
- Integrasi mingguan Jumat sore (90 menit) + demo internal (20 menit)
- Tinjauan risiko Senin pagi (30 menit) — **termasuk hitung berapa halaman proposal sudah terisi**, ini metrik pencegah proposal baru 6 halaman di tanggal 20

## Siapa yang menunggumu, siapa yang kamu tunggu

- **Kamu memblokir:** tidak ada jalur teknis kritis
- **Kamu diblokir oleh:** R3 (kontrak API & mock, Selasa Sprint 0)
- **Tanggung jawab tambahanmu:** memastikan R1 dan R3 tidak telat di deadline awal mereka (skema fitur & kontrak API), karena keterlambatan mereka merembet ke seluruh tim, dan kamu yang paling cepat menyadarinya lewat stand-up harian.
