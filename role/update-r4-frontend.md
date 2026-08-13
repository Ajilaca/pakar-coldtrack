# Update Tugas R4 — Frontend & Demo Engineer / PM

**Per 7 Agustus 2026** · Deadline internal tim: **24 Agustus** (sisa 17 hari)
Disusun R2 berdasarkan audit repositori terhadap `role/context-r4-frontend.md`.

---

## Ringkasan

Sisi teknis tim pada dasarnya sudah selesai — R1, R2, dan R3 hampir tuntas. **Yang tersisa
sebagian besar adalah tulisan, dan itu ada di jalurmu sebagai perakit proposal.**

Temuan paling penting dari audit: **proposal baru terisi 1 dari 8 bagian**, dan dua bagian sudah
lewat tenggat.

---

## Status proposal — bagian paling mendesak

| Bagian | Penulis | Tenggat | Status |
|---|---|---|---|
| Judul, Latar Belakang, Tujuan & Manfaat | **R4** | 8 Agu | belum ada |
| §4.1 Alur Dataset | R1 | 14 Agu | belum ada |
| §4.2 Alur Model | R2 | 16 Agu | **selesai** |
| §4.3 Alur Integrasi | R3 | 16 Agu | belum ada |
| Business Value | R4 + R1 | 18 Agu | belum ada |
| Governance AI | R1 + R4 | 18 Agu | belum ada |
| Kesimpulan | **R4** | 20 Agu | belum ada |
| Perakitan & penyeragaman gaya | **R4** | 20 Agu | belum mulai |

**Bagianmu sendiri (Latar Belakang & Tujuan) tenggatnya 8 Agustus — besok.** Bagian ini tidak
membutuhkan hasil teknis apa pun dan sebenarnya bisa dikerjakan sejak minggu pertama.

Risiko terbesar bukan kode yang belum jadi, melainkan proposal yang baru mulai ditulis pada
tanggal 20 — persis skenario yang tinjauan risiko Senin dimaksudkan untuk mencegah.

Satu-satunya bagian yang sudah ada bisa dipakai sebagai contoh format:
`docs/proposal_4_2_alur_pengembangan_model.md`.

---

## Status frontend

`frontend/src/app/page.tsx` (153 baris) sudah ada dan memanggil API. Branch `frontend/prototype`
punya 1 commit yang belum di-merge ke `main`.

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

Akurasi TTB sangat bergantung jaraknya:

| TTB sebenarnya | MAE |
|---|---|
| ≤ 10 menit | 3,46 menit |
| ≤ 30 menit | 7,60 menit |
| seluruh rentang | 53,45 menit |

Model andal sebagai alarm jangka pendek, tidak andal sebagai hitung mundur jarak jauh.

**Saran: tampilkan angka TTB hanya bila di bawah ~30 menit.** Di atas itu cukup tampilkan status
risiko tanpa angka spesifik. Menampilkan "muatan aman 247 menit lagi" akan memberi kesan presisi
yang tidak dimiliki model — dan bila juri menguji dengan skenario berbeda, selisihnya bisa terlihat.

Kabar baiknya, ini justru memperkuat demo: skenario #3 (kompresor melemah) yang disarankan sebagai
demo utama menghasilkan TTB pendek, persis rentang di mana model paling akurat.

---

## Yang masih kurang

### 1. `docs/ai_governance.md` masih kerangka kosong

16 baris, isinya hanya komentar HTML. Tanggung jawab bersama R1.

Sebagian besar bahan **sudah tersedia** di `docs/model_card.md` bagian "Limitations & Ethical
Considerations" — tujuh butir keterbatasan, termasuk analisis risiko false negative versus false
positive, dan penegasan bahwa sistem adalah alat bantu, bukan pengambil keputusan. Bisa langsung
dirujuk atau disalin seperlunya.

### 2. GIF demo — belum ada

Disebut sebagai artefak wajib. Dipakai di README dan bahan video.

### 3. Video PoW & Promosi — belum mulai

Materi dari R2 untuk segmen "Model & fine-tuning" (menit 2:30–4:00) sudah siap pakai:

- `ml/reports/loss_curves.png` — perbandingan pretrain vs dari nol
- `ml/reports/confusion_matrix.png`
- `ml/reports/ttb_by_horizon.png`
- `ml/reports/ablation_results.json`, `baseline_metrics.json`

**Satu hal yang perlu diketahui sebelum menulis naskah:** narasi model **berubah** dari rencana
awal. Kalimat yang disiapkan di context — *"kami mengambil representasi dari data IoT publik lalu
menalanya ke domain rantai dingin"* — **tidak lagi akurat**, karena eksperimen membuktikan
prapelatihan justru merugikan dan model produksi akhirnya dilatih dari nol.

Narasi pengganti: *"Kami merencanakan transfer learning, mengujinya secara serius, menemukan bahwa
pendekatan itu tidak berhasil pada domain ini, dan menjelaskan mengapa."* Ini lebih kuat — sebuah
temuan dengan grafik pendukung, bukan klaim yang bisa dibantah dalam satu pertanyaan.

### 4. Papan risiko & daftar periksa submission — belum ada

Keduanya artefak wajib menurut `context-r4` baris 148.

---

## Yang perlu kamu tagih ke tim minggu ini

| Ke | Apa | Kenapa mendesak |
|---|---|---|
| **R3** | Proposal §4.3 + `docs/architecture.md` | tenggat 16 Agu; `architecture.md` masih kerangka kosong |
| **R1** | Proposal §4.1 + grafik sim-to-real | tenggat 14 Agu; grafik dibutuhkan video PoW segmen "Pabrik data" |
| **R1** | `01_eda.ipynb` | artefak wajib yang belum ada |
| **R1 + R4** | `docs/ai_governance.md` | perlu disepakati siapa menulis duluan |

---

## Urutan prioritas

1. **Latar Belakang & Tujuan** — tenggatmu besok, tidak bergantung siapa pun
2. **Tagih §4.1 dan §4.3** — dua bagian terbesar yang belum tersentuh
3. Lengkapi kartu hasil frontend + GIF demo
4. `ai_governance.md` bersama R1
5. Naskah video, papan risiko, daftar periksa submission
