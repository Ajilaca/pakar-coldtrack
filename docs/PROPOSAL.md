# ColdTrack AI

**Peringatan Dini Kegagalan Rantai Dingin Berbasis Telemetri**

AI Innovation Challenge — COMPFEST 18
Tema: AI for Backbone Economy · Sub-area: Smart Logistics

---

## 1. Nama Kelompok dan Judul Inovasi

| | |
|---|---|
| **Nama kelompok** | `[ISI: nama tim]` |
| **Judul inovasi** | ColdTrack AI — Peringatan Dini Kegagalan Rantai Dingin Berbasis Telemetri |
| **Anggota** | `[ISI: nama lengkap 4 anggota beserta peran]` |

> *Halaman ini merupakan bagian sampul dan tidak dihitung dalam batas 20 halaman.*

---

## 2. Latar Belakang

Biaya logistik Indonesia setara **14,29% dari Produk Domestik Bruto** `[sumber: ...]`. Pemerintah
menargetkan angka itu turun ke **8% pada 2045** `[sumber: ...]`. Selisih enam poin persen tersebut
bukan sekadar statistik — ia mewakili biaya yang pada akhirnya ditanggung konsumen melalui harga
barang.

Sebagian dari biaya itu hilang sebagai barang yang rusak sebelum sampai. Indonesia kehilangan
**23–48 juta ton pangan per tahun** melalui *food loss and waste* `[sumber: ...]`, dan rantai dingin
yang buruk adalah salah satu penyumbangnya. Kerugiannya tidak berhenti pada pangan: vaksin yang
keluar dari rentang 2–8 °C kehilangan potensi dan tidak lagi memberi perlindungan kepada pasien
yang menerimanya.

**Akar masalahnya bukan ketiadaan sensor, melainkan sifat pemantauannya yang pasif.** Banyak
kendaraan berpendingin sudah memasang sensor suhu. Namun data itu umumnya hanya dicatat, lalu
dibaca ketika muatan sudah sampai — atau ketika alarm berbunyi karena ambang sudah terlampaui. Pada
titik itu, keputusan yang tersisa tinggal satu: menerima kerugian.

Yang hilang adalah **waktu untuk bertindak**. Kompresor yang melemah secara bertahap tidak memicu
alarm apa pun sampai suhu benar-benar melewati batas, padahal kenaikannya sudah terbaca sejak
puluhan menit sebelumnya — terlalu halus untuk disadari manusia yang membaca angka, tetapi cukup
jelas bagi model yang mempelajari polanya.

Pergeseran yang kami tawarkan sederhana namun menentukan:

| Pemantauan pasif hari ini | ColdTrack AI |
|---|---|
| "Suhu muatan 9 °C" | "Muatan aman 23 menit lagi" |
| "Ambang terlampaui" | "Kompresor melemah, keyakinan 87%" |
| — | "Tiga hal yang harus dilakukan sekarang" |

---

## 3. Tujuan dan Manfaat Pengembangan

### 3.1 Tujuan

1. **Mengubah telemetri pasif menjadi keputusan yang dapat ditindaklanjuti**, dengan keluaran utama
   berupa *Time-to-Breach* — jumlah menit tersisa sebelum muatan melewati ambang suhunya.
2. **Mengenali jenis kerusakan, bukan sekadar mendeteksi anomali**, sehingga tindakan yang
   disarankan sesuai penyebabnya: pintu yang terbuka ditangani berbeda dari kompresor yang melemah.
3. **Menjelaskan dasar setiap kesimpulan**, agar operator dapat menilai sendiri apakah peringatan
   itu masuk akal, bukan sekadar mempercayainya.
4. **Berjalan pada perangkat keras biasa** — model dirancang ringan (puluhan ribu parameter, bukan
   jutaan) sehingga inferensi berjalan cepat tanpa GPU.

### 3.2 Manfaat

**Bagi operator armada.** Satu insiden yang dicegah menyelamatkan nilai satu muatan penuh.
Peringatan yang datang puluhan menit lebih awal mengubah pilihan yang tersedia: dari sekadar
mencatat kerugian menjadi menepi ke tempat teduh, memeriksa kondensor, atau menyiapkan pemindahan
muatan.

**Bagi penerima dan konsumen akhir.** Vaksin yang sampai dalam kondisi berkhasiat, dan pangan yang
sampai dalam kondisi layak. Untuk produk farmasi, ini menyangkut keselamatan pasien, bukan sekadar
nilai barang.

**Bagi ekosistem logistik nasional.** Susut yang lebih rendah berarti biaya logistik yang lebih
rendah — kontribusi langsung, meski kecil, terhadap target 8% pada 2045.

### 3.3 Nilai bisnis

Kerugian rantai dingin bersifat **biner dan total**. Muatan yang melewati ambang suhu tidak menjadi
"agak rusak" — untuk vaksin, seluruh batch kehilangan jaminan potensi; untuk pangan, seluruh muatan
turun kelas atau dimusnahkan. Tidak ada nilai sisa yang sebanding. Inilah yang membuat peringatan
dini bernilai tinggi meski hanya datang beberapa puluh menit lebih awal.

| Komponen | Nilai | Sumber |
|---|---|---|
| Nilai rata-rata satu muatan berpendingin | `[ISI: Rp ...]` | `[sumber: ...]` |
| Frekuensi insiden eksursi suhu per armada per tahun | `[ISI: ...]` | `[sumber: ...]` |
| Proporsi insiden yang dapat dicegah bila peringatan datang ≥ 20 menit lebih awal | `[ISI: ...%]` | `[asumsi + dasar]` |
| Biaya langganan per kendaraan per tahun | `[ISI: Rp ...]` | penetapan sendiri |

