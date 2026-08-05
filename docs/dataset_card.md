# Dataset Card — ColdTrack AI

Dokumen ini menjelaskan seluruh dataset publik yang digunakan tim ColdTrack AI, perannya dalam
pipeline, serta temuan penting dari proses eksplorasi data (EDA). Model AI kami tidak dilatih dari
nol maupun murni disintesis — kami mengambil pola dinamika suhu dari data IoT dunia nyata,
lalu menalanya (fine-tune) ke domain rantai dingin menggunakan data sintetik yang kami bangun sendiri
(lihat Bagian 2 Playbook Teknis). Dataset di bawah ini adalah fondasi tahap pretraining dan validasi.

---

## Ringkasan Peran Tiap Dataset

| # | Dataset | Peran dalam Proyek |
|---|---|---|
| 1 | Temperature Readings: IoT Devices | Pretraining pola suhu normal (siklus harian) |
| 2 | Intel Berkeley Lab Data | Referensi pola kegagalan sensor nyata |
| 3 | Smart Manufacturing IoT-Cloud | Pembanding struktur & rasio label anomali |
| 4 | NAB (realKnownCause) | Set uji eksternal untuk generalisasi model |
| 5 | UAH-DriveSet | Referensi perilaku pengemudi (agresif/mengantuk) |
| 6 | Taxi Trajectory Porto | Referensi realisme rute (pola macet/berhenti) |
| 7 | NASA POWER API | Suhu ambien nyata untuk koordinat Indonesia |

---

## 1. Temperature Readings: IoT Devices

- **Sumber**: Kaggle (atulanandjha) — https://www.kaggle.com/datasets/atulanandjha/temperature-readings-iot-devices
- **Lisensi**: GNU Lesser General Public License 3.0
- **Ukuran**: 97.606 baris, suhu ruangan indoor/outdoor
- **Peran**: Korpus pretraining utama backbone GRU — mengajarkan model dinamika suhu umum (inersia
  termal, siklus harian).

**Temuan EDA:**
- Data bersih, tanpa missing value.
- Rentang suhu 21–51°C — wajar untuk iklim India (bukan anomali, bukan bug).
- Mayoritas data (77.261 baris) berlabel "Out" (outdoor), sisanya "In" (indoor) — kami memfilter
  hanya data outdoor karena lebih relevan dengan kondisi kargo yang terekspos suhu ambien.
- Interval pencatatan tidak konsisten: median gap 0 menit, tapi gap maksimum mencapai ~11,5 hari.
  Perlu resampling ke interval 1 menit sebelum dipakai untuk pretraining.
- Pola diurnal (naik siang, turun dini hari) terkonfirmasi jelas saat di-zoom ke skala satu hari.

**Catatan penting**: dataset ini berasal dari India, bukan Indonesia. Perannya hanya untuk
mengajarkan model *bentuk kurva* suhu secara umum (fisika perpindahan panas bersifat universal),
bukan nilai suhu ambien Indonesia. Nilai suhu ambien Indonesia yang sesungguhnya berasal dari
dataset #7 (NASA POWER).

---

## 2. Intel Berkeley Lab Data

- **Sumber**: MIT CSAIL — http://db.csail.mit.edu/labdata/labdata.html
- **Ukuran**: 2.313.682 baris, 54 sensor (suhu, kelembapan, tegangan)
- **Peran**: Referensi pola kegagalan sensor nyata untuk desain katalog anomali sintetik kami
  (A5: sensor macet, A6: sensor berderau/paket hilang).

**Temuan EDA:**
- **17,7% dari seluruh data adalah outlier ekstrim** (suhu di luar rentang 0–50°C, termasuk nilai
  -38,4°C dan 385,6°C yang mustahil secara fisik).
- Outlier tersebar acak di hampir semua sensor (bukan disebabkan oleh sensor tertentu yang rusak
  permanen) — mengindikasikan noise/glitch transmisi sesaat, bukan kegagalan hardware total.
- Dua sensor (moteid 5 dan 57) hampir tidak pernah mengirim data (<40 baris dari total jutaan),
  kemungkinan mati/kehabisan baterai di awal pengumpulan data.
- Ditemukan beberapa moteid dengan ID tidak valid (contoh: 65407) — bit error transmisi, dibuang
  saat pembersihan data.

---

## 3. Smart Manufacturing IoT-Cloud Monitoring Dataset

- **Sumber**: Kaggle (ziya07) — https://www.kaggle.com/datasets/ziya07/smart-manufacturing-iot-cloud-monitoring-dataset
- **Lisensi**: CC0-1.0
- **Ukuran**: 100.000 baris, data sensor mesin manufaktur
- **Peran**: Kalibrasi struktur label dan rasio kelas anomali sebelum data sintetik kami sendiri
  siap; latihan pipeline pemrosesan.

