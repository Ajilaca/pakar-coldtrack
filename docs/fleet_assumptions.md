# Asumsi armada ColdTrack AI

Semua nilai di sini adalah **[ASUMSI]**: dipakai agar sistem armada bisa dijalankan dan diuji, bukan
fakta lapangan. `docs/PROPOSAL.md` melarang angka kerugian dikarang tanpa tanda; setiap angka di
dashboard yang bergantung pada asumsi ini harus bisa ditelusuri ke berkas ini. Ganti dengan nilai dari
mitra saat pilot (Fase 7).

## Data armada demo (`ml/preprocess/export_fleet.py` → `backend/data/fleet/`)

| Hal | Nilai | Alasan |
|---|---|---|
| Sumber telemetri | 24 trip dari **split val** dataset v4 (14 A0, 10 anomali, setiap mode A1–A8 ada) | Data latih memamerkan model secara tidak jujur; split test disisihkan untuk evaluasi |
| Lokasi depo | 6 hub di Jawa, koordinat pusat kota (Jakarta, Bandung, Cirebon, Semarang, Yogyakarta, Surabaya) | Bukan alamat depo nyata; hanya untuk peta |
| Rute | Garis lurus antar hub + jitter kecil, satu titik per menit | v4 tidak punya lat/lon; model tidak memakai lokasi |
| Nomor polisi | Dibangkitkan acak dengan awalan wilayah depo | Bukan kendaraan nyata |
| Massa muatan | Acak dari 600 / 800 / 1.000 / 1.200 / 1.500 kg | v4 tidak punya massa |
| Perangkat | Firmware 1.4.2 (≈30 %) vs terbaru 1.5.0; gateway 0.8.7 (≈15 %) vs 0.9.3; tanggal kalibrasi 10–400 hari lalu; offset kalibrasi N(0; 0,25 °C); baterai 2,35–3,1 V | Untuk menghidupkan panel "Perlu diperbarui"; semua `"sumber": "sintetik"` |

## Nilai muatan dan kerugian (`backend/config.yaml: fleet.harga_per_kg_idr`)

| Profil muatan | Harga per kg (IDR) | Catatan |
|---|---|---|
| `vaksin_2_8C` | 2.500.000 | Ilustratif. Nilai vaksin sangat bervariasi per produk; tidak ada sumber harga yang dipakai |
| `daging_beku_-18C` | 140.000 | Ilustratif, orde besaran harga eceran daging beku |
| `buah_segar_2_4C` | 30.000 | Ilustratif |
| `ikan_segar_0_5C` | 60.000 | Ilustratif |
| `produk_susu_2_4C` | 25.000 | Ilustratif |

Nilai muatan trip = massa × harga per kg. Rumus kerugian (Fase 3, `app/fleet/loss.py`, mengikuti
rencana armada):

- **Nilai berisiko** = nilai muatan × `risk_index` (indeks risiko mesin fisika, bukan probabilitas
  kerusakan terkalibrasi).
- **Kerugian terjadi** = nilai muatan penuh bila breach (suhu muatan taksiran melewati batas profil).
  Ini batas atas: dalam praktik sebagian muatan mungkin masih dapat diselamatkan.
- **Kerugian berhasil diatasi** = nilai muatan insiden yang SELESAI sebelum breach, atau kembali AMAN
  tanpa breach. Tidak membuktikan bahwa tindakan operator yang mencegahnya.
- **Lead time** (definisi frame Figma Kerugian, 11 Oktober 2026):
  - Insiden dengan breach: `breach_at − detected_at`. Nilai 0 berarti terdeteksi saat sudah melewati batas.
  - Insiden tanpa breach: TTB mesin fisika saat terdeteksi (`incidents.ttb_terdeteksi_min`, yaitu perkiraan breach − deteksi).
  - Insiden yang TTB-nya di atas batas tampil (tidak ada perkiraan breach) tidak punya lead time.
  - Insiden sebelum migrasi 005 juga tidak punya lead time.

## Operasional

| Hal | Nilai | Alasan |
|---|---|---|
| Riwayat engine per truk | 240 menit (`fleet.history_cap_min`) | Mesin fisika butuh riwayat; dibatasi agar siklus tetap cepat |
| Celah yang diisi nilai terakhir | ≤ 5 menit (`fleet.ffill_maks_menit`) | Celah lebih besar → `DATA_TIDAK_LENGKAP` |
| Truk dianggap tanpa data | ≥ 10 menit tanpa bacaan (`fleet.offline_setelah_menit`) | Status `TIDAK_ADA_DATA`, tidak pernah AMAN |
| Kompresi / retensi TimescaleDB | kompresi > 7 hari, retensi 180 hari | Belum ada kebijakan retensi dari mitra |
| Agregat riwayat | 15 menit, disegarkan tiap 15 menit untuk 1 hari terakhir | Cukup untuk grafik riwayat |
| Zona waktu fitur model | `Asia/Jakarta` (`fleet.zona_waktu`) | ts disimpan UTC, tetapi `hour_of_day` dilatih dengan jam lokal (simulator latih, skenario demo WIB). Worker mengonversi sebelum fitur dihitung |
| Debounce worker-infer | 2 detik dinding (`fleet.infer_debounce_detik`) | Batch dari buffer perangkat cukup dihitung sekali |