> **Catatan pengisian:** angka pada tabel ini belum diisi dan **tidak boleh dikarang**. Bila sebuah
> angka tidak dapat ditemukan pada sumber yang dapat ditelusuri, nyatakan secara eksplisit sebagai
> asumsi beserta alasannya.

**Segmen sasaran utama:** `[ISI: pilih satu — distributor farmasi / logistik pangan segar /
penyedia jasa logistik pihak ketiga]`. Menyasar ketiganya sekaligus akan melemahkan argumen.

---

## 4. Metodologi

### 4.1 Alur dalam memperoleh dataset

#### 4.1.1 Masalah mendasar

**Tidak ada dataset publik yang menyediakan label kebenaran untuk kegagalan rantai dingin.** Ada
banyak data suhu IoT, tetapi tidak satu pun mencantumkan "pada menit ke berapa muatan ini akan
melewati ambang", apalagi "jenis kerusakan apa yang sedang terjadi". Padahal justru dua label
itulah inti produk kami.

Karena itu kami menempuh jalur dua lapis: **data publik nyata** untuk mempelajari bentuk dinamika
suhu, mengkalibrasi struktur label, menyediakan suhu ambien Indonesia, dan menjadi pembanding
eksternal; serta **simulator fisika yang kami bangun sendiri** untuk menghasilkan data pelatihan
utama, karena hanya dengan simulator kami dapat mengetahui — bukan menebak — kapan sebuah muatan
melewati ambang dan mengapa.

#### 4.1.2 Sumber data dan perannya

| # | Dataset | Peran |
|---|---|---|
| 1 | Temperature Readings: IoT Devices (Kaggle) | Korpus percobaan prapelatihan pola suhu umum |
| 2 | Intel Berkeley Lab Data (MIT CSAIL) | Referensi pola kegagalan sensor nyata |
| 3 | Smart Manufacturing IoT-Cloud (Kaggle) | Pembanding struktur label & rasio anomali |
| 4 | NAB — realKnownCause (Numenta) | Set uji eksternal pada data suhu nyata |
| 5 | UAH-DriveSet (Universidad de Alcalá) | Referensi perilaku mengemudi untuk `harsh_events` |
| 6 | Taxi Trajectory Porto (ECML/PKDD) | Referensi realisme rute perkotaan |
| 7 | NASA POWER API | Suhu ambien & radiasi matahari nyata untuk Indonesia |

Dua di antaranya perlu penjelasan khusus.

**Dataset #1 berasal dari India, bukan Indonesia.** Perannya semata mengajarkan *bentuk kurva* suhu
— inersia termal dan siklus harian — karena fisika perpindahan panas bersifat universal. Nilai suhu
ambien Indonesia yang sesungguhnya diambil dari dataset #7 (NASA POWER) untuk koordinat Jakarta.
Inilah yang membuat simulasi kami mencerminkan kondisi tropis: rentang 26–31,3 °C dengan standar
deviasi 1,22, dibanding 5,7 pada data India.

**Dataset #5 berlisensi non-komersial dan dilarang didistribusikan ulang.** Kami hanya mengunduh
berkas data teks (tanpa video), memakai 1 dari 6 pengemudi, dan menyitasinya sesuai ketentuan
(Romera et al., ITSC 2016).

#### 4.1.3 Keputusan berbasis bukti dari eksplorasi data

**Temuan 1 — Rasio anomali dataset publik terlalu timpang untuk ditiru.** Dataset #3 hanya memuat
**8,9% anomali**. Bila kami meniru rasio itu, model akan belajar bahwa menebak "sehat" hampir selalu
benar, dan tidak pernah serius mempelajari pola kegagalan. Kami karena itu mendesain data sintetik
dengan rasio **60% sehat / 40% anomali** secara sengaja.

Dataset yang sama juga memperlihatkan cacat yang kami hindari: proporsi `failure_type` pada baris
`anomaly_flag=0` dan `anomaly_flag=1` nyaris identik, menandakan kedua kolom label dihasilkan
independen dan tidak saling menjamin konsistensi. Simulator kami menghasilkan ketiga label
(`is_anomaly`, `failure_mode`, `time_to_breach`) dari satu sumber kebenaran yang sama.

**Temuan 2 — Ambang suhu pada rancangan awal tidak seluruhnya akurat.** Kami memverifikasi ulang
tiap nilai `cargo_profiles.yaml` terhadap standar resmi dan menemukan tiga koreksi:

| Profil | Rancangan awal | Terverifikasi | Sumber |
|---|---|---|---|
| Vaksin | 2,0 – 8,0 °C | tidak berubah | WHO; BPOM No. 6/2020 tentang CDOB |
| Daging beku | −20,0 – −18,0 °C | **−25,0 – −18,0 °C** | Codex Alimentarius CAC/RCP 1-1969, USDA, FAO |
| Ikan segar | 0,0 – 4,0 °C | **0,0 – 5,0 °C** | SNI 01-2696.3-2006 |
| Sayur & buah | 4,0 – 8,0 °C | **2,0 – 4,0 °C** | Pedoman chiller HACCP |
| Produk susu | 2,0 – 6,0 °C | **2,0 – 4,0 °C** | Pedoman chiller HACCP |

**Temuan 3 — Tiga cacat label ditemukan melalui pengujian silang antar peran.** Ketiganya ditemukan
bukan oleh pembuat simulator, melainkan oleh anggota lain saat data yang sama dikonsumsi melalui
jalur berbeda (penyiapan pipeline pelatihan):

| Bug | Gejala | Perbaikan |
|---|---|---|
| 1 | `time_to_breach` konstan sepanjang satu perjalanan | versi v2 |
| 2 | Muatan berat nyaris tidak pernah melewati ambang (kalibrasi massa) | versi v3 |
| 3 | `is_anomaly`/`failure_mode` konstan per perjalanan | versi v4 |

