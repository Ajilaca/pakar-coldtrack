# Update Tugas R4 — Frontend & Demo Engineer / PM

**Per 13 Agustus 2026** · Deadline internal tim: **24 Agustus** — sisa **11 hari**
Disusun R2 berdasarkan audit repositori terhadap `role/context-r4-frontend.md`.

---

## Ringkasan

Sisi teknis tim pada dasarnya sudah selesai — R1, R2, dan R3 hampir tuntas. **Yang tersisa sebagian
besar adalah tulisan, dan itu ada di jalurmu sebagai perakit proposal.**

Dua temuan yang perlu ditangani segera:

1. **Proposal baru terisi 1 dari 8 bagian**, dan dua bagian sudah lewat tenggat
2. **Frontend dan backend belum pernah benar-benar saling bicara** — nama field tidak cocok

Kabar baiknya, penghambat kedua dari sisi data sudah beres: skenario demo telah diganti dan
diverifikasi bekerja (rincian di bawah).

---

## Temuan uji integrasi — perlu ditangani minggu ini

R2 menelusuri jalur permintaan dari frontend sampai model. Frontend masih memakai data tiruan
(`NEXT_PUBLIC_USE_MOCK` bernilai `true` secara default), sehingga ketidakcocokan berikut belum
pernah muncul.

### Masalah 1 — nama field tidak cocok

Frontend mengirim (`src/lib/types.ts`):

```ts
readings: { timestamp?, temperature_c, ambient_temp_c?, door_open? }[]
```

Backend mewajibkan (`backend/app/schemas.py`):

```
{ ts, temp_c, humidity, ambient_c, door_open, reefer_on, lat, lon, speed_kmh, harsh_events }
```

Hampir seluruh nama berbeda, dan **enam field wajib tidak dikirim sama sekali**. Begitu
`USE_MOCK=false`, setiap permintaan ditolak dengan galat 422 dan demo berhenti total.

**Perlu keputusan bersama R3:** frontend menyesuaikan ke skema backend, atau backend melonggarkan
field yang tidak dipakai? Sebagai bahan pertimbangan, `lat` dan `lon` **tidak dipakai model sama
sekali** dan bisa dijadikan opsional.

### Masalah 2 — skenario demo lebih pendek dari syarat minimum (SUDAH DIBERESKAN R2)

Backend menolak permintaan berisi kurang dari 60 bacaan (model menghitung statistik ringkasan di
dalam dirinya; jendela yang di-*pad* menghasilkan nilai salah). Skenario lama hanya berisi 3–5
bacaan di sisi backend dan 31 di sisi frontend.

**Sudah diselesaikan.** Kelima berkas di `backend/data/scenarios/` telah diganti dengan versi
berisi 125–150 bacaan, diambil dari perjalanan asli di dataset v4 lewat
`ml/preprocess/export_demo_scenarios.py`.

Setiap skenario **sudah diverifikasi menghasilkan diagnosis yang benar** — dari sebelumnya 0 dari 5,
kini 5 dari 5:

| Skenario | Diagnosis model | Keyakinan | Time-to-Breach |
|---|---|---|---|
| Perjalanan normal | A0 (sehat) | 88 % | disembunyikan, sesuai aturan |
| Pintu terbuka lama | A1 | **100 %** | 22 menit |
| Kompresor melemah | degradasi_bertahap | 35 % | 11 menit |
| Sensor macet | masalah_sensor | 52 % | 24 menit |
| Kejut suhu ambien | A7 | **100 %** | 22 menit |

Seluruh nilai TTB jatuh di rentang 11–24 menit — area di mana model paling akurat (MAE 7,08 menit),
sekaligus cukup memberi ruang untuk tiga langkah tindakan yang direkomendasikan.

**Artinya kamu tidak perlu mengurangi jumlah skenario.** Saran sebelumnya untuk memangkas menjadi
tiga sudah tidak berlaku — kelimanya bekerja, dan **skenario "kompresor melemah" tetap bisa menjadi
demo utama** sesuai rencana awal di `context-r4` baris 93.

### Yang perlu kamu lakukan

1. **Sesuaikan nama field di `src/lib/types.ts`** agar cocok dengan skema backend (`temp_c` bukan
   `temperature_c`, `ambient_c` bukan `ambient_temp_c`, dan enam field yang belum dikirim).
2. **Ambil data skenario dari backend** lewat `GET /api/v1/scenarios`, jangan dari
   `src/lib/scenario-data.ts` yang hanya berisi 31 bacaan hasil pembangkitan lokal.
3. **Jalankan dengan `NEXT_PUBLIC_USE_MOCK=false` minggu ini**, jangan tunggu M6. Ini satu-satunya
   cara memastikan demo benar-benar bekerja sebelum hari H.

---

## Status proposal — bagian paling mendesak

| Bagian | Penulis | Tenggat | Status |
|---|---|---|---|
| Judul, Latar Belakang, Tujuan & Manfaat | **R4** | 8 Agu | **lewat tenggat** |
| §4.1 Alur Dataset | R1 | 14 Agu | besok |
| §4.2 Alur Model | R2 | 16 Agu | **selesai** |
| §4.3 Alur Integrasi | R3 | 16 Agu | belum ada |
| Business Value | R4 + R1 | 18 Agu | belum ada |
| Governance AI | R1 + R4 | 18 Agu | belum ada |
| Kesimpulan | **R4** | 20 Agu | belum ada |
| Perakitan & penyeragaman gaya | **R4** | 20 Agu | belum mulai |

