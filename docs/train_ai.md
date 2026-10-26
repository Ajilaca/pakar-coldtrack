# Data dan fisika untuk melatih model AI

Dokumen ini menjelaskan dari mana data latih ColdTrack AI berasal, rumus fisika yang membangunnya, dan
bagaimana mesin fisika (`backend/app/core/`) dipakai bersama model. Semua data adalah sintetis. Tidak ada
data logger truk sungguhan.

## Ringkasan

- Model dilatih dari nol pada **dataset v4**: 700 trip hasil simulator fisika, 251.073 baris per menit
  (`data/processed/v4_seed1000_700trips.parquet`, seed 1000).
- Dataset publik membentuk simulator, tetapi tidak ada baris data nyata yang masuk ke data latih. NASA POWER
  memberi kurva iklim, Intel Berkeley memberi parameter kegagalan sensor, dan UAH-DriveSet memberi statistik
  mengemudi. Data IoT India sempat dipakai untuk prapelatihan, lalu ditinggalkan karena tidak membantu
  (model_card.md, Ablation B). Daftar lengkapnya di bagian 8.
- Label (mode kegagalan, Time-to-Breach) tidak tersedia di data publik mana pun, jadi dibuat dari simulator.
- Di backend, status AMAN/WASPADA/KRITIS dan TTB yang ditampilkan datang dari **mesin fisika**, bukan dari model.
  Model hanya memberi forecast suhu dan diagnosis penyebab.

## 1. Dataset yang dipakai

| Berkas | Isi |
|---|---|
| `data/processed/v4_seed1000_700trips.parquet` | 700 trip, 251.073 baris, 23 kolom, dibagi per trip menjadi train/val/test |
| `data/processed/windows/windows_{train,val,test}.npz` | Jendela 60 menit x 12 fitur: 77.703 (train), 16.414 (val), 16.244 (test) |
| `data/processed/windows/b8_{train,val}.npz` | Label v5 dan fitur konteks trip (lihat bagian 5) |

| | Train | Val | Test |
|---|---|---|---|
| Trip | 489 | 105 | 106 |
| Trip sehat (A0) | 284 | 62 | 65 |
| Trip dengan satu mode gangguan | 205 | 43 | 41 |

Lima jenis muatan: daging beku (148 trip), vaksin 2 sampai 8 °C (144), ikan segar (143), sayur dan buah (142),
produk susu (123). Durasi trip 240 sampai 479 menit (median 357). Sekitar 1,9% bacaan suhu hilang (NaN).
Split dilakukan per trip, bukan per jendela, supaya jendela dari trip yang sama tidak bocor ke split lain.
Split test dipakai satu kali per model dan setiap pemakaiannya dicatat di
`bench/results/test_access_log.json`.

Versi lama (v1 sampai v3) tetap ada di folder yang sama untuk keterlacakan. v4 adalah yang dipakai
`ml/`, `bench/`, `hw/`, dan model produksi.

## 2. Simulator fisika

Simulator (`ml/simulator/02_simulator_fixed_v4.ipynb`) menghitung suhu muatan tiap menit dengan persamaan
pendinginan Newton:

```
C dT/dt = - k_cool * u * (T - T_set)         pendingin reefer, u = kapasitas 0..1
          + k_leak * (T_amb - T)             kebocoran panas lewat dinding
          + k_door * pintu * (T_amb - T)     pertukaran udara saat pintu terbuka
          + k_solar * radiasi                beban matahari
          + derau N(0, 0,05 °C)
```

dengan `C = massa x kalor jenis muatan`, `k_leak = 0,5`, `k_door = 8,0`, `k_solar = 0,05`, `k_cool = 50`.

Masukan lingkungan:

- **Suhu ambien dan radiasi matahari** mengikuti pola harian yang dikalibrasi dari NASA POWER untuk Jakarta
  (`T2M`, `ALLSKY_SFC_SW_DWN`). Rentang suhu luar di dataset 26 sampai 31 °C.
- **Profil muatan** (`backend/config.yaml`, `cargo_profiles`) memberi rentang suhu aman, kalor jenis, dan massa.
  Rentang suhu sudah dicek terhadap WHO, Peraturan BPOM No. 6/2020, Codex Alimentarius, SNI, dan pedoman HACCP
  (tabel di bagian 6).
- **Sensor** diberi derau dan kegagalan. Bacaan suhu yang hilang (NaN) muncul acak. `temp_true_c` menyimpan suhu
  asli untuk label dan evaluasi. Kolom itu tidak pernah dipakai sebagai fitur.

### Sembilan kode kondisi