Bug ketiga paling berdampak: **48,3% jendela pelatihan 60 menit salah label**. Setelah diperbaiki
di sumbernya, angka itu turun ke **0,00%** dengan metodologi pengukuran yang sama.

#### 4.1.4 Simulator dan katalog anomali

Data pelatihan utama dihasilkan simulator berbasis persamaan termal, dengan suhu ambien dan radiasi
matahari nyata dari NASA POWER sebagai masukan. Katalog anomalinya dirancang dari pola yang
benar-benar teramati pada data publik:

- **Sensor macet dan sensor berderau** dirancang dari dataset #2, yang memperlihatkan 17,7% data
  berupa pencilan ekstrem — termasuk nilai −38,4 °C dan 385,6 °C yang mustahil secara fisika.
- **Pola penurunan suhu mendadak** dilengkapi dari dataset #4, yang memuat dua anomali dengan waktu
  kejadian yang sudah diketahui pasti.
- **Pola berhenti-jalan dan kemacetan** mengacu pada dataset #6.
- **Frekuensi pengereman dan belokan keras** mengacu pada dataset #5.

#### 4.1.5 Validasi sim-to-real

**Uji Kolmogorov–Smirnov** menghasilkan KS = 1,0000 (p ≈ 0). Angka ini **tidak kami perlakukan
sebagai kegagalan**, melainkan sebagai pertanda bahwa ujinya tidak tepat guna: data pembanding
mengukur suhu ruangan tanpa pendingin aktif (21–51 °C), sedangkan data kami mengukur kargo yang
dijaga aktif oleh reefer (2–8 °C). Yang bermakna adalah kemiripan **pola**, bukan **nilai**.

**Uji Autocorrelation Function** dipakai sebagai pembanding utama:

| Lag (menit) | ACF nyata | ACF sintetik |
|---|---|---|
| 1 | 0,970 | 0,999 |
| 10 | 0,872 | 0,985 |
| 30 | 0,740 | 0,956 |
| 60 | 0,575 | 0,912 |

Kedua kurva menurun mulus dari ~1,0 tanpa lonjakan mendadak, menunjukkan struktur memori termal
yang konsisten dengan hukum perpindahan panas.

---

### 4.2 Alur pengembangan model (tiap fitur)

#### 4.2.1 Pendekatan

ColdTrack AI menghasilkan tiga keluaran dari satu masukan yang sama — jendela telemetri 60 menit
terakhir, 12 fitur per menit. Sistem akhir memakai **dua model dengan kontrak masukan identik**:

| | `coldtrack.onnx` | `coldtrack_ttb.onnx` |
|---|---|---|
| Arsitektur | GRU 2 lapis (hidden 64) + jalur statistik ringkasan | XGBoost, 300 pohon |
| Keluaran | prediksi suhu, probabilitas 7 kelas | Time-to-Breach |
| Ukuran | 169 KB | 950 KB |
| Latensi CPU | 1,1 ms | 0,09 ms |

Pembagian tugas ini bukan keputusan awal, melainkan hasil pengujian yang diuraikan di §4.2.6.

#### 4.2.2 Alur pengembangan umum

**Tahap 1 — Kontrak data.** Skema 12 kolom fitur dibekukan (`docs/feature_schema.md`), disertai tes
otomatis yang memastikan kolom label tidak pernah bocor menjadi masukan model. Melalui tes inilah
tiga cacat pelabelan pada dataset ditemukan (§4.1.3).

**Tahap 2 — Penyiapan masukan.** Data per menit dipecah menjadi jendela geser 60 langkah. Jendela
tidak pernah melintasi batas perjalanan, dan sasaran prediksi diambil dari **setelah** ujung jendela
sehingga tidak ada informasi masa depan yang bocor. Pembagian train/val/test dilakukan per
perjalanan, bukan per baris.

**Tahap 3 — Prapelatihan.** Backbone GRU dilatih pada korpus suhu IoT publik (1,3 juta jendela).

**Tahap 4 — Pelatihan model utama** pada korpus sintetik dengan ketiga head aktif.

**Tahap 5 — Evaluasi dan pemilihan.** Model dibandingkan dengan tiga baseline, diuji lewat dua
*ablation study*, lalu dievaluasi pada split test yang belum pernah disentuh selama pengembangan.

#### 4.2.3 Fitur 1 — Prediksi suhu (t+15 / t+30 / t+60)

**Model:** head regresi pada `coldtrack.onnx` (GRU).
**Metrik:** MAE pada t+30.
**Hasil:** **0,198 °C** terhadap target < 0,8 °C — **tercapai**, sekitar empat kali lebih akurat
daripada yang disyaratkan.

Fitur ini menjadi masukan bagi penilaian risiko: prediksi suhu maksimum pada ketiga horizon
dibandingkan terhadap ambang profil kargo.

#### 4.2.4 Fitur 2 — Klasifikasi mode kegagalan (7 kelas)

**Model:** head klasifikasi pada `coldtrack.onnx` (GRU), keluaran distribusi probabilitas 7 kelas.
**Metrik:** Macro F1.
**Hasil:** **0,581** terhadap target > 0,80 — **belum tercapai**.

Kelas yang dikenali: `A0` (sehat), `A1` (pintu terbuka lama), `A3`, `A7` (kejut ambien), `A8`,
`degradasi_bertahap`, `masalah_sensor`. Dua kelas terakhir merupakan hasil penggabungan dua kelas
asli (A2+A4 dan A5+A6).

Pada lima skenario demonstrasi, diagnosis model tepat seluruhnya. Namun **keyakinan sangat timpang
antar kelas**: pintu terbuka dan kejut ambien mencapai 100%, sedangkan degradasi bertahap hanya 35%
dan masalah sensor 52%.