**Bagianmu sendiri (Latar Belakang & Tujuan) sudah lewat tenggat 5 hari.** Bagian ini tidak
membutuhkan hasil teknis apa pun dan bisa dikerjakan kapan saja.

Risiko terbesar bukan kode yang belum jadi, melainkan proposal yang baru mulai ditulis pada tanggal
20 — persis skenario yang tinjauan risiko Senin dimaksudkan untuk mencegah.

Satu-satunya bagian yang sudah ada bisa dipakai sebagai contoh format:
`docs/proposal_4_2_alur_pengembangan_model.md`.

---

## Status frontend

Branch `frontend/prototype` sudah punya struktur yang cukup lengkap — komponen kartu hasil, impor
CSV, daftar pendorong, peta tiruan, dan klien API. **Satu commit belum di-merge ke `main`**, dan
`main` saat ini masih berisi halaman placeholder awal.

Yang perlu dicek terhadap "Anatomi satu halaman" di `context-r4` baris 40–51:

- [ ] Header + badge "Mode Demo — parameter statis"
- [ ] Dropdown 5 skenario pra-set + tombol unggah CSV
- [ ] Tombol tunggal "Analisis Perjalanan" + skeleton loader
- [ ] Lampu status besar AMAN / WASPADA / KRITIS
- [ ] Angka raksasa Time-to-Breach
- [ ] Diagnosis mode kegagalan + skor keyakinan
- [ ] Tiga langkah tindakan
- [ ] Baris "Mengapa AI berpikir begini" — 3 fitur pendorong
- [ ] Grafik Recharts: garis aktual + prediksi + pita ambang

### Permintaan penting dari R2 soal tampilan Time-to-Breach

| TTB sebenarnya | MAE |
|---|---|
| ≤ 10 menit | 3,30 menit |
| ≤ 30 menit | 7,08 menit |
| seluruh rentang | 52,00 menit |

Model andal sebagai alarm jangka pendek, tidak andal sebagai hitung mundur jarak jauh.

**Saran: tampilkan angka TTB hanya bila di bawah ~30 menit.** Di atas itu cukup status risiko tanpa
angka spesifik. Menampilkan "muatan aman 247 menit lagi" memberi kesan presisi yang tidak dimiliki
model — dan bila juri menguji dengan skenario berbeda, selisihnya bisa terlihat.

Kabar baiknya ini justru memperkuat demo: skenario #3 (kompresor melemah) yang disarankan sebagai
demo utama menghasilkan TTB pendek, persis rentang di mana model paling akurat.

---

## Yang masih kurang

### 1. `docs/ai_governance.md` masih kerangka kosong

16 baris, isinya hanya komentar HTML. Tanggung jawab bersama R1.

Sebagian besar bahan **sudah tersedia** di `docs/model_card.md` bagian "Limitations & Ethical
Considerations" — tujuh butir keterbatasan, termasuk analisis risiko false negative versus false
positive, dan penegasan bahwa sistem adalah alat bantu, bukan pengambil keputusan.

### 2. GIF demo — belum ada

Artefak wajib. Dipakai di README dan bahan video.

### 3. Video PoW & Promosi — belum mulai

Materi dari R2 untuk segmen "Model & fine-tuning" (menit 2:30–4:00) sudah siap pakai:
`loss_curves.png`, `confusion_matrix.png`, `ttb_by_horizon.png`, `ablation_results.json`,
`baseline_metrics.json`.

**Satu hal penting sebelum menulis naskah:** narasi model **berubah** dari rencana awal. Kalimat
yang disiapkan di context — *"kami mengambil representasi dari data IoT publik lalu menalanya ke
domain rantai dingin"* — **tidak lagi akurat**, karena eksperimen membuktikan prapelatihan justru
merugikan dan model produksi akhirnya dilatih dari nol.

Narasi pengganti: *"Kami merencanakan transfer learning, mengujinya secara serius, menemukan bahwa
pendekatan itu tidak berhasil pada domain ini, dan menjelaskan mengapa."* Ini lebih kuat — sebuah
temuan dengan grafik pendukung, bukan klaim yang bisa dibantah dalam satu pertanyaan.

### 4. Papan risiko & daftar periksa submission — belum ada

Keduanya artefak wajib menurut `context-r4` baris 148.

---

## Yang perlu kamu tagih ke tim minggu ini

| Ke | Apa | Kenapa mendesak |
|---|---|---|
| **R1** | Proposal §4.1 + grafik sim-to-real | tenggat 14 Agu; grafik dibutuhkan video PoW |
| **R3** | Sepakati kontrak field dengan kamu | frontend dan backend belum pernah saling bicara |
| **R3** | Proposal §4.3 + `docs/architecture.md` | tenggat 16 Agu |
| **R1 + kamu** | `docs/ai_governance.md` | perlu disepakati siapa menulis duluan |

---

## Urutan prioritas

1. **Latar Belakang & Tujuan** — sudah lewat tenggat, tidak bergantung siapa pun
2. **Sesuaikan nama field, lalu uji `USE_MOCK=false`** — satu-satunya penghambat demo yang tersisa
3. **Tagih §4.1 dan §4.3** — dua bagian terbesar yang belum tersentuh
4. Merge `frontend/prototype` ke `main` + lengkapi kartu hasil
5. `ai_governance.md` bersama R1
6. GIF demo, naskah video, papan risiko, daftar periksa submission