**Temuan EDA:**
- Struktur labelnya sangat mirip rencana skema kami: `anomaly_flag` (biner) setara `is_anomaly`,
  `failure_type` (5 kategori) setara `failure_mode`, `predicted_remaining_life` setara konsep
  Time-to-Breach kami.
- Rasio anomali hanya **8,9%** — jauh lebih imbalanced dibanding target desain kami (60% sehat /
  40% anomali). Ini memperkuat alasan kami sengaja mendesain rasio yang lebih seimbang, supaya
  model tidak "malas" belajar pola anomali.
- Ditemukan inkonsistensi antar-label: proporsi `failure_type` pada baris dengan `anomaly_flag=0`
  dan `anomaly_flag=1` nyaris identik, menandakan kedua kolom label dihasilkan secara independen
  (tidak saling menjamin konsistensi). Kami menghindari pola ini dengan menghasilkan ketiga label
  (`is_anomaly`, `failure_mode`, `time_to_breach`) dari satu sumber kebenaran yang sama di
  simulator kami.

---

## 4. NAB — Numenta Anomaly Benchmark (realKnownCause)

- **Sumber**: Kaggle (boltzmannbrain/nab) — https://www.kaggle.com/datasets/boltzmannbrain/nab
- **File yang digunakan**: `ambient_temperature_system_failure.csv` (7.267 baris, interval 1 jam),
  `machine_temperature_system_failure.csv` (22.695 baris, interval 5 menit)
- **Peran**: Set uji eksternal untuk mengukur generalisasi model pada data suhu nyata dengan
  anomali yang waktunya sudah diketahui secara pasti (ground truth publik).

**Temuan EDA:**
- Nilai mentah dalam skala Fahrenheit, dikonversi ke Celsius sebelum digunakan.
- Data `machine_temperature` menunjukkan osilasi rutin (kemungkinan siklus HVAC ruang server) dan
  dua anomali penurunan suhu tajam yang tercatat (~15 Des 2013 dan ~15 Feb 2014) — pola kegagalan
  "penurunan mendadak" ini melengkapi katalog anomali kami yang sebagian besar berupa kenaikan suhu.

---

## 5. UAH-DriveSet

- **Sumber**: Universidad de Alcalá — http://www.robesafe.uah.es/personal/eduardo.romera/uah-driveset/
- **Lisensi**: Non-komersial/akademik saja — **dilarang didistribusikan ulang**, wajib disitasi
  (Romera et al., ITSC 2016)
- **Ukuran unduhan penuh**: ±3,3 GB (termasuk video perjalanan; data sensor teks jauh lebih kecil)
- **Cakupan yang kami gunakan**: 1 dari 6 driver (D1), 7 rute (kombinasi normal/drowsy/aggressive
  pada motorway/secondary road). Video tidak diunduh — hanya file data teks yang relevan.
- **Peran**: Referensi statistik perilaku mengemudi (normal/mengantuk/agresif) dan frekuensi event
  pengereman/belokan keras untuk parameter `harsh_events` di simulator kami. Bukan data pelatihan
  utama, sehingga sampel 1 driver dinilai cukup representatif untuk tujuan ini.
- **Catatan akses**: unduhan memerlukan persetujuan lisensi manual via formulir di situs resmi
  (tidak bisa diunduh otomatis via script/API).

**Temuan EDA — struktur `SEMANTIC_FINAL.txt`:**
- Format unik: satu file berisi 54 nilai, satu nilai per baris (bukan tabel kolom seperti file
  lain), merangkum satu rute penuh. Definisi tiap baris merujuk pada README resmi dataset.
- Berisi metadata rute (waktu, kecepatan, jarak), skor performa mengemudi per kategori (0–100:
  accelerations, brakings, turnings, lane-weaving, lane-drifting, overspeeding, car-following),
  jumlah event low/medium/high untuk akselerasi/pengereman/belokan, serta rasio perilaku
  (normal/drowsy/aggressive, basis 0–1).
- **Validasi silang label**: pada rute berlabel `DROWSY-MOTORWAY`, rasio "drowsy" hasil analisis
  memang paling dominan (55,7%, dibanding normal 32,4% dan aggressive 11,9%), dan score brakings
  (38,1/100) serta lane-weaving (26,3/100) sama-sama rendah — konsisten dengan ciri khas
  pengemudi mengantuk (reaksi rem telat, kendaraan kurang stabil di jalur). Ini menunjukkan label
  perilaku pada dataset ini akurat dan dapat diandalkan sebagai referensi.

---

## 6. Taxi Service Trajectory — Porto

