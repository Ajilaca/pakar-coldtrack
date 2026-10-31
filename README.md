# ColdTrack AI

Sistem peringatan dini kegagalan rantai dingin untuk armada truk berpendingin. Chip FPGA di truk (AMD Kria KV260)
menghitung status dan diagnosis sekali per menit. Backend di cloud lalu memverifikasi hasilnya, menambahkan
forecast suhu, dan menampilkannya di dasbor. Mesin diagnosis yang sama juga sudah di-layout sebagai chip ASIC
SKY130.

Untuk setiap truk, dasbor menampilkan status (AMAN, WASPADA, atau KRITIS), Time-to-Breach (sisa menit sampai muatan
melewati batas suhu), diagnosis penyebab, tindakan yang disarankan, insiden beserta audit trail, dan estimasi
kerugian.

![demo](docs/images/demo.gif)

## Cara kerja

```
sensor truk ─► KV260: segel SHA-256 + HMAC · mesin fisika · XGBoost 420 pohon
                 │  hasil per menit + bacaan mentah, lewat MQTT
                 ▼
          backend: verifikasi segel ─► forecast GRU ─► database ─► dasbor
```

Di truk, chip menghitung status, TTB, dan diagnosis, lalu menyegel tiap rekaman dengan rantai hash dan HMAC. Alarm
sopir keluar langsung ke pin, jadi tetap menyala saat sinyal hilang. RTL dan hasil Vivado ada di
[hw/](hw/README.md).

Di cloud, backend memeriksa segel dan memakai hasil chip apa adanya. GRU hanya dijalankan untuk forecast suhu
+15/+30/+60 menit. Truk tanpa chip dihitung penuh di cloud dengan komponen yang sama.

Status dan TTB selalu berasal dari mesin fisika. Model memberi forecast dan diagnosis penyebab, sedangkan masalah
sensor hanya ditentukan aturan sensor.

Penjelasan lengkap: [docs/architecture.md](docs/architecture.md).

## Halaman dasbor

| Halaman | Isi |
|---|---|
| Ringkasan | KPI armada, truk kritis, truk per diagnosis, tabel risiko, peta mini |
| Kondisi (`/condition`) | Status dan prediksi semua truk |
| Detail truk (`/truck/[id]`) | Grafik suhu aktual dan prediksi, faktor pendorong, tindakan |
| Tindakan (`/actions`) | Alur insiden: Tugaskan, Mulai tangani, Tandai selesai, tercatat di audit trail |
| Kerugian (`/losses`) | Nilai berisiko, kerugian terjadi, dan yang berhasil diatasi |
| Sensor (`/sensor`) | Skor kesehatan perangkat dan daftar yang perlu diperbarui |
| Lokasi (`/location`) | Peta Jawa dengan truk dan depo diwarnai menurut status |
| Simulasi (`/simulation`) | Uji skenario lewat `POST /api/v1/analyze`, tidak mengubah data armada |

Notifikasi muncul di lonceng dan sebagai toast saat ada truk yang memburuk (lewat SSE).

## Menjalankan

Butuh Docker Desktop (di Windows aktifkan WSL integration), sekitar 4 GB RAM bebas, dan port 3000, 8000, 5432,
dan 1883 yang kosong. Salin `.env.example` ke `.env`.

Demo armada dengan 24 truk virtual:

```bash
docker compose --profile dev up -d --build
```

Buka http://localhost:3000. `--profile dev` menyalakan simulator `virtual-trucks` yang memutar ulang trip dari
split val v4. Dua menit pertama tiap truk berstatus MENUNGGU DATA, karena model butuh 60 menit data trip
(`SIM_SPEED=30` secara bawaan). Reset data sebelum presentasi supaya angka insiden dan kerugian wajar:

```bash
docker compose --profile dev down -v
```

Tanpa simulator (API, dasbor, dan database saja): `docker compose up --build`.

Untuk mengembangkan frontend, nyalakan stack dengan
`docker compose --profile dev up -d db mosquitto api worker-ingest worker-infer virtual-trucks`, lalu jalankan
`npm run dev` di `frontend/`. `docker-compose.dev.yml` hanya berisi backend dan frontend tanpa database dan MQTT,
jadi di sana hanya halaman Simulasi yang berfungsi. Panduan demo: [docs/demo.md](docs/demo.md).

## Model