| Kode | Yang disuntikkan simulator | Kelas model |
|---|---|---|
| A0 | Tidak ada gangguan | `A0` |
| A1 | Pintu terbuka 20 menit sejak onset | `A1` |
| A2 | Kapasitas pendingin turun linear 1 ke 0,15 selama 120 menit lalu tetap (kompresor aus) | `degradasi_bertahap` |
| A3 | Pendingin mati total sejak onset | `A3` |
| A4 | Koefisien pendinginan x 0,6 sejak onset | `degradasi_bertahap` |
| A5 | Sensor macet: suhu terbaca beku di nilai saat onset | `masalah_sensor` |
| A6 | Sensor error: 5 lonjakan acak dan celah data | `masalah_sensor` |
| A7 | Kejut ambien: radiasi x 3 dan kecepatan 0 selama 30 menit (macet) | `A7` |
| A8 | Muatan masuk lebih hangat: suhu awal = batas atas + 2 °C | `A8` |

Label `time_to_breach` dihitung per menit: selisih menit sampai suhu muatan sebenarnya (`temp_true_c`) melewati
batas. Ketiga label (`is_anomaly`, `failure_mode`, `time_to_breach`) berasal dari satu sumber yang sama di
simulator, jadi tidak bisa saling bertentangan.

## 3. Fitur model

Model menerima jendela 60 menit x 12 fitur, nilai mentah (normalisasi ada di dalam graf ONNX).

| # | Kolom | Satuan | Keterangan |
|---|---|---|---|
| 1 | `temp_c` | °C | Suhu dari sensor |
| 2 | `delta_temp` | °C/menit | `temp_c[t] - temp_c[t-1]` |
| 3 | `ambient_c` | °C | Suhu udara luar |
| 4 | `delta_ambient` | °C | `temp_c[t] - ambient_c[t]` |
| 5 | `solar_radiation` | W/m² | Radiasi matahari |
| 6 | `humidity` | % | Kelembapan relatif |
| 7 | `door_open` | 0/1 | Pintu terbuka |
| 8 | `reefer_on` | 0/1 | Pendingin menyala |
| 9 | `reefer_duration_min` | menit | Lama pendingin menyala berturut-turut, dihitung dari awal jendela |
| 10 | `speed_kmh` | km/jam | Kecepatan kendaraan |
| 11 | `harsh_events` | jumlah | Kejadian rem atau belok mendadak (referensi statistik UAH-DriveSet) |
| 12 | `hour_of_day` | 0 sampai 23 | Jam lokal armada (Asia/Jakarta); timestamp disimpan UTC |

Kolom `is_anomaly`, `failure_mode`, `time_to_breach`, `temp_true_c`, dan suhu masa depan tidak boleh muncul
sebagai fitur. Tes `ml/tests/test_data_contract.py` dan `backend/app/preprocess.py` memeriksanya.

Sejak v5, model menerima masukan kedua `konteks` (6 fitur dari riwayat suhu sejak awal trip). Isinya ada di bagian 5.

## 4. Mesin fisika

Kode di `backend/app/core/`. Rumus yang sama dipakai di simulator, di backend, dan di chip (`hw/rtl/physics.sv`).

**Penaksir suhu muatan** (`observer.py`). Sensor membaca udara kabin, sedangkan yang harus dijaga adalah muatan.
Muatan mengikuti kabin dengan kelambanan:

```
UA = h * A,   A = 6 * (m / rho)^(2/3)     h = 8 W/m²K, rho = 500 kg/m³
k  = UA / (m * c)  per menit              (maksimum 1)
Tc[t] = Tc[t-1] + k * (T_sensor[t-1] - Tc[t-1])
```

**Time-to-Breach** (`engine.py`, `door_budget.py`). Bila kabin bertahan di suhu `Tcab`, muatan menuju `Tcab`
secara eksponensial dan menyentuh batas atas `T_hi` setelah:

```
TTB = - ln( (T_hi - Tcab) / (Tc - Tcab) ) / k          (0 bila Tc >= T_hi, 240 bila Tcab <= T_hi)
```

`Tcab` adalah rata-rata sensor 10 menit terakhir. Saat pintu terbuka, atau kendaraan berhenti dan suhu naik,
`Tcab = max(rata-rata 10 menit, suhu luar)`. Untuk hanyut pelan (kompresor melemah), TTB juga dibatasi proyeksi
kenaikan sensor 20 menit terakhir.

**Anggaran pintu** (`door_budget.py`). Saat pintu terbuka, dihitung sisa menit sampai muatan melewati batas pada
kasus terburuk (kabin sama dengan suhu luar), dan suhu puncak muatan bila pintu ditutup sekarang. Simulasi
maju memakai model dua-massa: udara kabin dan muatan.

**Status** (`engine.py`, ambang di `CFG`):

