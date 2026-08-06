# Simulator Termal — ColdTrack AI

README ini menjelaskan isi notebook simulator (`simulator_dev.ipynb`) yang digunakan untuk
menghasilkan data sintetik cold chain. Dikerjakan oleh R1 (AI Data Engineer), mengacu pada
Playbook Teknis Bagian 2.3.

## Tujuan

Menghasilkan data suhu kargo yang realistis secara fisika, lengkap dengan label
(`is_anomaly`, `failure_mode`, `time_to_breach`), untuk melatih model prediksi Time-to-Breach.
Label ini tidak tersedia di data publik manapun (lihat `dataset_card.md`), sehingga dibangun
sendiri melalui simulasi berbasis persamaan pendinginan Newton.

## Struktur Notebook

1. **Setup** — import library (`numpy`, `pandas`, `matplotlib`, `scipy.stats`)
2. **Cargo Profiles** — dictionary `cargo_profiles`, berisi rentang suhu aman, massa, dan
   toleransi waktu tiap jenis muatan. Rentang suhu telah diverifikasi terhadap standar resmi
   (WHO, Peraturan BPOM No. 6/2020, Codex Alimentarius, SNI, HACCP) — detail dan sumber ada di
   `dataset_card.md`.
3. **Ambient & Solar Generator** — fungsi `generate_ambient_solar()`, menghasilkan suhu ambien
   dan radiasi matahari mengikuti pola siklus harian, dikalibrasi berdasarkan data NASA POWER
   untuk koordinat Jakarta.
4. **Model Termal Inti** — fungsi `simulate_trip_full()`, mesin utama simulator. Menjalankan
   persamaan pendinginan Newton per menit, dengan opsi menyuntikkan salah satu dari 9 kode
   anomali (A0–A8), lapisan realisme sensor, dan perhitungan label per-menit.
5. **Generator Dataset** — fungsi `generate_full_dataset()`, memanggil `simulate_trip_full()`
   berulang dengan variasi acak untuk menghasilkan ratusan trip sekaligus.

## Fungsi Utama: `simulate_trip_full()`

```python
simulate_trip_full(
    cargo_type,          # nama profil muatan, mis. 'vaksin_2_8C'
    n_steps=240,          # durasi trip dalam menit
    start_hour=6,          # jam berangkat (0-23), memengaruhi kurva ambient/solar
    anomaly_type=None,     # None (sehat) atau salah satu kode 'A1'-'A8'
    onset_minute=None,     # menit mulai anomali (wajib jika anomaly_type diisi, kecuali A8)
    seed=None               # untuk reproducibility
)
```

Mengembalikan `(df_trip, labels)`. `df_trip` adalah DataFrame per-menit berisi:
- 12 kolom fitur inti sesuai `feature_schema.md`
- `temp_true_c` — suhu asli/ground truth (tidak tersedia di dunia nyata, hanya untuk evaluasi
  dan perhitungan `time_to_breach`; **tidak boleh** dipakai sebagai fitur input model)
- `time_to_breach` — dihitung **per menit** (hitung mundur ke breach terdekat), bukan satu angka
  per trip
- `gps_jitter_m`, `timestamp_offset_sec` — metadata realisme sensor, belum resmi masuk 12 fitur
  inti (perlu didiskusikan dengan R2 sebelum dipakai sebagai input model)

## Status Kode Anomali (9 dari 9 tervalidasi)

| Kode | Nama | Cara kerja | Status |
|---|---|---|---|
| A0 | Sehat | Tidak ada gangguan | OK |
| A1 | Pintu terbuka terlalu lama | `door_open` aktif 20 menit | OK |
| A2 | Degradasi kompresor | `u[t]` meluruh 1,0->0,15 selama 2 jam | OK breach konsisten |
| A3 | Kegagalan reefer total | `u[t]` -> 0 mendadak | OK |
| A4 | Kebocoran refrigeran | `k_cool` berkurang 40% | OK (validasi via pelebaran variasi suhu, bukan breach cepat -- sesuai definisi) |
| A5 | Sensor macet (stuck-at) | `temp_c` dibekukan di satu nilai | OK |
| A6 | Sensor berderau / paket hilang | Lonjakan impuls acak + gap NaN | OK |
| A7 | Kejut suhu ambien | Kecepatan 0 + pengali radiasi matahari 3x | OK |
| A8 | Prapendinginan buruk | Suhu awal di atas batas atas | OK |

## Riwayat Perbaikan Bug (dilaporkan R2, AI Model Engineer)

Dua bug ditemukan R2 lewat `ml/tests/test_data_contract.py` saat menyiapkan pipeline training,
sebelum sempat dipakai untuk training model -- dilacak dan diperbaiki di sumbernya (simulator),
bukan hanya ditambal di sisi konsumen data.

