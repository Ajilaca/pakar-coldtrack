# Update Tugas R1 — AI Data Engineer

**Per 7 Agustus 2026** · Deadline internal tim: **24 Agustus** (sisa 17 hari)
Disusun R2 berdasarkan audit repositori terhadap `role/context-r1-ai-data.md`.

---

## Yang sudah selesai

| Artefak | Status |
|---|---|
| `ml/simulator/` — simulator termal, 9 mode anomali A0–A8 | selesai |
| `data/processed/` — dataset v1 sampai v4 | selesai |
| `docs/dataset_card.md` — 255 baris, 7 dataset publik + verifikasi standar | selesai |
| `docs/feature_schema.md` — kontrak 12 kolom | selesai |
| `ml/tests/test_data_contract.py` — 7 tes, semua lolos | selesai |
| Perbaikan 3 bug pelabelan (v2 → v4) | selesai |

Kualitas kerjanya baik. Verifikasi `cargo_profiles` terhadap standar resmi (WHO, BPOM No. 6/2020,
Codex Alimentarius, SNI) melampaui yang diminta, dan pengakuan jujur bahwa `massa_kg` serta
`toleransi_menit` bukan kutipan standar adalah nilai tambah untuk penilaian.

---

## Yang masih kurang

### 1. Notebook `01_eda.ipynb` — belum ada

Disebut sebagai artefak wajib di `context-r1` baris 151. Temuan EDA sudah tertulis rapi di
`dataset_card.md`, tetapi notebooknya sendiri tidak ada di repositori.

Isi minimal: pemuatan tiap dataset publik, statistik ringkas, grafik yang mendasari temuan yang
sudah dituliskan (pola diurnal, sebaran outlier Intel Lab, rasio anomali Smart Manufacturing).

### 2. Grafik validasi sim-to-real — belum ada

Angkanya sudah ada di `dataset_card.md` (KS statistic 1,0000; ACF lag 1/10/30/60), tetapi
**Gambar 4.1** yang disebut di timeline Sprint 1 belum pernah dibuat.

Yang perlu digambar:

- Perbandingan kurva ACF data sintetik vs data IoT publik, lag 1–60
- Perbandingan distribusi suhu dan laju perubahan suhu

Simpan sebagai `ml/reports/sim_to_real_acf.png` dan `ml/reports/sim_to_real_distribusi.png`.
Grafik ini dipakai di proposal §4.1 dan segmen "Pabrik data" pada video PoW (menit 1:20–2:30).

### 3. Proposal §4.1 Alur Dataset — belum ditulis (paling mendesak)

Tenggat menurut jadwal R4 adalah **14 Agustus** — masih ada waktu, tetapi ini bagian dengan bobot
penilaian besar dan tidak bisa dikebut di hari terakhir.

Bahannya **sudah lengkap** di `dataset_card.md` dan `ml/simulator/README.md`; tinggal disusun ulang
menjadi narasi. Kerangka yang disarankan:

1. **Mengapa data sintetik** — tidak ada dataset publik berisi telemetri truk berpendingin Indonesia
   dengan label mode kegagalan, terutama label Time-to-Breach yang bersifat kontrafaktual
2. **Sumber data publik** — 7 dataset, peran masing-masing, lisensinya
3. **Simulator termal** — persamaan pendinginan Newton, kalibrasi, katalog 9 mode anomali
4. **Verifikasi terhadap standar resmi** — koreksi tiga nilai `cargo_profiles`, dan pengakuan jujur
   soal `massa_kg` dan `toleransi_menit`
5. **Validasi sim-to-real** — hasil uji KS dan ACF, termasuk pengakuan bahwa data sintetik lebih
   stabil daripada data nyata beserta penjelasannya
6. **Keterbatasan** — belum divalidasi terhadap perjalanan truk sungguhan

Contoh format dapat dilihat pada `docs/proposal_4_2_alur_pengembangan_model.md`.

### 4. `docs/ai_governance.md` — masih kerangka kosong

16 baris, isinya hanya komentar HTML. Ini tanggung jawab bersama dengan R4
(`context-r1` baris 32). Perlu disepakati siapa yang menulis duluan.

Sebagian bahan sudah tersedia di `docs/model_card.md` bagian "Limitations & Ethical
Considerations" — silakan dirujuk atau disalin seperlunya, khususnya soal risiko false negative
yang lebih berat daripada false positive.

---

## Catatan teknis kecil

**Berkas `.pyc` ikut ter-commit.** `ml/tests/test_data_contract.cpython-312-pytest-9.1.1.pyc` ada di
`main`. Ini berkas hasil kompilasi otomatis yang seharusnya tidak masuk repositori — `.gitignore`
sudah punya aturan `*.py[cod]`, jadi berkas ini kemungkinan ter-commit sebelum aturan itu berlaku.
Hapus dengan `git rm --cached ml/tests/test_data_contract.cpython-312-pytest-9.1.1.pyc`.

**Split test tidak seimbang untuk TTB.** Split `test` hanya memuat 10,6% jendela breach, sementara
`val` memuat 22,6%, dengan median TTB 63 vs 10 menit. Pembagian sudah distratifikasi per
`failure_mode`, tetapi tidak per kejadian breach, sehingga evaluasi Time-to-Breach antar split
kurang sebanding.

Ini **tidak mendesak** — R2 sudah menyesuaikan pelaporannya dan memakai angka test yang lebih
konservatif. Kalau nanti ada waktu longgar dan dataset dibangkitkan ulang, stratifikasi tambahan
berdasarkan ada/tidaknya breach akan membuat evaluasi lebih stabil. Kalau tidak sempat, cukup
dicatat sebagai keterbatasan.

---

## Urutan prioritas

1. **Proposal §4.1** — bobot penilaian terbesar, bahannya sudah siap
2. **Grafik sim-to-real** — dibutuhkan §4.1 dan video PoW
3. **`ai_governance.md`** bersama R4
4. **`01_eda.ipynb`** — melengkapi daftar artefak
5. Hapus berkas `.pyc`
