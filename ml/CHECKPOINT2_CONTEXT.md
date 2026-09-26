# ColdTrack AI v2 — Konteks Checkpoint-2 (`checkpoint-2-iteration`)

Dibuat selama jam hackathon, 26 Sep 2026. Dokumen ini menjelaskan isi commit checkpoint-2: apa yang berubah dari MVP lama, cara menjalankan, hasil, dan keterbatasan.

## 1. Kenapa dibangun ulang
Model lama dilatih pada data yang seluruhnya sintetis dan hasilnya buruk. Pembangunan ulang:
1. Simulator fisika baru dengan pilihan produk (ikan, daging, sayur, buah, susu/telur, lainnya) dan massa muatan.
2. Data iklim asli BMKG dan pola kerusakan sensor asli dari Intel Berkeley Lab. Label suhu muatan dan TTB tetap dari simulator.
3. Sistem hibrida: fisika + aturan + model belajar (GRU dan XGBoost).

## 2. Isi repo (checkpoint-2)

| File | Fungsi |
|---|---|
| `coldtrack_sim.py` | Simulator fisika truk (dua simpul: udara kabin dan muatan) dan pembuat dataset latih. Setiap parameter truk diberi tag sumber di dict `TRUCK` |
| `prep_windows.py` | Bagi data per trip (70/15/15), bersihkan sensor, susun jendela 60 menit, hitung label pintu lama (>= 20 menit) |
| `train_gru.py`, `run_train.py` | GRU multi-tugas: kejadian (pintu lama, kejut ambien, sensor rusak) + suhu muatan +15/30/60 menit + TTB |
| `ttb_features.py`, `observer.py`, `run_train_xgb.py` | Fitur ringkasan jendela dan fitur fisika; XGBoost untuk TTB |
| `observer.py` | Penaksir suhu muatan (kausal, tiap menit sejak menit 0) dan proyeksi TTB fisika |
| `door_budget.py` | Fisika murni: sisa menit pintu boleh terbuka (bacaan sensor dan kasus terburuk), dan hasil bila pintu ditutup sekarang; ada `sensitivity()` |
| `sensor_rules.py` | Aturan sensor: nilai mustahil, lompatan, datar lama, tegangan (opsional) |
| `gru_v1.pt`, `scalers_v1.json` | Bobot GRU dan skala normalisasi (dilatih pada `dataset_v3`) |
| `xgb_ttb.json`, `xgb_features.txt` | Model XGBoost TTB dan urutan fiturnya |

Tidak di-commit: `dataset_v*.parquet` (83 MB tiap file, batas GitHub 100 MB) dan data mentah Intel `data.txt` (144 MB).

## 3. Cara menjalankan

```
python -m pip install torch pandas pyarrow scikit-learn xgboost
# dataset (buat di Colab dengan coldtrack_sim.generate_dataset, simpan sebagai dataset_v3.parquet)
python run_train.py --data dataset_v3.parquet --epochs 25
python run_train_xgb.py --data dataset_v3.parquet
```

Membuat dataset (Colab, butuh `climate_clean.csv`, `product_specs.csv`, `sensor_fault_params.json`):

```python
import coldtrack_sim as cs
clim, specs = cs.load_data()
ds = cs.generate_dataset(clim, specs, n_trips=1500, seed=0)
cs.summarize(ds)
ds.to_parquet("dataset_v3.parquet", index=False)
```

## 4. Sumber data dan parameter

**Data**
- Iklim: BMKG harian 2010–2020 (Kaggle `greegtitan/indonesia-climate`): t_min, t_avg, t_max, rh_avg. Semua stasiun digabung jadi "hari Indonesia".
- Sensor rusak: Intel Berkeley Lab (Kaggle `divyansh22/intel-berkeley-research-lab-sensor-data`), dipakai hanya untuk mengukur pola (nilai macet 122,15 C, ambang, derau 0,073 C).
- Produk: `data kalor.pdf` (54 produk), batas suhu dari proposal.

**Parameter truk (Isuzu 18 CBM refrigerated box)**

| Parameter | Nilai | Sumber |
|---|---|---|
| Dimensi dalam, payload | 4,015 x 2,1 x 1,8 m; 4.285 kg | halaman Isuzu (volume hitung 15,2 m3, bukan 18) |
| Mode suhu | beku -18..-20 C; chiller 0..+5 C | halaman Isuzu |
| K isolasi | 0,40 W/m2K | batas ATP kelas diperkuat; makalah truk 0,36 |
| Tebal isolasi | 8 cm | makalah truk 67–97 mm; pemasok 75–100 mm |
| h udara-muatan | 8 W/m2K | makalah truk (muatan karkas) |
| Kapasitas pendingin | 2.575 W | makalah truk (nominal 0 C dalam / 30 C luar) |
| Kerapatan curah | 500 kg/m3 | Cargo Handbook 400–595 (ikan beku kotak/karton) |
| Cd pintu | 0,65 | Gosney–Olama (via calcengineer.com), bukan dokumen ASHRAE asli |