**Bug 1 -- `time_to_breach` konstan per trip.** TTB sebelumnya dihitung sekali per pemanggilan
fungsi lalu disalin ke seluruh baris trip, sehingga tidak pernah menghitung mundur seperti
seharusnya. Diperbaiki dengan menghitung TTB untuk tiap menit secara vectorized
(`np.searchsorted` terhadap indeks breach terdekat).

**Bug 2 -- muatan berat nyaris tidak pernah breach.** `C_thermal = massa_kg * 3.5` membuat time
constant untuk daging beku (2000 kg) mencapai ~233 jam -- jauh melebihi durasi trip (4-8 jam),
sehingga breach rate mode A3 (reefer mati total) untuk daging beku adalah 0% dari seluruh
sampel, meski secara fisika seharusnya tetap breach diberi waktu cukup. Diperbaiki dengan
menyekalakan `C_thermal` memakai akar kuadrat massa (`1050 * sqrt(massa_kg/300)`), dikalibrasi
agar profil vaksin (300 kg, sudah tervalidasi sebelumnya) tidak berubah. Breach rate daging beku
naik dari 0% menjadi 16,7% pada mode A3, sementara profil lain tetap stabil.

Riwayat file data: `v1` (sebelum perbaikan bug) -> `v2` (bug diperbaiki) -> `v3` (bug diperbaiki +
lapisan realisme sensor ditambahkan). **`v3` adalah versi resmi terkini.**

## Catatan Kalibrasi

Konstanta fisika (`k_cool=50`, `k_leak=0.5`, `k_door=8.0`, `k_solar=0.05`) telah dikalibrasi
ulang dari nilai awal di Playbook Teknis (`k_cool=0.15` dkk) karena skala aslinya membuat noise
mendominasi efek fisika sehingga suhu "melayang" seperti random walk. Nilai saat ini menghasilkan
riak suhu ~0,9°C pada kondisi sehat, mendekati target playbook (±0,4°C).

## Lapisan Realisme Sensor (Playbook Langkah 7)

Diterapkan ke **seluruh** trip (bukan hanya kasus anomali), karena keterbatasan sensor murah di
dunia nyata selalu ada:
- Kuantisasi `temp_c` ke kelipatan 0,1°C
- Packet loss bursty: 1-3 kejadian per trip, masing-masing 2-5 menit (di luar trip mode A6, yang
  sudah punya gap sendiri) -- pola berkelompok, bukan acak seragam, mengikuti temuan EDA Intel Lab
  Data
- `gps_jitter_m` (±8 meter) dan `timestamp_offset_sec` (±10 detik) dicatat sebagai kolom
  tambahan untuk keperluan audit, belum resmi menjadi bagian dari 12 fitur input model

## Validasi Sim-to-Real

Uji Kolmogorov-Smirnov dan ACF terhadap dataset IoT Temp India telah dilakukan -- hasil dan
interpretasi lengkap ada di `dataset_card.md` bagian "Validasi Sim-to-Real". Ringkasnya: pola ACF
data sintetik dan real sama-sama menurun mulus (bentuk kualitatif konsisten), tetapi data sintetik
menurun lebih lambat (lebih autokorelatif/stabil) -- sebagian dapat dijelaskan karena data sintetik
mensimulasikan sistem dengan reefer aktif, sementara data pembanding adalah ruangan pasif tanpa
kontrol suhu. Kemungkinan noise simulator (`σ=0,05°C`) juga sedikit terlalu kecil dibanding
sensor sungguhan -- dicatat sebagai perbaikan potensial untuk iterasi berikutnya.

## Checklist Status (Playbook Bagian 2.3)

- [x] Lapisan realisme sensor untuk seluruh data (Langkah 7)
- [x] Randomisasi domain: 700 trip, variasi cargo/jam berangkat/durasi, 60% sehat / 40% anomali
      (Langkah 8)
- [x] Validasi sim-to-real: uji KS dan ACF terhadap dataset IoT publik (Langkah 9)
- [x] Pembagian data per `trip_id` (70/15/15, stratifikasi per `failure_mode` terverifikasi)
      (Langkah 10)
- [x] Tes otomatis anti-kebocoran target (`ml/tests/test_data_contract.py`, 5/5 lolos)

## Referensi Terkait

- `dataset_card.md` -- sumber dan temuan EDA seluruh dataset publik, verifikasi cargo profiles,
  dan hasil validasi sim-to-real
- `feature_schema.md` -- kontrak 12 kolom fitur yang diserahkan ke R2
- `ml/tests/test_data_contract.py` -- tes otomatis kontrak data
- Playbook Teknis ColdTrack AI, Bagian 2.3 -- spesifikasi lengkap generator data sintetik
