# Model Card — ColdTrack AI

**Versi aktif:** v3 (11 Oktober 2026, lihat bagian berikut) · **Versi sebelumnya:** v2 (hibrida),
7 Agustus 2026 · **Penanggung jawab:** R2 (AI Model Engineer)

## Pembaruan v3 — GRU hasil latih ulang B3 (11 Oktober 2026)

Model klasifikasi + forecast diganti dengan `ml/reports/coldtrack_b3.onnx` (kontrak:
`ml/reports/labels_b3.json`), setelah lulus gerbang G3 (`bench/results/keputusan/G3.json`).
`coldtrack_ttb.onnx` (XGBoost TTB) **tidak berubah**. Kontrak masukan/keluaran identik dengan
`coldtrack.onnx`; berkas v2 tetap disimpan untuk keterlacakan dan benchmark.

| | v2 `coldtrack.onnx` | v3 `coldtrack_b3.onnx` |
|---|---|---|
| Arsitektur | GRU 2 lapis, hidden 64 + statistik ringkasan | GRU 3 lapis, hidden 128 + statistik ringkasan |
| Pelatihan | bobot loss 30/1/8, class weight sqrt | hasil sweep Optuna 60 trial: bobot loss forecast/TTB lebih rendah, label smoothing, class weight lebih lunak (`labels_b3.json: konfigurasi`) |
| Macro F1 (test) | 0,581 | **0,668** |
| PR-AUC anomali (test) | 0,711 | **0,786** |
| Forecast MAE t+30 (test) | 0,198 °C | **0,192 °C** |
| Latensi CPU batch 1 (p50, G16) | 0,21 ms | 1,38 ms |

Sumber angka: `bench/results/test/{baseline_proposal,kandidat_b3}.json` (split test, dipakai sekali
per model, akses tercatat di `bench/results/test_access_log.json`) dan
`bench/results/g16-cpu/B3/latensi_kandidat.json`. Angka val 5 seed dan seluruh proses seleksi ada di
`bench/report/REPORT.md` bagian B3.

**Yang belum berubah dan tetap diakui:**
- Target Macro F1 > 0,80 dan PR-AUC > 0,85 **belum tercapai**.
- Penyebab utama yang terukur: label `failure_mode` bertahan dari onset sampai akhir trip, padahal
  A1 (pintu) dan A7 (kejut ambien) adalah peristiwa sementara. Sebagian besar jendela A1/A7 jauh
  setelah onset tidak memuat jejak peristiwanya sama sekali (`bench/results/g16-gpu/B3/label_check.json`),
  sehingga tidak dapat dibedakan dari kondisi sehat oleh model berbasis jendela apa pun. Definisi
  metrik dan target tidak diubah; peninjauan definisi label direkomendasikan ke tim data.
- Head `time_to_breach_min` milik GRU v3 lebih buruk dari v2 untuk TTB ≤ 30 menit; TTB produksi
  tetap dari XGBoost.
- **Target PRD belum tercapai, dinyatakan apa adanya:** Macro F1 test 0,668 (target > 0,80) dan
  PR-AUC test 0,786 (target > 0,85). Penyebab terukur: label bertahan sampai akhir trip, sehingga
  **58 % jendela A1 dan 51 % jendela A7 (split val) tidak memuat jejak kejadiannya** (100 % setelah
  120 menit; `bench/results/g16-gpu/B3/label_check.json`).

### v3 di backend (diagnosis provider bawaan sejak 11 Oktober 2026)

Backend memakai v3 sebagai sumber `forecast` + `failure_mode` (`backend/config.yaml:
model.diagnosis_provider: v3`); status AMAN/WASPADA/KRITIS dan TTB yang ditampilkan tetap dari mesin
fisika. **Kembali ke checkpoint-2:** ubah nilai itu menjadi `checkpoint2` lalu restart backend (tanpa
perubahan kode; kedua provider diuji di CI). Rincian: `docs/architecture.md` §2.4.

