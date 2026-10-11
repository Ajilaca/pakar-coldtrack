# Menjalankan demo armada (lokal)

Demo ini berjalan **lokal** dengan Docker. Tidak ada deploy publik, sesuai keputusan 11 Oktober 2026:
untuk saat ini hanya untuk keperluan demo. 24 truk virtual memutar ulang trip dari split val v4 lewat
MQTT, worker menjalankan model per truk, dan dasbor diperbarui langsung.

## Prasyarat

- Docker Desktop. Di Windows, aktifkan WSL integration.
- RAM bebas sekitar 4 GB.
- Port 3000 (dasbor), 8000 (API), 5432 (database), dan 1883 (MQTT) tidak sedang dipakai.

## Mulai

```bash
docker compose --profile dev up -d --build
```

Buka **http://localhost:3000**. Build pertama butuh beberapa menit. `--profile dev` menyalakan
simulator truk virtual (`virtual-trucks`); tanpa itu tidak ada data yang masuk.

- **Jam simulasi:** `SIM_SPEED=30` (bawaan), artinya 1 menit simulasi = 2 detik nyata. Ubah di `.env`
  (lihat `.env.example`).
- **2 menit pertama:** setiap truk berstatus **MENUNGGU DATA**, karena model butuh 60 menit data trip
  (60 menit simulasi). Setelah itu status, prediksi, dan insiden mulai terisi.
- **Truk mati:** dua perangkat sengaja "mati" setelah 60–120 menit simulasi, sehingga truknya tampil
  **TIDAK ADA DATA** (tidak pernah AMAN).
- **Putus sinyal:** terjadi acak. Bacaan disangga lalu dikirim sebagai batch; celah panjang tampil
  sebagai **DATA TIDAK LENGKAP**.

## Berhenti dan reset

```bash
docker compose --profile dev stop        # berhenti, data tetap ada
docker compose --profile dev down -v     # hapus semua data demo (database + broker), mulai bersih
```

Data menumpuk selama stack menyala: notifikasi, insiden, dan nilai kerugian ikut membesar. **Reset
sebelum presentasi** supaya angkanya wajar.

## Alur demo yang disarankan

1. **Ringkasan:** KPI armada, truk kritis vs tidak, truk per diagnosis, tabel risiko, peta mini.
2. Klik truk **KRITIS**, lalu **Detail truk**: kondisi langsung, banner status (TTB, diagnosis,
   keyakinan), grafik suhu aktual + prediksi +15/+30/+60, faktor pendorong, dan tindakan.
3. **Lonceng notifikasi:** kotak masuk. Toast muncul di kanan bawah saat ada truk yang memburuk.
4. **Tindakan:** isi nama operator, lalu **Tugaskan → Mulai tangani → Tandai selesai**. Setiap
   langkah tercatat di audit trail.
5. **Kerugian:** nilai berisiko, kerugian terjadi, dan yang berhasil diatasi, beserta cara
   menghitungnya.
6. **Sensor:** skor kesehatan per truk dan panel "Perlu diperbarui".
7. **Lokasi:** peta Jawa, truk dan depo diwarnai sesuai status.
8. **Simulasi:** skenario demo, misalnya "Pintu Kargo Terbuka Terlalu Lama" → KRITIS. Tidak
   mengubah data armada.

## Yang perlu disampaikan dengan jujur saat demo

- **Data:** sintetis dari simulator (split val v4), bukan logger truk nyata. Jam asli trip tidak
  dipertahankan saat diputar ulang.
- **Alarm pada truk normal:** cukup sering, terutama muatan 2–4 °C. Mesin fisika memberi status
  non-AMAN pada sekitar 20% menit trip normal (`healthy_alert_rate` 0,199,
  `eval/results/iter2_results.json`). Rincian: `docs/fleet_assumptions.md`.
- **Rupiah:** estimasi dari harga per kg `[ASUMSI]`, bukan kerugian tercatat.
- **Kesehatan sensor:** skor memakai bobot `[DESAIN]` yang belum dikalibrasi. Model Berkeley belum
  lolos evaluasi (G4).
- **Satu sensor per truk:** desain Figma menampilkan tiga posisi sensor.
- **Target PRD:** tidak ada klaim bahwa target PRD terpenuhi.

## Masalah umum

| Gejala | Penyebab / solusi |
|---|---|
| Sidebar menulis "Memuat ulang tiap 30 detik" | Koneksi SSE ke API putus; dasbor jatuh ke polling. Cek `docker compose logs api` |
| Semua truk MENUNGGU DATA terus | Simulator tidak jalan: pastikan memakai `--profile dev`, lalu cek `docker compose logs virtual-trucks` |
| Halaman armada error, Simulasi jalan | Database/worker belum siap. Cek `docker compose ps` (semua harus healthy) |
| Port 3000/8000 sudah dipakai | Hentikan server lain (mis. `npm start` atau uvicorn lokal) lalu ulangi |

## Di luar cakupan demo (rencana Fase 6 bila nanti online)

Reverse proxy dengan HTTPS dan basic auth, MQTT TLS 8883 dengan akun dan ACL per perangkat, backup
`pg_dump` harian, serta hosting. Frontend bisa ditaruh di Vercel, tetapi backend (worker, TimescaleDB,
MQTT, SSE) butuh host container seperti Railway atau VPS.