- **Sumber**: Kaggle (crailtap/taxi-trajectory), dataset kompetisi ECML/PKDD
- **Ukuran**: 1,9 GB, ~1,7 juta trip taksi
- **Peran**: Referensi realisme rute perkotaan (pola berhenti-jalan, kemacetan) untuk generator
  rute sintetik kami — bukan untuk meniru rute Porto secara langsung.

**Temuan EDA:**
- Setiap baris merepresentasikan satu trip utuh; rute tersimpan sebagai daftar koordinat
  [longitude, latitude] pada kolom `POLYLINE`, dicatat tiap 15 detik.
- Median durasi trip ~10 menit — wajar untuk perjalanan taksi dalam kota.
- Ditemukan outlier: trip berdurasi 0 detik (data rusak/trip batal) dan trip hingga 10,5 jam
  (kemungkinan GPS macet). Kedua jenis outlier ini difilter sebelum dipakai sebagai referensi.

---

## 7. NASA POWER API

- **Sumber**: NASA POWER — https://power.larc.nasa.gov/ (gratis, tanpa API key)
- **Parameter diambil**: `T2M` (suhu udara 2m), `ALLSKY_SFC_SW_DWN` (radiasi matahari)
- **Peran**: Sumber suhu ambien dan beban radiasi matahari yang benar-benar mewakili kondisi
  Indonesia (Jakarta) — inilah yang membuat simulasi kami "terasa Indonesia", berbeda dari dataset
  #1 yang hanya mengajarkan pola umum.

**Temuan EDA (sampel Jakarta, 1–7 Jan 2024):**
- Rentang suhu 26–31,3°C, jauh lebih stabil dibanding dataset IoT India (std 1,22 vs 5,7) — sesuai
  karakter iklim tropis.
- Pola diurnal jelas: suhu terendah dini hari, tertinggi siang hari.
- Radiasi matahari berkorelasi langsung dengan kenaikan suhu (radiasi 0 di malam hari, naik tajam
  mulai jam 6 pagi) — data ini menjadi input langsung untuk komponen `k_solar` pada persamaan
  termal simulator (lihat Bagian 2.3 Langkah 4, Playbook Teknis).

---

## Verifikasi Cargo Profiles (Bagian 2.3 Langkah 1 Playbook Teknis)

Playbook Teknis awal mencantumkan nilai `cargo_profiles.yaml` sebagai referensi dari "standar
nyata (CDOB BPOM untuk farmasi, praktik HACCP untuk pangan)" tanpa merinci sumber per-produk.
Kami melakukan verifikasi tambahan terhadap tiap nilai dan menemukan sebagian besar rentang suhu
sudah akurat, dengan tiga koreksi kecil. Dua kolom lain (`massa_kg`, `toleransi_menit`) dikonfirmasi
**bukan** berasal dari standar resmi — ini penting diungkapkan secara jujur di proposal.

| Profil | Nilai di Playbook (asli) | Nilai Terverifikasi | Sumber |
|---|---|---|---|
| Vaksin | 2,0 – 8,0°C | **Tidak berubah** — 2,0 – 8,0°C | WHO; Peraturan BPOM No. 6/2020 (perubahan dari No. 9/2019) tentang CDOB — cold room/chiller wajib 2–8°C, alarm deviasi disarankan pada 2,5–7,5°C |
| Daging beku | -20,0 – -18,0°C | **Direvisi** — -25,0 – -18,0°C | Codex Alimentarius CAC/RCP 1-1969, USDA, FAO — standar umum ≤ -18°C dengan rentang operasional hingga -25°C |
| Ikan segar | 0,0 – 4,0°C | **Direvisi** — 0,0 – 5,0°C | SNI 01-2696.3-2006 (filet kakap beku) — suhu maksimal 5°C |
| Sayur & buah | 4,0 – 8,0°C | **Direvisi** — 2,0 – 4,0°C | Pedoman chiller HACCP — rekomendasi optimal 2–4°C untuk sayuran berdaun hijau |
| Produk susu | 2,0 – 6,0°C | **Direvisi** — 2,0 – 4,0°C | Pedoman chiller HACCP, batas atas umum "zona bahaya" di 5°C |

**Pernyataan keterbatasan yang jujur (wajib dicantumkan di proposal):**
Kolom `massa_kg` dan `toleransi_menit` pada `cargo_profiles.yaml` **bukan** hasil kutipan dari
dokumen standar resmi manapun. Tidak ada regulasi yang menyatakan durasi toleransi eksursi suhu
secara eksplisit dengan angka tunggal — nilai tersebut sangat bervariasi tergantung produk,
formulasi, dan riwayat suhu sebelumnya (konsep "cumulative excursion" yang lebih kompleks dari
sekadar durasi tunggal). Kedua kolom ini ditetapkan sebagai **asumsi desain simulasi yang
konservatif**, semata-mata untuk keperluan pembuatan label Time-to-Breach pada data sintetik kami
— bukan representasi ambang toleransi resmi dari produk tertentu.