| Status | Pemicu |
|---|---|
| KRITIS | Suhu muatan di luar batas, atau TTB <= 30 menit |
| WASPADA | TTB <= 60 menit; sensor atau muatan kurang dari 0,25 x lebar rentang dari batas atas (maks. 1 K); pintu terbuka dan sisa waktu terburuk <= 30 menit; sensor mencurigakan atau rusak |
| AMAN | Selain itu |

**Aturan sensor** (`sensor_rules.py`): rentang, lompatan, garis datar, dan baterai. Sensor yang bermasalah tidak
boleh membuat status AMAN, dan tidak boleh memicu KRITIS dari angkanya sendiri.

**Aturan diagnosis** (`inference.aturan_diagnosis`). Dua kelas tidak diserahkan ke model karena model hanya
mengenalinya dari satu sinyal bersih simulator (bagian 7): `prapendinginan_buruk` bila suhu awal muat di atas
batas atas profil, dan `reefer_mati_total` bila reefer melapor mati 15 menit atau lebih dan suhu naik 0,5 °C
atau lebih sejak mati.

### Pembagian peran

| Keputusan | Sumber |
|---|---|
| Status AMAN/WASPADA/KRITIS | Mesin fisika |
| TTB yang ditampilkan | Mesin fisika |
| Masalah sensor | Aturan sensor |
| A3 dan A8 | Aturan diagnosis |
| Forecast suhu t+15/30/60 menit | GRU |
| Diagnosis A1, A7, degradasi bertahap | GRU |
| TTB model (informasi saja) | XGBoost |

## 5. Label v5 dan konteks trip

Di dataset v4, A1 (20 menit) dan A7 (30 menit) adalah kejadian sementara, tetapi `failure_mode` bertahan sampai
akhir trip. Sekitar 58% jendela A1 dan 51% jendela A7 di val tidak memuat jejak kejadiannya sama sekali, sehingga
tidak ada model yang bisa mengenalinya. Label v5 memberi kelas itu hanya selama kejadian masih ada di jendela atau
suhu belum pulih (maksimum 120 menit), sesudahnya A0. Definisi ada di `bench/experiments/b8/b8_lib.py`.
Ini mengubah definisi label, jadi metrik v5 tidak sebanding langsung dengan metrik label lama dan keduanya
dilaporkan berdampingan.

Konteks trip: menit trip, suhu awal muat, suhu sekarang dikurangi suhu awal, tren 240 menit, rata-rata 240 dikurangi
rata-rata 60 menit, dan kemiringan 240 menit. Semuanya kausal dari `temp_c`.

## 6. Verifikasi profil muatan

Nilai awal `cargo_profiles` dicek ulang terhadap standar resmi. Rentang suhu sebagian besar sudah akurat, dengan
empat koreksi.

| Profil | Rentang akhir | Sumber |
|---|---|---|
| Vaksin | 2,0 sampai 8,0 °C | WHO; Peraturan BPOM No. 6/2020 tentang CDOB |
| Daging beku | -25,0 sampai -18,0 °C | Codex Alimentarius CAC/RCP 1-1969, USDA, FAO |
| Ikan segar | 0,0 sampai 5,0 °C | SNI 01-2696.3-2006 |
| Sayur dan buah | 2,0 sampai 4,0 °C | Pedoman chiller HACCP |
| Produk susu | 2,0 sampai 4,0 °C | Pedoman chiller HACCP |

**Keterbatasan:** kolom massa muatan dan toleransi menit bukan kutipan dari standar mana pun. Tidak ada regulasi yang
memberi satu angka durasi toleransi, karena nilainya bergantung pada produk dan riwayat suhunya. Keduanya adalah
asumsi desain yang konservatif, dipakai hanya untuk membuat label TTB pada data sintetis.

## 7. Keterbatasan yang sudah diukur

- **Semua data sintetis.** Skor test hanya mengukur generalisasi ke trip simulator lain, bukan ke truk sungguhan.
  Model sensor berbasis data Berkeley (data nyata) tidak lolos gerbang G4.
- **Jalan pintas (B12).** Satu sinyal diubah di val, lalu dilihat F1 per kelas. A3 hanya dikenali dari `reefer_on`
  (1,00 turun ke 0,00 bila flag dipaksa nyala), A1 dari `door_open` (0,91 turun ke 0,00), A8 dari suhu awal muat
  (1,00 turun ke 0,32), dan `masalah_sensor` dari suhu yang datar sempurna (0,85 turun ke 0,19 dengan derau 0,1 °C).
  Penyebabnya aturan simulator yang kaku: trip A8 selalu mulai di batas atas + 2 °C, dan derau sensor hanya 0,05 °C.