Penjelasannya dapat ditelusuri. Pintu terbuka dan kejut ambien memiliki penanda eksplisit di dalam
masukan — `door_open` berupa nilai biner, dan radiasi ekstrem berupa angka yang mencolok — sehingga
model cukup membacanya. Sebaliknya, degradasi bertahap hanya bertanda kenaikan 0,01 °C per menit,
yang secara statistik mirip fluktuasi normal; dan pembacaan sensor yang diam pada satu nilai dapat
berarti sensor rusak maupun pendingin yang bekerja sangat baik. Kedua kelas berkeyakinan rendah itu
juga persis dua kelas hasil penggabungan, sehingga satu label harus menampung dua pola berbeda.

Konsekuensi desainnya: **keyakinan klasifikasi tidak dijadikan penentu status** (lihat §4.3.4).

#### 4.2.5 Fitur 3 — Time-to-Breach

**Model:** `coldtrack_ttb.onnx` (XGBoost 300 pohon), model terpisah.
**Metrik:** MAE pada rentang yang menentukan keputusan.
**Hasil:** **7,08 menit** untuk TTB ≤ 30 menit, terhadap target < 8 menit — **tercapai**.

Ini keluaran pembeda utama produk. Keandalannya sangat bergantung pada horizon:

| TTB sebenarnya | MAE |
|---|---|
| ≤ 10 menit | **3,30 menit** |
| ≤ 30 menit | **7,08 menit** |
| seluruh rentang | 52,00 menit |

Model akurat persis pada rentang yang menentukan keputusan operasional, dan tidak akurat di luar
itu. Memperkirakan kejadian lima jam ke depan dari jendela 60 menit berada di luar jangkauan
informasi yang tersedia. Antarmuka karena itu menampilkan angka TTB **hanya bila di bawah 30 menit**.

#### 4.2.6 Keputusan berbasis bukti

**Temuan 1 — GRU menghabiskan kapasitas untuk pekerjaan yang tidak perlu.** Model versi awal hanya
pernah menebak 2 dari 7 kelas. Setelah normalisasi fitur (rentang antar kolom timpang hingga 4500:1,
sehingga radiasi matahari menenggelamkan sinyal pintu terbuka) dan penyeimbangan bobot loss (head
prediksi suhu semula hanya memperoleh 2,3% dari total loss), performa membaik. Diagnosisnya: XGBoost
**menerima** statistik ringkasan jendela secara cuma-cuma, sementara GRU harus **menemukan sendiri**
cara menghitungnya sambil melayani tiga tugas. Statistik itu lalu disuplai langsung ke lapisan
keluaran, dengan tambahan hanya 792 parameter:

| | Macro F1 | Prediksi suhu | Time-to-Breach |
|---|---|---|---|
| Sebelum | 0,440 | 0,244 | 22,94 |
| **Sesudah** | **0,598** | **0,209** | **21,84** |

**Temuan 2 — Transfer learning tidak berhasil pada domain ini.** Dua konfigurasi dilatih dengan
resep identik:

| | Dari backbone pretrained | Dilatih dari nol |
|---|---|---|
| Loss latih akhir | **2,99** | 3,58 |
| Loss validasi akhir | 4,18 | **2,78** |

Arah keduanya berlawanan — pola khas *overfitting*. **Prapelatihan bukan sekadar tidak membantu,
melainkan merugikan.** Penyebabnya dapat dijelaskan: tidak ada dataset publik yang memuat telemetri
truk berpendingin, sehingga korpus terbaik hanya mampu mengisi **4 dari 12 fitur**. Delapan fitur
sisanya bernilai nol, sehingga bobot backbone terspesialisasi pada distribusi masukan yang timpang.

Sebelum menyimpulkan, kami memperbaiki dugaan penyebabnya lebih dulu: korpus prapelatihan diganti
dari 6.113 menjadi 1,3 juta jendela — 207 kali lebih besar. Hasilnya tidak berubah. **Model produksi
karena itu dilatih dari nol.**

**Temuan 3 — Model pohon lebih unggul untuk Time-to-Breach.** Tiga baseline diuji pada data sama:

| Metrik (split test) | GRU | XGBoost | Regresi linear | Isolation Forest |
|---|---|---|---|---|
| Prediksi suhu t+30 (°C) | 0,198 | **0,189** | 0,338 | — |
| Macro F1 | 0,581 | **0,664** | — | — |
| PR-AUC anomali | 0,711 | **0,753** | — | 0,371 |
| Time-to-Breach ≤ 30 menit | 17,9 | **7,1** | — | — |

**XGBoost mengungguli GRU pada seluruh metrik.** Kami memilih melaporkannya daripada
menyembunyikannya, dan mengambil konsekuensinya: Time-to-Breach dipindahkan ke XGBoost, karena di
situlah selisihnya terbesar dan satu-satunya perpindahan yang mengubah status target dari belum
tercapai menjadi tercapai. GRU dipertahankan untuk dua tugas lain karena selisih pada prediksi suhu
tipis dan keduanya jauh melampaui target; pada klasifikasi keduanya sama-sama belum mencapai ambang;
dan satu model GRU melayani dua keluaran sekaligus dalam 169 KB.

#### 4.2.7 Ringkasan hasil

| Keluaran | Metrik | Hasil | Target | Status |
|---|---|---|---|---|
| Prediksi suhu | MAE @ t+30 | **0,198 °C** | < 0,8 °C | tercapai |
| Mode kegagalan | Macro F1 | 0,581 | > 0,80 | belum |
| Time-to-Breach | MAE (≤ 30 menit) | **7,08 menit** | < 8 menit | tercapai |
| Deteksi anomali | PR-AUC | 0,711 | > 0,85 | belum |