**Perbandingan dengan checkpoint-2 (model backend sebelumnya)** pada 16.500 jendela val v4 yang sama,
seleksi jendela suite `eval/` (`bench/results/g16-cpu/B7/banding_model_val.json`): v3 lebih baik di
forecast (MAE t+30 0,208 vs 1,398 °C), deteksi pintu/kejut ambien/sensor (AUROC 0,837/0,894/0,975 vs
0,613/0,483/0,341) dan jendela sehat yang dilabel gangguan (3,6 % vs 23,8 %). **Keterbatasan
perbandingan:**
1. Diuji di data v4, yang **asing bagi checkpoint-2** (dilatih di simulator garis checkpoint-2).
2. v3 **dituning di split val yang sama** (sweep B3), sehingga angka v3 di sini sedikit optimistis.
3. Definisi label pintu berbeda: checkpoint-2 dilatih untuk pintu terbuka **>= 20 menit**.
4. Uji sebaliknya di data simulator checkpoint-2 (`ml/dataset_v3.parquet`) **belum dapat dijalankan**:
   berkas itu tidak ada di repo.
5. Split test tidak dipakai lagi untuk perbandingan ini (jatah satu kali v3 sudah dipakai di G3).

**Kebijakan label sensor (keputusan 2026-10-11):** kelas `masalah_sensor` dari v3 tidak dipakai
sebagai label; kerusakan sensor hanya datang dari lapisan aturan (sama dengan checkpoint-2). Alasan:
masukan yang terlalu mulus, misalnya jendela sintetis dari form isian manual dasbor, menyerupai sensor
macet bagi v3 (78 % `masalah_sensor` pada isian bawaan) padahal sensornya sehat. Bila v3 memilih
`masalah_sensor` dan aturan tidak menandai sensor, dipakai aturan checkpoint-2 persis: kelas gangguan
lain hanya dipakai bila peluangnya >= 0,5, selain itu `normal_sehat` dengan keyakinan
1 - maks(peluang kelas gangguan lain); status bukan AMAN tetap diberi label aturan. `probabilities`
hanya dikirim bila label = kelas teratas model, supaya tampilan tidak bertentangan dengan dirinya.

**Keterbatasan pada skenario demo:** skenario 3 (degradasi kompresor, A2) tidak dikenali v3
(`normal_sehat` 0,58, `degradasi_bertahap` 0,12; v2 mengenalinya dengan 0,35). Status KRITIS tetap
benar dan labelnya menjadi `suhu_muatan_mendekati_batas` dari aturan. Jendela demo itu dulu dipilih
karena dikenali benar oleh v2; skenario dibiarkan apa adanya (tidak diganti agar v3 tampak benar).
Kelas `degradasi_bertahap` tetap salah satu kelas terlemah v3.

**Latensi:** v3 lebih lambat dari v2: p50 0,21 → 1,38 ms per panggilan (CPU, batch 1, G16;
`bench/results/g16-cpu/B3/latensi_kandidat.json`), masih jauh di bawah anggaran PRD 300 ms.

**Data tidak lengkap:** v3 (dan model jendela lain) hanya dilatih pada jendela 60 menit tanpa bacaan
hilang. Di val v4, 32 % jendela memuat bacaan hilang; pada jendela itu keluaran v3 lewat jalur backend
berbeda dari jalur latih (selisih probabilitas median 0,021, maks 0,56), sedangkan pada jendela lengkap
keduanya identik. Mitigasi: bila ada jeda > 90 detik di 60 bacaan terakhir, respons memuat
`data_lengkap: false` + `catatan_data` dan keyakinan diagnosis dibatasi 0,5 (pilihan tampilan
konservatif, bukan nilai terkalibrasi). **Metrik di atas hanya berlaku untuk jendela lengkap.**