- **Augmentasi (B13).** Melatih ulang dengan flag reefer palsu, sensor pintu hilang, suhu awal digeser, dan derau
  suhu menaikkan A1 saat sensor pintu mati dari 0,00 ke 0,78 dan A8 tanpa suhu awal dari 0,32 ke 0,84, dengan
  biaya Macro F1 val 0,875 menjadi 0,856. A3 saat flag palsu hanya naik ke 0,30, karena suhu muatan naik sekitar
  0,4 °C per jam setelah reefer mati. Sinyal yang tepat untuk kasus ini adalah arus atau kopling kompresor.
- **Sim-to-real.** Autokorelasi suhu sintetis lebih tinggi dari data IoT pembanding (0,912 lawan 0,575 di lag 60
  menit). Sebagian karena reefer menjaga suhu aktif, sebagian karena derau simulator lebih kecil dari sensor
  sungguhan. Uji Kolmogorov-Smirnov tidak bermakna di sini karena rentang suhu kedua sistem memang berbeda.
- **Bug label yang sudah diperbaiki.** TTB konstan per trip dan massa muatan berat yang tidak pernah breach
  (v2/v3), serta `failure_mode` konstan per trip yang membuat 48,3% jendela salah label (v4, kini 0,00%).

## 8. Dataset publik

Tujuh dataset publik dianalisis (EDA). Tabel di bawah menunjukkan apa yang akhirnya dipakai dan untuk apa.
Tidak ada yang dimasukkan mentah ke data latih model produksi.

| Dataset | Sumber | Status | Dipakai untuk |
|---|---|---|---|
| NASA POWER (`T2M`, `ALLSKY_SFC_SW_DWN`) | power.larc.nasa.gov | **Dipakai** | Kurva suhu luar dan radiasi matahari Jakarta di simulator, sehingga datanya terasa Indonesia. Rentang suhu sampel 26 sampai 31,3 °C, radiasi 0 di malam hari |
| Intel Berkeley Lab (2,3 juta baris, 54 sensor) | db.csail.mit.edu/labdata | **Dipakai** | Parameter kegagalan sensor di simulator (derau sehat, nilai macet ekstrem 122,15 °C, jumlah peralihan median) untuk A5 dan A6. Juga dipakai melatih model kesehatan sensor eksperimen (`ml/sensor_health/`), yang tidak lolos gerbang G4. 17,7% bacaan adalah outlier ekstrem |
| UAH-DriveSet (1 pengemudi, 7 rute) | robesafe.uah.es | **Dipakai** sebagai referensi | Statistik rem dan belok keras untuk parameter `harsh_events`. Lisensi akademik, tidak boleh didistribusikan ulang, wajib disitasi (Romera et al., ITSC 2016) |
| Temperature Readings: IoT Devices (97.606 baris, India) | Kaggle (atulanandjha), LGPL 3.0 | **Sempat dipakai**, lalu ditinggalkan | Prapelatihan backbone GRU pada data outdoor. Hasilnya tidak membantu (loss latih lebih rendah tetapi loss validasi lebih tinggi), jadi model produksi dilatih dari nol. Sekarang hanya untuk uji sim-to-real (bagian 7) |
| NAB realKnownCause | Kaggle (boltzmannbrain/nab) | Referensi | Set uji eksternal anomali suhu nyata; nilai Fahrenheit dikonversi ke Celsius. Tidak masuk pipeline latih |
| Smart Manufacturing IoT-Cloud (100.000 baris) | Kaggle (ziya07), CC0-1.0 | Referensi | Pembanding struktur label. Rasio anomalinya 8,9%, jauh lebih timpang dari rancangan kami, dan label `failure_type` dibuat independen dari `anomaly_flag` |
| Taxi Trajectory Porto (1,7 juta trip) | Kaggle (crailtap) | Referensi | Gambaran pola berhenti dan jalan untuk generator rute. Trip berdurasi 0 detik dan 10,5 jam dibuang |

Catatan dari analisis:

- Data IoT berasal dari India (21 sampai 51 °C), jadi hanya mengajarkan bentuk kurva suhu, bukan nilai ambien
  Indonesia. Nilai itu datang dari NASA POWER.
- Interval pencatatan data IoT tidak konsisten (celah maksimum sekitar 11,5 hari), sehingga perlu dibuat ulang
  ke interval 1 menit sebelum dipakai.
- Outlier Berkeley tersebar acak di hampir semua sensor, tanda derau transmisi sesaat, bukan sensor yang mati
  permanen. Dua sensor (moteid 5 dan 57) hampir tidak pernah mengirim data.

## 9. Mengulang dari awal

```bash
python -m ml.training.finetune                    # latih GRU dari nol (sekitar 35 menit di CPU)
python -m bench.experiments.b8.b8_export_onnx     # ekspor v5 ke ONNX, uji paritas
python -m bench.experiments.b12.b12_shortcut      # uji ketergantungan pada satu sinyal
```

Angka lengkap dan perbandingan versi ada di [model_card.md](model_card.md). Hasil percobaan ada di
`bench/results/`.
