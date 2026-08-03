# Feature Schema — ColdTrack AI

Dokumen ini adalah kontrak skema fitur antara R1 (AI Data Engineer) dan R2 (AI Model Engineer).
Skema ini dibekukan sesuai target Playbook Teknis (titik serah terima hari ke-4) dan tidak diubah
sepihak setelah R2 mulai membangun pipeline training. Perubahan harus disepakati bersama.

Input model: jendela geser 60 langkah (60 menit, interval 1 menit) x 12 fitur berikut.

---

## Daftar Kolom

| # | Nama Kolom | Tipe | Satuan / Rentang | Deskripsi |
|---|---|---|---|---|
| 1 | `temp_c` | float | °C | Suhu kargo aktual, dibaca langsung dari sensor |
| 2 | `delta_temp` | float | °C/menit | Laju perubahan suhu terhadap langkah sebelumnya |
| 3 | `ambient_c` | float | °C | Suhu udara ambien di sekitar kendaraan |
| 4 | `delta_ambient` | float | °C | Selisih suhu kargo terhadap suhu ambien |
| 5 | `solar_radiation` | float | W/m² | Radiasi matahari pada koordinat & waktu saat itu |
| 6 | `humidity` | float | % (0-100) | Kelembapan relatif di dalam ruang kargo |
| 7 | `door_open` | int | 0 / 1 | Status pintu kargo (1 = terbuka) |
| 8 | `reefer_on` | int | 0 / 1 | Status unit pendingin (1 = menyala) |
| 9 | `reefer_duration_min` | float | menit | Durasi reefer menyala tanpa jeda hingga langkah ini |
| 10 | `speed_kmh` | float | km/h | Kecepatan kendaraan saat ini |
| 11 | `harsh_events` | int | jumlah kejadian | Jumlah event mengemudi kasar (rem/belok mendadak) dalam window |
| 12 | `hour_of_day` | int | 0-23 | Jam dalam hari, untuk menangkap pola diurnal |

---

## Aturan Turunan (Derived Feature Rules)

- `delta_temp[t] = temp_c[t] - temp_c[t-1]`
- `delta_ambient[t] = temp_c[t] - ambient_c[t]`
- `reefer_duration_min` di-reset ke 0 setiap kali `reefer_on` berubah dari 0 ke 1, lalu bertambah
  1 setiap langkah selama `reefer_on = 1` berturut-turut.
- `harsh_events` dihitung sebagai jumlah kejadian percepatan/pengereman/belokan yang melewati
  ambang batas dalam window 60 langkah (ambang batas mengikuti referensi statistik dari
  UAH-DriveSet, lihat `dataset_card.md`).

## Kolom Terlarang sebagai Fitur Input

Sesuai catatan "jebakan klasik" di Playbook Teknis Bagian 2.3 Langkah 6 — kolom berikut adalah
**target/label**, bukan fitur input, dan tidak boleh pernah muncul di sisi X model:

- `is_anomaly`
- `failure_mode`
- `time_to_breach`
- Nilai suhu masa depan dalam bentuk apa pun

Sebuah tes otomatis wajib memeriksa nama-nama kolom fitur terhadap daftar terlarang ini sebelum
data masuk ke pipeline training (lihat Playbook Teknis Bagian 2.3 Langkah 6).

## Referensi Sumber Insight

Setiap kolom di atas dapat ditelusuri ke insight dari proses EDA 7 dataset publik. Detail lengkap
ada di `dataset_card.md`. Ringkasan keterkaitan:

- `ambient_c`, `solar_radiation` → NASA POWER API
- `temp_c`, `delta_temp` (pola dasar) → IoT Temperature Readings, Intel Lab Data
- `speed_kmh` (kaitan dengan kemacetan/anomali suhu) → Taxi Trajectory Porto
- `harsh_events` → UAH-DriveSet
- `hour_of_day` → IoT Temperature Readings, NASA POWER API (keduanya menunjukkan pola diurnal kuat)

---

*Status: draft — menunggu review bersama tim sebelum dibekukan resmi di hari ke-4 (6 Agustus 2026).*