**Zona waktu fitur `hour_of_day` (perbaikan 11 Oktober 2026):** model dilatih dengan **jam lokal**
(simulator latih dan skenario demo memakai WIB). Sebelumnya `POST /analyze` mengambil jam dari offset
yang dikirim klien. Akibatnya bacaan identik yang dikirim sebagai UTC (`Z`) dan sebagai `+07:00`
memberi forecast berbeda: selisih maksimum 0,15 °C (v3) dan 0,61 °C (checkpoint-2) pada tiga jendela
uji. Status tidak berubah, karena mesin fisika tidak memakai jam (sesuai `G4_robustness/
hour_shift_utc_vs_wib_+7h` di `eval/results/iter2_results.json`), dan label pada jendela uji itu juga
tidak berubah. Sekarang ts ber-zona waktu dikonversi ke `fleet.zona_waktu` (bawaan `Asia/Jakarta`)
sebelum fitur dihitung (`backend/app/inference.ke_zona_armada`), sama dengan worker armada.
- ts tanpa zona waktu dianggap jam lokal armada.
- Keterbatasan: armada di luar WIB (WITA/WIT) butuh `zona_waktu` per truk/depo; belum ada.
- Angka evaluasi di atas tidak terpengaruh, karena dihitung langsung dari jendela latih, bukan lewat
  `/analyze`.

Bagian di bawah ini mendeskripsikan **v2** dan dipertahankan sebagai riwayat.

---

Dokumen ini menjelaskan model yang dipakai ColdTrack AI, cara pengujiannya, dan — sama
pentingnya — **di mana model ini tidak bisa diandalkan**. Seluruh angka di sini berasal dari
split **test**, bagian data yang tidak pernah dipakai untuk mengambil keputusan apa pun selama
pengembangan.

---

## Model Details

Sistem ini memakai **dua model** yang berbagi kontrak masukan identik.

| | `coldtrack.onnx` | `coldtrack_ttb.onnx` |
|---|---|---|
| Jenis | GRU 2 lapis (hidden 64) + statistik ringkasan jendela | XGBoost, 300 pohon |
| Keluaran | prediksi suhu t+15/30/60, probabilitas 7 mode kegagalan | Time-to-Breach (menit) |
| Ukuran | 169 KB | 950 KB |
| Latensi CPU (batch 1) | 1,1 ms | 0,09 ms |
| Parameter / pohon | 41.443 parameter | 300 pohon |

**Masukan (sama untuk keduanya):** tensor `float32` berbentuk `[batch, 60, 12]` — jendela 60 menit
berturut-turut, 12 fitur per menit sesuai `docs/feature_schema.md`. Nilai dikirim **mentah**;
normalisasi dan perhitungan statistik agregat dibungkus di dalam grafik ONNX masing-masing model,
sehingga backend tidak perlu mengulang langkah prapemrosesan apa pun.

### Arsitektur GRU

```
Jendela 60 x 12 ──> [GRU 2 lapis, hidden 64, dropout 0,2] ──> 64 angka ──┐
        │                                                                 ├──> 136 angka
        └────────> [6 statistik x 12 fitur, tanpa parameter] ──> 72 angka ┘        │
                                                                                    ├──> suhu t+15/30/60
                                                                                    └──> 7 kelas mode kegagalan
```

Jalur statistik ringkasan (rata-rata, simpangan baku, min, maks, nilai terakhir, tren) ditambahkan
setelah diagnosis menunjukkan GRU menghabiskan kapasitas untuk mempelajari besaran yang sebenarnya
dapat dihitung langsung. Setelah ditambahkan, Macro F1 naik dari 0,440 ke 0,598 di split validasi
dengan tambahan hanya 792 parameter.

### Pemetaan 9 mode anomali menjadi 7 kelas

Dua pasang mode digabung karena tanda tangan termalnya nyaris tidak dapat dibedakan dari jendela
60 menit:

| Kelas keluaran | Berasal dari | Alasan penggabungan |
|---|---|---|
| `degradasi_bertahap` | A2 (kompresor melemah) + A4 (kebocoran refrigeran) | keduanya menghasilkan drift naik yang lambat |
| `masalah_sensor` | A5 (sensor macet) + A6 (sensor berderau) | keduanya kegagalan sensor, bukan kegagalan kargo |
| `A0`, `A1`, `A3`, `A7`, `A8` | tidak digabung | tanda tangannya khas |