Seluruh angka berasal dari **split test** — bagian data yang tidak pernah dipakai untuk mengambil
keputusan apa pun selama pengembangan. Angka pada split validasi lebih baik, tetapi karena split itu
dipakai berulang untuk memilih arsitektur, angkanya sudah condong optimistis dan tidak layak
dilaporkan sebagai hasil akhir.

---

### 4.3 Alur integrasi model ke environment kode

#### 4.3.1 Arsitektur

Layanan backend dirancang **sepenuhnya sinkron, stateless, dan bebas efek samping**. Seluruh alur
beroperasi *in-memory* tanpa basis data maupun pekerja latar belakang.

```
[ Frontend Next.js 14 ]
       │  POST /api/v1/analyze  (JSON, ≥ 60 bacaan telemetri)
       ▼
[ Backend FastAPI (Uvicorn, 1 worker) ]
       ├── 1. Validasi skema Pydantic v2
       ├── 2. Prapemrosesan & fitur turunan  →  tensor [1, 60, 12]
       ├── 3. Inferensi dua model ONNX:
       │      ├── coldtrack.onnx      → prediksi suhu + 7 kelas
       │      └── coldtrack_ttb.onnx  → Time-to-Breach
       ├── 4. Skoring risiko & penetapan status
       ├── 5. Mesin aturan → 3 tindakan berprioritas
       └── 6. Lapisan penjelasan → 3 faktor pendorong
       │
       ▼
[ Respons JSON tunggal ]
```

#### 4.3.2 Kepatuhan batasan MVP

| Batasan MVP | Status | Bukti pada repositori |
|---|---|---|
| Pemrosesan sinkron saja | Patuh | Tidak ada Celery, RQ, Redis, maupun cron job |
| Tanpa basis data | Patuh | Tidak ada ORM/driver SQL; skenario demo berupa berkas JSON statis |
| Tanpa otentikasi | Patuh | Tanpa login, sesi, JWT, maupun cookie |
| Satu perintah eksekusi | Patuh | `docker compose up --build` tanpa langkah manual |
| Parameter statis terpusat | Patuh | Seluruh ambang dan bobot dibekukan di `backend/config.yaml` |
| Antarmuka satu alur | Patuh | Satu halaman, satu masukan, satu keluaran AI |

#### 4.3.3 Alur pemrosesan

1. **Validasi skema.** Permintaan dengan < 60 bacaan ditolak `HTTP 400`, untuk mencegah statistik
   ringkasan jendela yang tidak pernah dilihat model saat pelatihan.
2. **Prapemrosesan.** Sebuah *Forbidden Column Guard* memastikan tidak ada kolom label
   (`is_anomaly`, `failure_mode`, `time_to_breach`, `time_to_breach_min`) lolos ke matriks fitur. Empat
   fitur turunan dihitung: Δtemp, Δambient, `reefer_duration_min`, dan `hour_of_day`.
3. **Inferensi dua model** dengan kontrak tensor identik `[1, 60, 12]`.
4. **Skoring risiko dan penetapan status** (§4.3.4).
5. **Mesin aturan** menghasilkan tiga tindakan berprioritas beserta estimasi waktu.
6. **Lapisan penjelasan** menghitung tiga faktor pendorong utama (§4.4.1).

#### 4.3.4 Penetapan status: model mengusulkan, aturan memutuskan

*Cargo Risk Index* (0,0–1,0) dihitung dari empat komponen berbobot yang dikonfigurasi di
`config.yaml`:

**R = 0,40·R_temp + 0,25·R_rate + 0,20·R_reefer + 0,15·R_door**

Status dasar ditetapkan secara deterministik — bukan dari R saja, tetapi juga dari prediksi suhu itu
sendiri — lalu disesuaikan oleh dua aturan keselamatan yang **sengaja bekerja dengan cara berbeda**:

| Aturan | Isi | Arah |
|---|---|---|
| Dasar | KRITIS bila R ≥ 0,70 **atau** prediksi suhu maksimum ≥ ambang kritis profil; WASPADA bila R ≥ 0,35 **atau** prediksi suhu maksimum > ambang maksimum profil | — |
| **Lantai Time-to-Breach** | TTB ≤ 30 menit → minimal KRITIS; ≤ 60 menit → minimal WASPADA | hanya menaikkan |
| **Penjepit sensor bermasalah** | diagnosis sensor → status ditetapkan WASPADA, indeks risiko dijepit ke 0,45–0,60, angka TTB disembunyikan | menaikkan **dan** menurunkan |

**Lantai TTB murni asimetris.** Ia hanya dipakai bila keparahannya lebih tinggi daripada status
dasar, sehingga kasus yang sudah benar tidak pernah berubah. Alasannya: status dasar hanya melihat
prediksi suhu, sedangkan TTB berasal dari model yang sepenuhnya terpisah — keduanya dapat tidak
sepakat. Perancangan asimetris ini mengikuti ketimpangan konsekuensi: kegagalan yang tidak
terdeteksi jauh lebih merugikan daripada peringatan berlebih. Aturan ini lahir dari kesalahan nyata
yang kami temukan pada pengujian ujung-ke-ujung; kasus lengkapnya diuraikan pada §4.4.2.

**Penjepit sensor sengaja bekerja dua arah**, dan itu bukan pengecualian yang terlewat melainkan
konsekuensi dari prinsip yang berbeda. Bila model mendiagnosis sensor macet atau rusak, seluruh
perhitungan di atas berdiri pada angka yang tidak dapat dipercaya: suhu terlihat stabil justru
*karena* sensornya beku, bukan karena muatannya aman.

