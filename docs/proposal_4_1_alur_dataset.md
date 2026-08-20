# 4.1 Alur Dataset

## 4.1.1 Pendekatan

Masalah mendasar yang kami hadapi di awal: **tidak ada dataset publik yang menyediakan label
kebenaran untuk kegagalan rantai dingin.** Ada banyak data suhu IoT, tetapi tidak satu pun yang
mencantumkan "pada menit ke berapa muatan ini akan melewati ambang", apalagi "jenis kerusakan apa
yang sedang terjadi". Padahal justru dua label itulah inti produk kami.

Karena itu kami menempuh jalur dua lapis:

1. **Data publik nyata** dipakai untuk mempelajari bentuk dinamika suhu, mengkalibrasi struktur
   label, menyediakan suhu ambien Indonesia yang sebenarnya, dan menjadi pembanding eksternal.
2. **Simulator fisika yang kami bangun sendiri** dipakai menghasilkan data pelatihan utama, karena
   hanya dengan simulator kami dapat mengetahui — bukan menebak — kapan sebuah muatan melewati
   ambang dan mengapa.

Tidak satu pun dari tujuh dataset publik di bawah ini dipakai mentah sebagai data pelatihan fitur
inti. Perannya adalah prapelatihan, kalibrasi, dan validasi.

## 4.1.2 Sumber data dan perannya

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

**Dataset #1 berasal dari India, bukan Indonesia.** Perannya semata mengajarkan *bentuk kurva*
suhu — inersia termal dan siklus harian — karena fisika perpindahan panas bersifat universal.
Nilai suhu ambien Indonesia yang sesungguhnya diambil dari dataset #7 (NASA POWER), yang kami
tarik untuk koordinat Jakarta. Inilah yang membuat simulasi kami mencerminkan kondisi tropis:
rentang 26–31,3 °C dengan standar deviasi 1,22, dibanding 5,7 pada data India.

**Dataset #5 berlisensi non-komersial dan dilarang didistribusikan ulang.** Kami hanya mengunduh
berkas data teks (tanpa video), memakai 1 dari 6 pengemudi, dan menyitasinya sesuai ketentuan
(Romera et al., ITSC 2016). Perannya terbatas sebagai referensi statistik perilaku, bukan data
pelatihan.

## 4.1.3 Keputusan berbasis bukti

Eksplorasi data tidak kami perlakukan sebagai formalitas. Tiga temuan berikut mengubah keputusan
desain secara langsung.

### Temuan 1 — Rasio anomali dataset publik terlalu timpang untuk ditiru

Dataset #3 hanya memuat **8,9% anomali**. Bila kami meniru rasio itu, model akan belajar bahwa
menebak "sehat" hampir selalu benar, dan tidak pernah serius mempelajari pola kegagalan. Kami
karena itu mendesain data sintetik dengan rasio **60% sehat / 40% anomali** secara sengaja.

Dataset yang sama juga memperlihatkan cacat yang kami hindari: proporsi `failure_type` pada baris
`anomaly_flag=0` dan `anomaly_flag=1` nyaris identik, menandakan kedua kolom label dihasilkan
secara independen dan tidak saling menjamin konsistensi. Simulator kami menghasilkan ketiga label
(`is_anomaly`, `failure_mode`, `time_to_breach`) dari satu sumber kebenaran yang sama.

### Temuan 2 — Ambang suhu di rancangan awal tidak seluruhnya akurat

Rancangan awal mencantumkan `cargo_profiles.yaml` sebagai rujukan "standar nyata" tanpa merinci
sumber per produk. Kami memverifikasi ulang tiap nilai dan menemukan **tiga koreksi**:

| Profil | Rancangan awal | Terverifikasi | Sumber |
|---|---|---|---|
| Vaksin | 2,0 – 8,0 °C | tidak berubah | WHO; BPOM No. 6/2020 tentang CDOB |
| Daging beku | −20,0 – −18,0 °C | **−25,0 – −18,0 °C** | Codex Alimentarius CAC/RCP 1-1969, USDA, FAO |
| Ikan segar | 0,0 – 4,0 °C | **0,0 – 5,0 °C** | SNI 01-2696.3-2006 |
| Sayur & buah | 4,0 – 8,0 °C | **2,0 – 4,0 °C** | Pedoman chiller HACCP |
| Produk susu | 2,0 – 6,0 °C | **2,0 – 4,0 °C** | Pedoman chiller HACCP |

### Temuan 3 — Tiga cacat label ditemukan melalui pengujian silang antar peran

Tiga bug ditemukan bukan oleh pembuat simulator, melainkan oleh R2 saat menyiapkan pipeline
pelatihan — yaitu ketika data yang sama dikonsumsi lewat jalur berbeda:

| Bug | Gejala | Perbaikan |
|---|---|---|
| 1 | `time_to_breach` konstan sepanjang satu perjalanan | versi v2 |
| 2 | Muatan berat nyaris tidak pernah melewati ambang (kalibrasi massa) | versi v3 |
| 3 | `is_anomaly`/`failure_mode` konstan per perjalanan | versi v4 |