---

## Intended Use

**Untuk apa model ini dibuat.** Memberi peringatan dini pada operator armada rantai dingin bahwa
suhu kargo sedang menuju keluar dari pita aman, sehingga masih ada waktu bertindak — menepi,
memanggil teknisi, atau mengalihkan muatan.

**Yang bukan tujuannya.**

- **Bukan penentu keputusan otomatis.** Keluaran model adalah masukan bagi operator manusia dan
  rule engine, bukan pengganti keduanya.
- **Bukan prediktor umur simpan.** Model memprediksi kapan suhu keluar ambang, **bukan** kapan
  produk membusuk. Keduanya hal berbeda; ColdTrack AI tidak memiliki data pembusukan.
- **Bukan sertifikat kepatuhan.** Tidak menggantikan pencatatan suhu resmi yang disyaratkan CDOB
  atau HACCP.
- **Bukan hitung mundur jarak jauh.** Lihat bagian keterbatasan Time-to-Breach di bawah.

---

## Training Data

Sumber utama: `data/processed/v4_seed1000_700trips.parquet` — 700 perjalanan sintetik, 251.073
baris, resolusi 1 menit, dibangun R1 dengan simulator termal berbasis hukum pendinginan Newton.
Rincian sumber, kalibrasi, dan validasi sim-to-real ada di `docs/dataset_card.md`.

Data dipecah menjadi jendela geser 60 menit, dibagi **per `trip_id`** (bukan per baris) agar tidak
ada perjalanan yang sama muncul di dua split:

| Split | Jendela | Peran |
|---|---|---|
| train | 77.703 | melatih bobot |
| val | 16.414 | memilih arsitektur dan hiperparameter |
| test | 16.244 | **hanya untuk pelaporan akhir** |

### Model dilatih dari nol, bukan dari backbone pretrained

Rencana awal memakai transfer learning dua tahap: prapelatihan pada data suhu IoT publik, lalu
fine-tuning pada domain rantai dingin. Rencana itu **diuji dan ditinggalkan** karena tidak terbukti
memberi manfaat — lihat Ablation B di bawah.

Skrip prapelatihan (`ml/pretrain.py`) dan korpusnya tetap dipertahankan di repositori sebagai bukti
eksperimen, tetapi tidak berada di jalur produksi.

---

## Evaluation

Seluruh angka berikut dari split **test**.

### Terhadap target resmi

| Head | Metrik | Hasil | Target | Status |
|---|---|---|---|---|
| Forecast suhu | MAE @ t+30 | **0,198 °C** | < 0,8 °C | tercapai |
| Mode kegagalan | Macro F1 | 0,581 | > 0,80 | belum |
| Time-to-Breach | MAE (TTB ≤ 30 menit) | **7,08 menit** | < 8 menit | tercapai |
| Deteksi anomali | PR-AUC | 0,711 | > 0,85 | belum |

**Dua dari empat target tercapai.** MAE forecast pada horizon lain: 0,152 °C (t+15) dan
0,237 °C (t+60).

### Perbandingan dengan baseline

Untuk menjawab pertanyaan "mengapa perlu deep learning", tiga baseline diuji pada data yang sama:

| Metrik | GRU fusion | XGBoost | Regresi linear | Isolation Forest |
|---|---|---|---|---|
| Forecast t+30 (°C) | 0,198 | **0,189** | 0,338 | — |
| Macro F1 | 0,581 | **0,664** | — | — |
| Akurasi | 0,813 | **0,871** | — | — |
| PR-AUC anomali | 0,711 | **0,753** | — | 0,371 |
| TTB ≤ 30 menit (menit) | 10,8 | **7,1** | — | — |