## Riwayat Perbaikan Bug (Kolaborasi dengan R2)

Tiga bug ditemukan R2 (AI Model Engineer) saat menyiapkan pipeline training, dilacak dan
diperbaiki di sumbernya (simulator). Detail teknis lengkap ada di `ml/simulator/README.md`;
ringkasan di sini untuk konteks metodologi proposal:

- **Bug 1** (`time_to_breach` konstan per trip) dan **Bug 2** (muatan berat nyaris tidak pernah
  breach karena kalibrasi massa) — diperbaiki di versi `v2`/`v3`.
- **Bug 3** (`is_anomaly`/`failure_mode` konstan per trip, menyebabkan 48,3% jendela training
  60-menit salah label pada tiga mode yang terukur) — diperbaiki di versi `v4`, diverifikasi turun
  menjadi 0,00% salah label dengan metodologi pengukuran yang sama.

Proses ini didokumentasikan apa adanya karena menunjukkan siklus validasi silang yang nyata antar
peran tim (R1 membangun, R2 menguji di jalur konsumsi berbeda, R1 memperbaiki di sumbernya) —
bukan disembunyikan sebagai kelemahan.

## Validasi Sim-to-Real (Playbook Bagian 2.3 Langkah 9)

Dilakukan dua uji untuk mengukur kemiripan data sintetik terhadap dataset IoT publik (#1,
Temperature Readings: IoT Devices), khusus pada trip kondisi sehat.

**Uji Kolmogorov–Smirnov**: KS statistic = 1,0000 (p-value ≈ 0). Ini **bukan indikasi masalah**
— dua distribusi memang tidak tumpang tindih karena konteksnya berbeda: data real mengukur suhu
ruangan tanpa pendingin aktif (21–51°C), sedangkan data sintetik mengukur suhu kargo yang dijaga
aktif oleh reefer (2–8°C). KS test pada nilai mentah tidak relevan untuk dua sistem dengan rentang
operasi yang secara desain memang berbeda; yang lebih bermakna adalah kemiripan **pola**, bukan
**nilai**, sehingga digunakan uji ACF sebagai pembanding utama.

**Uji Autocorrelation Function (ACF)**, dibandingkan pada lag 1–60 menit:

| Lag (menit) | ACF Real | ACF Sintetik |
|---|---|---|
| 1 | 0,970 | 0,999 |
| 10 | 0,872 | 0,985 |
| 30 | 0,740 | 0,956 |
| 60 | 0,575 | 0,912 |

**Kesamaan**: Kedua kurva menurun secara mulus dari ~1,0 tanpa lonjakan atau penurunan drastis
mendadak — menunjukkan struktur "memori termal" yang secara kualitatif konsisten dengan hukum
fisika perpindahan panas pada kedua data.

**Perbedaan yang diakui secara jujur**: Data sintetik kami menurun jauh lebih lambat (ACF masih
0,912 di lag 60) dibanding data real (0,575) — artinya suhu kargo sintetik kami secara kuantitatif
lebih stabil/dapat diprediksi dibanding suhu ruangan pada data pembanding. Ini sebagian dapat
dijelaskan secara fisika: data real mengukur ruangan pasif tanpa kontrol suhu aktif, sedangkan
data sintetik mensimulasikan sistem dengan reefer yang secara aktif menjaga suhu tetap di
setpoint — sistem teregulasi aktif secara wajar lebih stabil dibanding ruangan tanpa regulasi.
Namun kami juga mengakui kemungkinan kontribusi dari parameter noise simulator (`σ=0,05°C`) yang
mungkin lebih kecil dibanding variabilitas sensor sungguhan, sehingga data kami cenderung "terlalu
bersih". Peningkatan noise model pada iterasi berikutnya adalah salah satu perbaikan yang
diidentifikasi, dan kami memilih untuk melaporkan temuan ini apa adanya alih-alih menyembunyikan
keterbatasan yang ditemukan saat validasi.

## Catatan Umum untuk Pembaca

- Seluruh dataset di atas **tidak digunakan mentah**. Perannya adalah pretraining, kalibrasi, dan
  validasi — bukan menjadi data pelatihan utama untuk fitur inti (Time-to-Breach). Data pelatihan
  utama dihasilkan melalui simulator fisika kami sendiri, karena label ground-truth untuk
  kegagalan cold chain tidak tersedia secara publik (lihat Bagian 2.2 Playbook Teknis).
- Satuan dan skala tiap dataset diverifikasi secara terpisah sebelum digabungkan (contoh: dataset
  NAB dalam Fahrenheit, dikonversi ke Celsius) untuk menghindari kesalahan penggabungan data.