## Inferensi streaming (Fase 3) — pilihan desain

| Hal | Pilihan | Tag | Alasan |
|---|---|---|---|
| `DATA_TIDAK_LENGKAP` | Hanya menggantikan AMAN; WASPADA/KRITIS tetap tampil | [DESAIN] | Data berlubang tidak boleh tampil AMAN, tetapi peringatan tidak boleh tertutup catatan kualitas data |
| Jenis insiden | `kondisi` (WASPADA/KRITIS, punya nilai kerugian) dan `data` (TIDAK_ADA_DATA, tanpa nilai), satu terbuka per (truk, jenis, trip) | [DESAIN] | Tanpa pemisahan, putus data "tereskalasi" jadi insiden kondisi dengan `detected_at`/lead time yang salah, dan insiden trip lama menelan episode trip baru (terlihat saat uji Docker 2026-10-11) |
| Pembuka insiden | Awal episode saja; `MENUNGGU_DATA` dan `DATA_TIDAK_LENGKAP` tidak membuka insiden | [DESAIN] | Putus sinyal pendek tidak membanjiri kotak masuk |
| Notifikasi insiden data | Hanya saat pertama terputus | [DESAIN] | Putus sinyal berulang menimbulkan banyak notifikasi tanpa informasi baru |
| Kesehatan sensor v0 | Skor 0–100 dari penalti (`app/models/sensor_health_rules.py`); grade Sehat ≥ 80, Perlu cek ≥ 50, Ganti < 50 | [DESAIN] | Bobot belum dikalibrasi terhadap kerusakan nyata. Pada seed, ke-14 truk A0 bernilai Sehat (tes). Derau diukur dengan selisih orde-2 karena suhu seed terkuantisasi 0,1 °C (MAD = 0) |
| Data terlambat | Prediksi dihitung ulang hanya untuk menit terakhir | [DESAIN] | Prediksi menit lampau tidak ditulis ulang |
| Notifikasi sensor | Saat grade kesehatan sensor BARU turun ke "Ganti" (level waspada) | [DESAIN] | Frame "Ringkasan + notifikasi"; tidak diulang selama grade tetap Ganti |
| Notifikasi pemulihan | Level `ok` (ikon hijau) saat insiden kondisi kembali AMAN tanpa breach | [DESAIN] | Frame "Ringkasan + notifikasi" |

### Temuan: alarm pada truk normal

Pada uji Docker (3 jam waktu simulasi, 24 truk), 8 dari 14 truk yang trip asalnya A0 (normal) membuka
insiden kondisi. Penyebabnya mesin fisika, bukan worker:
- Mesin yang sama dijalankan offline pada data seed memberi status non-AMAN yang panjang pada trip A0.
  Contoh: D 2605 RV, `produk_susu_2_4C`, 350 menit WASPADA dan 44 menit KRITIS. Truk ini berjalan di
  3,0–3,7 °C, dekat batas atas profil 2–4 °C.
- Ini konsisten dengan angka eval: `healthy_alert_rate` = 0,199 per menit pada trip A0
  (`eval/results/iter2_results.json`; sapuan margin 0,131–0,331 di `margin_sweep_iter2.json`).
- Di dasbor armada, angka itu terlihat sebagai insiden pada hampir setiap trip normal berprofil sempit.
- Ambang mesin tidak diubah di Fase 3. Perubahannya harus diputuskan dan divalidasi ulang di split val
  (lihat `docs/model_card.md` §6: ambang condong ke sisi waspada).

**Tindak lanjut (11 Oktober 2026):**
- **Sapuan val.** Margin peringatan "suhu mendekati batas" disapu di split **val**
  (`eval/margin_sweep_val.py`, `eval/results/margin_sweep_val.json`).
  - Kriteria yang ditetapkan sebelum hasil dilihat mengusulkan 0,20.
  - User memilih **0,25** sebagai kompromi.
- **Dampak di val, dibanding 0,35:**

  | Metrik | 0,35 | 0,25 |
  |---|---|---|
  | Alarm palsu per menit trip normal | 24,3% | 17,6% |
  | Breach terlewat | 0/20 | 0/20 |
  | Jendela TTB ≤ 30 mnt tampil AMAN | 0% | 0,4% |
  | Lead time median | 84 mnt | 37,5 mnt |
  | Episode alarm per jam | 0,36 | 0,39 |

  Profil 2–4 °C tetap paling sering beralarm (±40–47% menit). Sisa alarm juga datang dari aturan TTB ≤ 60
  menit (±6% menit normal), yang tidak terpengaruh margin.
- **Asal nilai lama.** Margin 0,35 dulu dipilih dari sapuan split **test** (`margin_sweep_iter2.json`).

### Catatan simulator

Simulator memutar ulang trip seed dengan ts = jam bersama. Jam asli trip v4 tidak dipertahankan, sehingga
pola harian di data (mis. suhu luar) tidak selalu cocok dengan `hour_of_day` yang dilihat model.