| | |
|---|---|
| Diagnosis dan forecast | GRU v5 (3 lapis, hidden 128, dengan 6 fitur konteks trip) dalam ONNX; keluarannya 7 kelas mode kegagalan dan forecast suhu t+15, t+30, dan t+60 menit |
| Status dan TTB | mesin fisika, dengan XGBoost sebagai pembanding informasi untuk TTB |
| Di chip | XGBoost 420 pohon untuk diagnosis dengan 82 fitur bilangan bulat |
| Hasil test | Macro F1 0,820 dan PR-AUC 0,855 dengan label v5, yang memperlakukan pintu terbuka dan kejut ambien sebagai kejadian sementara; dengan label lama 0,756 dan 0,812 (model v3: 0,668 dan 0,786) |

Semua data berasal dari simulator fisika, belum dari logger truk sungguhan. Pengujian gangguan menunjukkan beberapa
kelas (reefer mati, pintu terbuka, prapendinginan buruk) dikenali dari satu sinyal yang terlalu bersih di
simulator, jadi dua di antaranya sekarang diputuskan aturan. Kelas `degradasi_bertahap` masih lemah.

Angka, perbandingan versi, dan hasil pengujian gangguan ada di [docs/model_card.md](docs/model_card.md). Asal
data dan rumus fisikanya di [docs/train_ai.md](docs/train_ai.md).

## Chip ASIC (SKY130)

Mesin fisika, fitur, dan XGBoost juga dibuat sebagai chip ASIC di proses SkyWater SKY130 dengan LibreLane. Chip
berukuran 2,2 × 2,2 mm, berjalan pada 10 MHz, dan dihubungkan ke mikrokontroler lewat SPI. Model XGBoost dibaca
dari flash QSPI dan diverifikasi dengan tag HMAC, jadi model bisa diganti tanpa membuat chip baru.

| Pemeriksaan | Hasil |
|---|---|
| Signoff layout (DRC, LVS, XOR, antena) | 0 pelanggaran |
| Timing | setup dan hold terpenuhi di 9 corner |
| Gate-level simulation | lulus tanpa delay (bit-exact dengan golden) dan dengan SDF di corner tt, ss, ff |
| Wrapper Caravel untuk ChipFoundry chipIgnite | signoff bersih, precheck 13/13 lulus |

Berkas tapeout (GDS, LEF, netlist, SPEF) dan laporan layout ada di GitHub Release
[`asic-v1.0`](https://github.com/Ajilaca/pakar-coldtrack/releases/tag/asic-v1.0). Kunci HMAC yang tertanam di
layout ini adalah kunci lomba yang dipublikasikan, sehingga tapeout sungguhan memerlukan kunci baru dan layout
ulang. Mesin GRU belum di-layout karena keterbatasan waktu. Rinciannya di [hw/asic/](hw/asic/README.md).

## Pengujian

```bash
cd backend && ruff check . && pytest        # unit test backend
cd frontend && npm run lint && npm run build
```

Tes integrasi stack armada (MQTT ke database, dedupe, data terlambat, webhook, prediksi, API, audit, SSE) berjalan
di workflow `Fleet CI` ([.github/workflows/fleet.yml](.github/workflows/fleet.yml)). RTL diuji dengan cocotb
(`cd hw && make test`). Suite evaluasi sistem ada di [eval/](eval/README.md), dan benchmark latih ulang di
[bench/](bench/README.md).

## Struktur repo

```
backend/    FastAPI, worker ingest MQTT dan inferensi, TimescaleDB (migrations/), tests/
frontend/   Dasbor Next.js 14
hw/         RTL chip edge KV260, versi ASIC SKY130 (hw/asic), testbench cocotb, skrip Vivado, driver ARM
ml/         Simulator, notebook, pelatihan GRU dan XGBoost, ekspor ONNX
bench/      Percobaan latih ulang dan benchmark antar-device (hasil di bench/results/)
eval/       Evaluasi sistem sebagaimana di-deploy
data/       Data olahan hasil simulator dan dataset Berkeley
docker/     Konfigurasi Mosquitto
docs/       Arsitektur, kontrak API dan perangkat, kartu model, tata kelola AI
```

Setiap folder punya `README.md` sendiri.

## Dokumentasi

- [Arsitektur](docs/architecture.md)
- [Data dan fisika untuk melatih model](docs/train_ai.md)
- [Kartu model](docs/model_card.md)
- [Tata kelola AI](docs/ai_governance.md)
- [Kontrak API](docs/api_contract.md), [kontrak perangkat](docs/device_contract.md), dan [asumsi armada](docs/fleet_assumptions.md)
- [Menjalankan demo](docs/demo.md)
- [Versi ASIC SKY130](hw/asic/README.md) dan [laporan layout](hw/asic/xgboost/laporan.pdf)