- **Tidak boleh AMAN** — jangan memberi rasa aman palsu dari alat ukur yang sudah diketahui rusak.
- **Tidak boleh KRITIS** — jangan mengklaim kepastian dari alat ukur yang sama. Pada skenario
  "sensor macet", 60 bacaan terakhir bernilai identik (3,95 °C) namun model TTB tetap mengeluarkan
  23,8 menit. Angka itu hasil ekstrapolasi dari sinyal beku; menaikkannya ke KRITIS berarti
  menampilkan ketelitian yang tidak dimiliki sistem.

Pesan yang benar untuk kondisi ini adalah "alat ukur tidak dapat dipercaya, verifikasi manual" — dan
itu tepat WASPADA. Prinsipnya: **sistem tidak boleh mengklaim ketelitian yang melampaui alat
ukurnya**, baik ke arah menenangkan maupun ke arah menakut-nakuti.

#### 4.3.5 Gating Time-to-Breach

- **Truk sehat (kelas A0):** model mengembalikan `null`. Model TTB dilatih dengan *masking* pada
  jendela sehat, sehingga keluarannya pada kondisi normal tidak bermakna secara fisik.
- **Batas tampilan 30 menit:** prediksi model di atas 30 menit juga dikembalikan `null` —
  konsekuensi langsung dari profil MAE pada §4.2.5.
- **Cadangan berbasis aturan.** Bila model mengembalikan `null` sementara status berakhir WASPADA
  atau KRITIS, backend mengisi angkanya dengan ekstrapolasi linear dari laju kenaikan suhu lima
  menit terakhir: (ambang profil − suhu terkini) ÷ Δtemp rata-rata. Tanpa ini, layar dapat
  menampilkan peringatan KRITIS berdampingan dengan hitung mundur kosong. Angka cadangan ini
  **tidak berasal dari `coldtrack_ttb.onnx`**, sehingga MAE 7,08 menit pada §4.2.5 tidak berlaku
  untuknya, dan nilainya tidak dibatasi ambang 30 menit di atas.
- **Sensor bermasalah:** angka TTB disembunyikan sepenuhnya, termasuk hasil cadangan di atas
  (§4.3.4).

#### 4.3.6 Kontainer dan reproduksibilitas

Layanan dikemas dengan Docker *multi-stage build*. Tiga hal penting:

1. **Bobot model dikemas ke dalam citra** saat kompilasi. Citra tidak mengunduh artefak apa pun saat
   dijalankan, sehingga berhasil dieksekusi di lingkungan tanpa akses internet.
2. **Ukuran citra ringan.** Pemakaian `onnxruntime` CPU menggantikan PyTorch penuh menekan ukuran
   citra backend dari ~2,5 GB menjadi ~450 MB.
3. **Pemeriksaan kesehatan.** `GET /health` terhubung ke `healthcheck` Docker Compose, dan layanan
   frontend menunggu `condition: service_healthy` sebelum menerima lalu lintas.

Variabel `NEXT_PUBLIC_*` pada frontend diteruskan sebagai **build argument**, bukan variabel
runtime, karena Next.js menanamkan nilainya ke dalam bundel saat kompilasi. Kekeliruan pada titik
ini sempat menyebabkan antarmuka diam-diam kembali memakai data tiruan di dalam kontainer meski
backend berjalan normal — ditemukan dan diperbaiki melalui uji klon segar.

#### 4.3.7 Profil latensi terukur

| Skenario | p50 | p95 | p99 |
|---|---|---|---|
| 1 — Normal | 2,14 ms | 3,82 ms | 5,41 ms |
| 2 — Pintu terbuka | 2,08 ms | 3,65 ms | 4,98 ms |
| 3 — Kompresor melemah | 2,12 ms | 3,71 ms | 5,12 ms |
| 4 — Sensor macet | 2,15 ms | 3,80 ms | 5,30 ms |
| 5 — Kejut ambien | 2,09 ms | 3,68 ms | 5,05 ms |

Komposisinya: inferensi dua ONNX ~1,19 ms, prapemrosesan ~0,75 ms, mesin aturan dan serialisasi
~0,20 ms. Latensi p95 konsisten di bawah 4 ms — **250 kali lebih cepat daripada target 1000 ms**.

---

### 4.4 Metode lain yang mendukung pengambilan keputusan

#### 4.4.1 Lapisan penjelasan: atribusi faktor pendorong

Antarmuka menampilkan tiga faktor yang paling berkontribusi terhadap kondisi kargo. Lima sinyal
dinilai dari data masukan, tiga teratas diambil, lalu dinormalkan hingga berjumlah 1,0:

| Sinyal | Cara dinilai |
|---|---|
| Laju kenaikan suhu | rata-rata Δtemp terhadap ambang 0,05 °C/menit |
| Kenaikan suhu ambien | kenaikan sepanjang jendela, bukan selisih terhadap suhu kargo |
| Beban panas saat berhenti | radiasi matahari **dikalikan** proporsi waktu kendaraan diam |
| Status pintu kargo | seluruh jendela, dengan bobot dasar bila pintu pernah terbuka |
| Variansi pembacaan suhu | deviasi standar mendekati nol menandakan sensor macet |

Tiga keputusan desain pada lapisan ini lahir dari pengujian, bukan asumsi:

**Selisih suhu kargo terhadap ambien tidak dapat dipakai sebagai penanda bahaya.** Percobaan pertama
memakainya, dan sinyal itu menang di semua skenario termasuk perjalanan sehat. Sebabnya jelas: truk
berpendingin **memang selalu** berselisih 20–30 °C dengan udara luar — itu justru bukti pendinginnya
bekerja.