Bug ketiga paling berdampak: **48,3% jendela pelatihan 60 menit salah label** pada tiga mode
kegagalan yang terukur. Setelah diperbaiki di sumbernya, angka itu turun ke **0,00%** dengan
metodologi pengukuran yang sama.

Kami mencantumkan riwayat ini apa adanya karena menunjukkan siklus validasi silang yang benar-benar
berjalan — satu peran membangun, peran lain menguji lewat jalur konsumsi berbeda, lalu diperbaiki
di sumbernya, bukan ditambal di hilir.

## 4.1.4 Simulator dan katalog anomali

Data pelatihan utama dihasilkan simulator berbasis persamaan termal, dengan suhu ambien dan
radiasi matahari nyata dari NASA POWER sebagai masukan. Katalog anomalinya dirancang dari pola
yang benar-benar teramati pada data publik, bukan dikarang:

- **Sensor macet dan sensor berderau** dirancang dari dataset #2, yang memperlihatkan 17,7% data
  berupa pencilan ekstrem — termasuk nilai −38,4 °C dan 385,6 °C yang mustahil secara fisika.
  Sebarannya acak di hampir semua sensor, menandakan gangguan transmisi sesaat, bukan kerusakan
  permanen satu perangkat.
- **Pola penurunan suhu mendadak** dilengkapi dari dataset #4, yang memuat dua anomali penurunan
  tajam dengan waktu kejadian yang sudah diketahui pasti.
- **Pola berhenti-jalan dan kemacetan** mengacu pada dataset #6.
- **Frekuensi pengereman dan belokan keras** mengacu pada dataset #5.

## 4.1.5 Validasi sim-to-real

Kami menguji kemiripan data sintetik terhadap data IoT publik pada perjalanan kondisi sehat.

**Uji Kolmogorov–Smirnov** menghasilkan KS = 1,0000 (p ≈ 0). Angka ini **tidak kami perlakukan
sebagai kegagalan**, melainkan sebagai pertanda bahwa ujinya tidak tepat guna: data pembanding
mengukur suhu ruangan tanpa pendingin aktif (21–51 °C), sedangkan data kami mengukur kargo yang
dijaga aktif oleh reefer (2–8 °C). Dua sistem dengan rentang operasi yang memang berbeda secara
desain tentu tidak tumpang tindih. Yang bermakna adalah kemiripan **pola**, bukan **nilai**.

**Uji Autocorrelation Function** dipakai sebagai pembanding utama:

| Lag (menit) | ACF nyata | ACF sintetik |
|---|---|---|
| 1 | 0,970 | 0,999 |
| 10 | 0,872 | 0,985 |
| 30 | 0,740 | 0,956 |
| 60 | 0,575 | 0,912 |

Kedua kurva menurun mulus dari ~1,0 tanpa lonjakan mendadak, menunjukkan struktur memori termal
yang konsisten dengan hukum perpindahan panas.

## 4.1.6 Keterbatasan yang kami sadari

**Data sintetik kami terlalu bersih.** Pada lag 60 menit, ACF sintetik masih 0,912 sementara data
nyata sudah turun ke 0,575 — artinya suhu kargo kami lebih stabil dan lebih mudah diprediksi
daripada data pembanding. Sebagian dapat dijelaskan secara fisika, karena sistem dengan reefer
aktif memang lebih teregulasi daripada ruangan pasif. Namun kami juga menduga parameter derau
simulator (σ = 0,05 °C) lebih kecil daripada variabilitas sensor sungguhan. Menaikkan derau adalah
perbaikan yang sudah kami identifikasi untuk iterasi berikutnya.

**Dua kolom pada `cargo_profiles.yaml` bukan kutipan standar resmi.** Kolom `massa_kg` dan
`toleransi_menit` kami tetapkan sebagai asumsi desain simulasi yang konservatif. Tidak ada regulasi
yang menyatakan durasi toleransi eksursi suhu dalam satu angka tunggal; nilainya sangat bergantung
pada produk, formulasi, dan riwayat suhu sebelumnya — konsep *cumulative excursion* yang lebih
rumit daripada sekadar durasi. Kedua kolom itu semata alat untuk menghasilkan label Time-to-Breach,
bukan representasi ambang toleransi resmi produk tertentu.

**Korpus prapelatihan tidak terpakai pada model final.** Dataset #1 semula disiapkan sebagai
korpus prapelatihan. Evaluasi pada tahap pengembangan model menunjukkan prapelatihan justru
menurunkan performa pada data validasi, sehingga model final dilatih dari nol. Rinciannya
dijelaskan pada Bagian 4.2. Perannya kini terbatas sebagai pembanding sim-to-real.

**Rute sintetik tidak meniru geografi nyata Indonesia.** Dataset #6 hanya menjadi rujukan pola
berhenti-jalan, bukan sumber rute. Uji lapangan pada rute distribusi Indonesia yang sesungguhnya
belum dilakukan.