**XGBoost mengungguli GRU pada seluruh metrik.** Temuan ini dilaporkan apa adanya, dan menjadi
dasar keputusan memakai XGBoost untuk Time-to-Breach.

GRU tetap dipakai untuk forecast dan klasifikasi dengan pertimbangan: selisih pada forecast tipis
(0,198 vs 0,189, keduanya jauh melampaui target), pada klasifikasi kedua model sama-sama belum
mencapai target sehingga penggantian tidak mengubah status papan skor, dan satu model GRU melayani
dua keluaran sekaligus dengan ukuran 169 KB.

### Akurasi per kelas kegagalan

| Kelas | Recall | Jumlah sampel |
|---|---|---|
| A3 — kegagalan reefer total | **100,0 %** | 379 |
| A0 — sehat | 92,1 % | 12.546 |
| `masalah_sensor` (A5+A6) | 66,9 % | 872 |
| A1 — pintu terbuka lama | 58,9 % | 321 |
| A7 — kejut suhu ambien | 44,1 % | 642 |
| A8 — prapendinginan buruk | 20,1 % | 651 |
| `degradasi_bertahap` (A2+A4) | **10,6 %** | 833 |

Pola ini masuk akal secara fisika: A3 (reefer mati total) menghasilkan kenaikan monoton yang khas
dan selalu terdeteksi, sementara `degradasi_bertahap` justru mode yang paling sulit — perubahannya
lambat dan dalam jendela 60 menit nyaris tidak terbedakan dari kondisi sehat. Ironisnya, itulah
mode yang paling berbahaya di dunia nyata karena juga luput dari pengamatan manusia.

### Ablation study

**A. Multi-task vs single-task.** Arsitektur "satu backbone, tiga kepala" menahan performa:

| Tugas | Multi-task | Single-task |
|---|---|---|
| Forecast t+30 | 0,244 | **0,203** |
| Macro F1 | 0,440 | **0,613** |
| Time-to-Breach | **22,94** | 23,62 |

Kerugian ini kemudian **hampir sepenuhnya hilang** setelah jalur statistik ringkasan ditambahkan
(Macro F1 multi-task naik ke 0,598, mendekati 0,613 milik single-task).

**B. Fine-tuning vs dilatih dari nol.** Pretraining tidak memberi manfaat — bahkan merugikan:

| | Fine-tuned | Dari nol |
|---|---|---|
| Loss latih akhir | **2,99** | 3,58 |
| Loss validasi akhir | 4,18 | **2,78** |

Varian pretrained mencapai loss latih lebih rendah tetapi loss validasi lebih tinggi — pola
overfitting yang khas. Grafiknya ada di `ml/reports/loss_curves.png`.

**Penyebabnya dapat dijelaskan.** Korpus prapelatihan (Intel Berkeley Lab, 1,3 juta jendela) hanya
mampu mengisi **4 dari 12 fitur** — data sensor ruangan tidak memiliki informasi pintu, reefer,
kecepatan, maupun radiasi matahari. Delapan fitur sisanya bernilai nol, sehingga bobot GRU
terspesialisasi pada distribusi masukan yang timpang, dan spesialisasi itu justru harus dilupakan
saat fine-tuning.

Upaya perbaikan sudah dilakukan sebelum menyimpulkan: korpus prapelatihan diganti dari 6.113
jendela (IoT India, 3 fitur terisi) menjadi 1,3 juta jendela (Intel Lab, 4 fitur terisi) — 207 kali
lebih besar. Hasilnya tetap sama.

---

## Limitations & Ethical Considerations

### 1. Time-to-Breach hanya andal untuk peringatan jangka pendek

| TTB sebenarnya | MAE |
|---|---|
| ≤ 10 menit | **3,30 menit** |
| ≤ 30 menit | **7,08 menit** |
| keseluruhan | 52,00 menit |

Model **andal sebagai alarm "sebentar lagi jebol", tidak andal sebagai hitung mundur jarak jauh.**
Ini keterbatasan fisik, bukan kekurangan implementasi: memperkirakan kejadian lima jam ke depan
dari jendela 60 menit berada di luar jangkauan informasi yang tersedia.