**Radiasi matahari sendirian juga bukan penanda.** Nilai 400–700 W/m² adalah kondisi siang hari
biasa. Yang berbahaya adalah terik **ditambah** kendaraan diam, karena aliran udara kondensor
hilang. Kombinasi inilah yang memisahkan skenario kejut ambien (diam 35% waktu di bawah 848 W/m²)
dari perjalanan siang lain yang tetap melaju.

**Efek pintu terbuka dan beban panas bertahan setelah kejadiannya lewat**, sehingga keduanya dinilai
dari seluruh jendela 60 bacaan, bukan 30 terakhir.

Hasilnya, tiap skenario menonjolkan penyebabnya sendiri:

| Skenario | Faktor teratas | Kontribusi |
|---|---|---|
| Normal | *tidak ada yang menonjol* | 33 / 33 / 33 |
| Pintu terbuka | status pintu kargo | 83% |
| Kompresor melemah | laju kenaikan suhu | 71% |
| Sensor macet | variansi pembacaan suhu | 91% |
| Kejut ambien | beban panas saat berhenti | 91% |

**Keterbatasan yang kami nyatakan secara eksplisit:** atribusi ini bersifat **heuristik**, dihitung
dari data masukan dan **bukan** hasil pembongkaran bobot model. Metode atribusi formal seperti SHAP
belum diterapkan dan masuk rencana pengembangan.

#### 4.4.2 Pengujian ujung-ke-ujung sebagai metode verifikasi

Metrik model yang baik belum menjamin sistem yang benar. Hal ini kami buktikan sendiri.

Pada pengujian ujung-ke-ujung ditemukan bahwa status keselamatan dihitung **semata dari prediksi
suhu**, sementara Time-to-Breach dihasilkan model yang terpisah. Keduanya dapat tidak sepakat — dan
memang tidak sepakat. Pada skenario kompresor melemah:

```
prediksi suhu maksimum = 3,73 °C   (ambang profil = 4,0 °C)
   → tidak melanggar → risk 0,11 → status AMAN
Time-to-Breach model   = 19,5 menit → MELANGGAR, tetapi diabaikan
```

Antarmuka menampilkan lampu hijau "AMAN" tepat di sebelah tulisan "19 menit lagi sebelum ambang
terlampaui", dan rekomendasi tindakannya berbunyi "lanjutkan pemantauan rutin". Empat dari lima
skenario terdampak.

Perbaikannya berupa dua aturan eskalasi pada §4.3.4. Kecocokan status terhadap status yang
diharapkan naik dari **1/5 menjadi 5/5**.

Kami mencantumkan kejadian ini apa adanya karena inilah bentuk verifikasi yang bekerja: ditemukan
lewat pengujian pada sistem utuh, ditelusuri ke akarnya, lalu diperbaiki dengan aturan yang dapat
diaudit siapa pun tanpa membaca bobot model.

#### 4.4.3 Tata kelola AI dan pengawasan manusia

**Model tidak mengambil keputusan akhir.** Pemisahan tanggung jawabnya eksplisit:

| Dikerjakan model AI | Dikerjakan mesin aturan |
|---|---|
| Prediksi suhu t+15/30/60 | Penetapan status AMAN / WASPADA / KRITIS |
| Klasifikasi mode kegagalan | Pemilihan tiga langkah tindakan |
| Estimasi Time-to-Breach | Penerapan ambang keselamatan |

Ambang keselamatan berada di `config.yaml` dan dapat ditinjau siapa pun tanpa membaca bobot model.
Sistem ini adalah **alat bantu keputusan bagi operator**, bukan sistem kendali otomatis — tidak ada
aktuator yang dikendalikan langsung oleh keluaran model, dan operator dapat mengabaikan seluruh
rekomendasi tanpa hambatan teknis.

**Sistem menolak menyatakan aman ketika alat ukurnya tidak dapat dipercaya.** Ini contoh
*human-in-the-loop* yang konkret: pada diagnosis sensor bermasalah, status dikunci WASPADA dan angka
TTB disembunyikan, dengan tindakan pertama berbunyi "verifikasi suhu kargo secara manual dengan
termometer cadangan".

**Risiko yang kami petakan:**

| Risiko | Mitigasi |
|---|---|
| Sensor rusak menghasilkan pembacaan palsu | Status dikunci WASPADA, TTB disembunyikan |
| Keyakinan klasifikasi rendah pada kerusakan halus | Status tidak bergantung pada keyakinan |
| Model gagal dimuat | Jatuh ke mesin aturan heuristik, versi dilaporkan `coldtrack-rule-v1.0` |
| Data masukan terlalu pendek | Ditolak, bukan dijawab dengan tebakan |

**Yang belum ada dan kami akui:** tidak ada pemantauan pergeseran distribusi data, tidak ada
mekanisme umpan balik operator untuk mengoreksi diagnosis yang salah, dan tidak ada pencatatan
riwayat prediksi. Ketiganya memerlukan basis data, yang sengaja tidak dipakai pada tahap ini.

**Kepatuhan dan keadilan.** Ambang suhu mengacu pada standar yang dapat ditelusuri (§4.1.3). Namun
durasi toleransi eksursi suhu **bukan** kutipan regulasi — tidak ada aturan yang menyatakannya
sebagai angka tunggal, sehingga nilai yang kami pakai adalah asumsi desain simulasi yang
konservatif. Sistem ini juga **bukan alat pemenuhan regulasi**: tidak menerbitkan sertifikat
kepatuhan dan tidak menggantikan pencatatan suhu resmi yang diwajibkan CDOB. Dari sisi keadilan,
sistem menilai kondisi kargo dan kendaraan, bukan orang — tidak ada data pribadi pengemudi yang
diproses dan tidak ada keluaran yang menilai kinerja individu.

---

## 5. Kesimpulan

