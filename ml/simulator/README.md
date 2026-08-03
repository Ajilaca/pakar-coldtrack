# Simulator Termal — ColdTrack AI

README ini menjelaskan isi notebook simulator (`02_simulator.ipynb` atau nama serupa) yang
digunakan untuk menghasilkan data sintetik cold chain. Dikerjakan oleh R1 (AI Data Engineer),
mengacu pada Playbook Teknis Bagian 2.3.

## Tujuan

Menghasilkan data suhu kargo yang realistis secara fisika, lengkap dengan label
(`is_anomaly`, `failure_mode`, `time_to_breach`), untuk melatih model prediksi Time-to-Breach.
Label ini tidak tersedia di data publik manapun (lihat `dataset_card.md`), sehingga dibangun
sendiri melalui simulasi berbasis persamaan pendinginan Newton.

## Struktur Notebook

1. **Setup** — import library (`numpy`, `pandas`, `matplotlib`)
2. **Cargo Profiles** — dictionary `cargo_profiles`, berisi rentang suhu aman, massa, dan
   toleransi waktu tiap jenis muatan (vaksin, daging beku, ikan segar, sayur/buah, produk susu).
   Rentang suhu telah diverifikasi terhadap standar resmi (WHO, Peraturan BPOM No. 6/2020,
   Codex Alimentarius, SNI, HACCP) — detail dan sumber ada di `dataset_card.md`.
3. **Ambient & Solar Generator** — fungsi `generate_ambient_solar()`, menghasilkan suhu ambien
   dan radiasi matahari yang berubah mengikuti pola siklus harian, dikalibrasi berdasarkan data
   NASA POWER untuk koordinat Jakarta (lihat `dataset_card.md` bagian dataset #7).
4. **Model Termal Inti** — fungsi `simulate_trip()`, mesin utama simulator. Menjalankan
   persamaan pendinginan Newton per menit, dengan opsi menyuntikkan salah satu dari 9 kode
   anomali (A0–A8).

## Fungsi Utama: `simulate_trip()`

```python
simulate_trip(
    cargo_type,          # nama profil muatan, mis. 'vaksin_2_8C'
    n_steps=240,          # durasi trip dalam menit
    start_hour=6,          # jam berangkat (0-23), memengaruhi kurva ambient/solar
    anomaly_type=None,     # None (sehat) atau salah satu kode 'A1'-'A8'
    onset_minute=None,     # menit mulai anomali (wajib jika anomaly_type diisi, kecuali A8)
    seed=None               # untuk reproducibility
)
```

Mengembalikan dictionary berisi:
- `temp_profile` — suhu kargo sebenarnya, per menit
- `temp_sensor` — suhu yang "dibaca" sensor (berbeda dari `temp_profile` khusus untuk A5/A6,
  yang mensimulasikan kegagalan sensor itu sendiri, bukan kegagalan kargo)
- `ambient_profile` — suhu ambien sepanjang trip
- `is_anomaly`, `failure_mode`, `time_to_breach` — tiga label target

## Status Kode Anomali (9 dari 9 tervalidasi)

| Kode | Nama | Cara kerja | Status |
|---|---|---|---|
| A0 | Sehat | Tidak ada gangguan | ✅ |
| A1 | Pintu terbuka terlalu lama | `door_open` aktif 20 menit | ✅ |
| A2 | Degradasi kompresor | `u[t]` meluruh 1,0→0,3 selama 3 jam | ✅ (breach butuh trip panjang, ~5 jam) |
| A3 | Kegagalan reefer total | `u[t]` → 0 mendadak | ✅ |
| A4 | Kebocoran refrigeran | `k_cool` berkurang 40% | ✅ (validasi via pelebaran variasi suhu, bukan breach cepat) |
| A5 | Sensor macet (stuck-at) | `temp_sensor` dibekukan di satu nilai | ✅ |
| A6 | Sensor berderau / paket hilang | Lonjakan impuls acak + gap NaN | ✅ |
| A7 | Kejut suhu ambien | Kecepatan 0 + pengali radiasi matahari 3x | ✅ (perlu diuji saat radiasi matahari tinggi, siang hari) |
| A8 | Prapendinginan buruk | Suhu awal di atas batas atas | ✅ |

## Catatan Kalibrasi

Konstanta fisika (`k_cool=50`, `k_leak=0.5`, `k_door=8.0`, `k_solar=0.05`) telah dikalibrasi
ulang dari nilai awal di Playbook Teknis (`k_cool=0.15` dkk) karena skala aslinya membuat noise
mendominasi efek fisika sehingga suhu "melayang" seperti random walk. Nilai saat ini menghasilkan
riak suhu ~0,9°C pada kondisi sehat, mendekati target playbook (±0,4°C).

## Belum Dikerjakan / Langkah Selanjutnya

- [ ] Lapisan realisme sensor tambahan: kuantisasi 0,1°C, jitter GPS, packet loss bursty
      (Langkah 7 Playbook)
- [ ] Randomisasi domain: generate 600–900 trip dengan variasi acak cargo, jam berangkat,
      kualitas insulasi, gaya mengemudi (Langkah 8 Playbook)
- [ ] Validasi sim-to-real: uji Kolmogorov–Smirnov dan ACF terhadap dataset IoT publik
      (Langkah 9 Playbook)
- [ ] Pembagian data per `trip_id` (70/15/15) dan ekspor ke `data/processed/*.parquet`
      (Langkah 10 Playbook)
- [ ] Tes otomatis anti-kebocoran target (memastikan `is_anomaly`, `failure_mode`,
      `time_to_breach` tidak pernah masuk sebagai fitur input)

## Referensi Terkait

- `dataset_card.md` — sumber dan temuan EDA seluruh dataset publik yang mendasari kalibrasi
- `feature_schema.md` — kontrak 12 kolom fitur yang diserahkan ke R2
- Playbook Teknis ColdTrack AI, Bagian 2.3 — spesifikasi lengkap generator data sintetik