**Implikasi produk:** tampilkan angka TTB hanya bila nilainya di bawah ~30 menit. Di atas itu,
tampilkan status risiko tanpa angka spesifik agar tidak memberi kesan presisi yang tidak dimiliki
model.

### 2. Keluaran TTB tidak terdefinisi untuk kondisi sehat

Model TTB dilatih hanya pada jendela yang benar-benar menuju breach; jendela sehat di-mask dari
loss. Akibatnya, model **tetap mengeluarkan angka** saat kondisi sehat, dan angka itu tidak
bermakna — pengujian pada 2.000 jendela sehat menghasilkan median **17 menit**, dan **tidak satu
pun** bernilai besar yang dapat dipakai backend sebagai penanda "aman".

**Angka TTB wajib disembunyikan bila `failure_prob` menunjuk ke kelas `A0`.** Ini bukan saran,
melainkan syarat kebenaran keluaran.

### 3. Mode degradasi bertahap hampir tidak terdeteksi

Recall 10,6 %. Sistem **tidak boleh dipromosikan sebagai pendeteksi kompresor melemah atau kebocoran
refrigeran.** Kegagalan jenis ini akan lolos pada sebagian besar kasus.

### 4. Dilatih sepenuhnya pada data sintetik

Tidak ada telemetri truk berpendingin nyata dalam data latih, karena dataset publik semacam itu
tidak tersedia. Simulator dikalibrasi terhadap dataset IoT publik dan standar suhu resmi
(WHO, BPOM No. 6/2020, Codex Alimentarius, SNI), dan divalidasi lewat uji KS serta ACF — tetapi
**belum pernah divalidasi terhadap perjalanan truk sungguhan.** Performa di lapangan berpotensi
berbeda, dan uji lapangan wajib dilakukan sebelum penggunaan operasional.

### 5. Split test tidak seimbang untuk TTB

Split test hanya memuat 10,6 % jendela breach, sementara val memuat 22,6 %, dengan median TTB 63
vs 10 menit. Pembagian data distratifikasi per `failure_mode` tetapi tidak per kejadian breach,
sehingga estimasi TTB antar split kurang sebanding. Angka test tetap dipakai karena lebih
konservatif.

### 6. Risiko false negative lebih berat daripada false positive

Alarm palsu merugikan waktu operator; kegagalan terdeteksi berarti muatan rusak — pada kasus
vaksin, berpotensi membahayakan penerima. Ambang keputusan pada rule engine sebaiknya condong ke
sisi waspada, dan sistem tidak boleh dijadikan satu-satunya lapis pengaman.

### 7. Model bersifat statis

Bobot dibekukan saat ekspor. Model tidak belajar dari data baru saat berjalan, sesuai ketentuan
lomba mengenai parameter statis. Setiap pembaruan menuntut pelatihan ulang dan verifikasi ulang.

---

## Reproduksi

```bash
python -m ml.preprocess.build_windows        # jendela dari dataset v4
python -m ml.finetune                        # latih GRU (~35 menit CPU)
python -m ml.export_onnx                     # ekspor coldtrack.onnx + labels.json
python -m ml.export_ttb_xgboost              # ekspor coldtrack_ttb.onnx (~1 menit)
python -m ml.make_reports                    # metrics.json + grafik
python -m ml.baselines                       # baseline pembanding
python -m ml.ablation                        # ablation A & B (~2,5 jam)
```

Seluruh skrip memakai `seed = 42`. Bobot model (`*.pt`) tidak disertakan di repositori; jalankan
`ml.finetune` untuk membangunnya kembali.

**Berkas terkait:** `ml/reports/metrics.json` · `baseline_metrics.json` · `ablation_results.json` ·
`loss_curves.png` · `confusion_matrix.png` · `ttb_by_horizon.png` · `docs/dataset_card.md` ·
`docs/feature_schema.md`