### 5.1 Apa yang berhasil

ColdTrack AI mengubah telemetri rantai dingin yang selama ini hanya dicatat menjadi keputusan yang
dapat ditindaklanjuti. Dari satu masukan berupa deret pembacaan sensor, sistem menghasilkan prediksi
suhu, diagnosis jenis kerusakan, jumlah menit tersisa sebelum ambang terlampaui, dan tiga langkah
tindakan yang sesuai penyebabnya — seluruhnya sinkron pada CPU biasa dengan latensi p95 di bawah
4 ms.

**Dua dari empat sasaran metrik tercapai.** Prediksi suhu melampaui targetnya sekitar empat kali
lipat, dan Time-to-Breach tercapai pada rentang yang menentukan keputusan. Pada kelima skenario
demonstrasi, diagnosis model tepat seluruhnya dan status yang dihasilkan sesuai yang diharapkan.

### 5.2 Apa yang kami pelajari — termasuk yang tidak sesuai rencana

**Prapelatihan justru merugikan.** Rencana awal kami gagal secara terukur, dan model final dilatih
dari nol.

**Model pohon mengungguli jaringan saraf pada tugas Time-to-Breach**, sehingga sistem final memakai
dua model, bukan satu.

**Kesalahan paling berbahaya ditemukan di tahap integrasi, bukan pemodelan.** Status sempat
bertentangan dengan Time-to-Breach pada empat dari lima skenario. Metrik model yang baik tidak
menjamin sistem yang benar.

### 5.3 Keterbatasan yang kami akui

- **Belum pernah diuji pada telemetri truk sungguhan.** Validasi sim-to-real menunjukkan data kami
  secara kuantitatif lebih stabil daripada data nyata, sebagian karena fisika dan sebagian kami duga
  karena parameter derau simulator terlalu kecil.
- **Dua sasaran metrik belum tercapai**, dan kami memilih melaporkannya apa adanya. Menurunkan
  target setelah melihat hasil akan terbaca sebagai menyesuaikan ukuran pada hasil yang sudah
  didapat.
- **Degradasi bertahap hampir tidak terdeteksi** — recall 10,6%. Kami tidak mengklaim sistem ini
  mampu mendeteksi kompresor yang melemah secara andal.
- **Atribusi fitur masih heuristik**, bukan metode formal seperti SHAP.

### 5.4 Langkah berikutnya

| Prioritas | Langkah | Alasan |
|---|---|---|
| 1 | Uji lapangan pada armada mitra | Satu-satunya cara menutup kesenjangan sim-to-real |
| 2 | Pelatihan ulang dengan telemetri nyata | Metrik saat ini belum teruji di luar simulasi |
| 3 | Menaikkan derau simulator | Data sintetik terbukti terlalu bersih |
| 4 | Memisahkan kembali kelas yang digabung | Kemungkinan penyebab keyakinan rendah |
| 5 | Atribusi fitur formal (SHAP) | Memperkuat dasar penjelasan yang ditampilkan |
| 6 | Pemantauan pergeseran data & umpan balik operator | Prasyarat penggunaan berkelanjutan |

### 5.5 Penutup

Nilai sebuah sistem peringatan dini tidak terletak pada ketepatan angkanya semata, melainkan pada
apakah ia memberi manusia cukup waktu untuk bertindak. Selisih antara "muatan sudah rusak" dan
"muatan aman 23 menit lagi" adalah selisih antara mencatat kerugian dan mencegahnya.

Kami membangun sistem ini dengan menjaga agar setiap angka yang tampil di layar dapat dijelaskan
asal-usulnya, dan setiap keterbatasan dinyatakan lebih dulu sebelum ditanyakan. Itu pula yang kami
anggap sebagai syarat sebuah sistem AI layak dipercaya untuk keputusan yang menyangkut keselamatan
pangan dan farmasi.

---

## Daftar Pustaka

> *Tidak dihitung dalam batas 20 halaman.*

`[ISI: susun sitasi lengkap untuk seluruh sumber yang ditandai [sumber: ...] di atas, serta:]`

1. World Health Organization — pedoman penyimpanan vaksin 2–8 °C.
2. Badan POM RI. Peraturan No. 6 Tahun 2020 tentang Cara Distribusi Obat yang Baik (CDOB).
3. Codex Alimentarius. CAC/RCP 1-1969, *General Principles of Food Hygiene*.
4. Badan Standardisasi Nasional. SNI 01-2696.3-2006.
5. Romera, E., Bergasa, L. M., & Arroyo, R. (2016). Need Data for Driver Behaviour Analysis?
   Presenting the Public UAH-DriveSet. *IEEE ITSC 2016*.
6. NASA POWER Project. https://power.larc.nasa.gov/
7. Numenta Anomaly Benchmark (NAB).
8. `[ISI: sumber angka 14,29% PDB]`
9. `[ISI: sumber target 8% pada 2045]`
10. `[ISI: sumber 23–48 juta ton food loss and waste]`

---

## Lampiran

> *Tidak dihitung dalam batas 20 halaman.*

| Lampiran | Isi | Berkas |
|---|---|---|
| A | Kurva loss pretrain vs dari nol | `ml/reports/loss_curves.png` |
| B | Confusion matrix 7 kelas | `ml/reports/confusion_matrix.png` |
| C | MAE Time-to-Breach per horizon | `ml/reports/ttb_by_horizon.png` |
| D | Model Card lengkap | `docs/model_card.md` |
| E | Dataset Card lengkap | `docs/dataset_card.md` |
| F | Kontrak API | `docs/api_contract.md` |
| G | Skema fitur 12 kolom | `docs/feature_schema.md` |
| H | Tangkapan layar antarmuka (5 skenario) | `[ISI: belum diambil]` |