Sumber makalah truk: https://publications.cnr.it/api/v1/documents/download/188981

## 5. Kejadian yang disimulasikan (independen, boleh bersamaan)
- **A1 pintu terbuka:** 1–60 menit, 1–2 kali buka, lebar 0,2–1,0. A0 tidak punya pintu terbuka.
- **A2 kejut ambien:** puncak = `t_max` BMKG; pendingin mati selama kejut.
- **A3 sensor rusak:** ekstrem / datar / bergantian.
- Pelanggaran = suhu **muatan** di luar rentang produk. TTB = menit sampai melewati batas (maks 240).

## 6. Arsitektur sistem (hibrida)
- **Fisika (observer, door_budget):** suhu muatan taksiran, TTB, sisa waktu pintu. Dipakai untuk 60 menit pertama dan TTB <= 60 menit.
- **Aturan sensor:** status ok/curiga/rusak.
- **GRU:** kejadian dan prediksi suhu ke depan (jendela 60 menit).
- **XGBoost:** TTB rentang lebih panjang, dengan fitur fisika.
- **Aturan keputusan (dari proposal lama):** TTB hanya tampil <= 30 menit; lantai status (TTB <= 30 -> minimal KRITIS, <= 60 -> minimal WASPADA); sensor bermasalah -> WASPADA, risiko dijepit 0,45–0,60, TTB disembunyikan. *(belum dirakit ke kode di checkpoint ini)*
- Masukan model: telemetri saja (T_sensor bersih, T_amb, RH, door_open, moving, jam sin/cos, sensor_bad) + info muatan. `reefer_duty`, `T_cargo`, `T_air`, `ev_*` bukan masukan.

## 7. Hasil (data uji `dataset_v3`, 1.500 trip, di dalam simulator)

| Keluaran | Hasil |
|---|---|
| GRU A1 pintu lama | AUC 0,999 (mudah; label hampir sama dengan `door_open`) |
| GRU A2 kejut ambien | AUC 1,000 |
| GRU A3 sensor rusak | AUC 0,849 |
| GRU suhu muatan +15/30/60 | MAE 0,8 C |

TTB (MAE menit):

| Metode | Semua | TTB < 120 |
|---|---|---|
| Tebak rata-rata | 80,6 | — |
| GRU | 39,6 | 122,2 |
| XGBoost tanpa fitur fisika | 42,7 | 86,6 |
| XGBoost + fitur fisika | 22,7 | 43,7 |
| Fisika murni (penaksir + proyeksi) | 17,6 | 37,5 |

Aturan sensor: 0 dari 1.004 trip tanpa A3 tertandai; deteksi ekstrem 100% (tunda 0 menit), datar 96% (tunda 60), bergantian 100% (tunda median 33). Sensor rusak menaikkan galat TTB fisika dari 24 ke 67 menit (TTB < 120).

## 8. Temuan Intel Lab yang membentuk aturan sensor
- 17,4% bacaan ekstrem; ~91% tepat 122,15 C; hanya muncul saat tegangan < 2,4 V.
- Kerusakan mendadak: hanya 14 dari 46 mote rusak permanen punya nilai ekstrem sebelum rusak.
- Rangkaian datar sehat p99 ~34 menit; >= 60 menit hanya 5 rangkaian di 2 mote. Datar tidak mendahului kegagalan.
- Lompatan > 5 C antar pembacaan pada sensor sehat: 0,008%.

## 9. Keterbatasan yang diakui
1. **Label suhu muatan dan TTB berasal dari simulator kita.** Penaksir fisika memakai persamaan yang sama, jadi "fisika paling akurat" hanya berlaku di simulator dan bukan bukti untuk truk nyata. Belum ada label suhu muatan nyata.
2. Klaim bahwa rumus fisika akan meleset di data lapangan adalah **hipotesis**, belum diuji.
3. Kasus "sebentar lagi rusak" (0 < TTB <= 30) masih lemah untuk semua metode (galat ~55 menit).
4. Simulator tidak memodelkan massa termal dinding/rak, sehingga suhu kabin bereaksi terlalu cepat (lompatan 14–36 C/menit saat pintu dibuka).
5. Uji deteksi sensor memakai kerusakan buatan generator; bukti terhadap dunia nyata hanya dari ambang Intel Lab.
6. Muatan dianggap homogen; luas pintu = lebar x tinggi box; sensor IoT terpisah dari termostat (asumsi).
7. Kompresor lemah/mati belum ditangani (fitur lanjutan); label pintu lama masih mudah.
8. Rumus pertukaran udara pintu adalah batas atas untuk box kosong.

## 10. Status pekerjaan
Selesai: data, simulator bersumber, GRU, XGBoost, penaksir fisika, `door_budget`, aturan sensor.
Belum: aturan keputusan terpadu, ekspor ONNX + cek paritas, backend/frontend (form + CSV), tabel parameter-sumber final, Evaluation Artifact PDF (20.30), pitch deck bahasa Inggris (23.59).
