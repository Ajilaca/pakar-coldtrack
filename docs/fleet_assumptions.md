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
- **Lead time** = `breach_at − detected_at`.

## Operasional

| Hal | Nilai | Alasan |
|---|---|---|
| Riwayat engine per truk | 240 menit (`fleet.history_cap_min`) | Mesin fisika butuh riwayat; dibatasi agar siklus tetap cepat |
| Celah yang diisi nilai terakhir | ≤ 5 menit (`fleet.ffill_maks_menit`) | Celah lebih besar → `DATA_TIDAK_LENGKAP` |
| Truk dianggap tanpa data | ≥ 10 menit tanpa bacaan (`fleet.offline_setelah_menit`) | Status `TIDAK_ADA_DATA`, tidak pernah AMAN |
| Kompresi / retensi TimescaleDB | kompresi > 7 hari, retensi 180 hari | Belum ada kebijakan retensi dari mitra |
| Agregat riwayat | 15 menit, disegarkan tiap 15 menit untuk 1 hari terakhir | Cukup untuk grafik riwayat |
