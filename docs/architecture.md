# Arsitektur ColdTrack AI

Sistem ini punya tiga bagian: chip edge di truk (KV260), backend armada, dan dasbor. Chip menghitung status dan
diagnosis sekali di truk. Backend memverifikasi hasilnya, menambahkan forecast suhu, lalu dasbor
menampilkannya. Truk yang belum memakai chip dihitung penuh di cloud dengan komponen yang sama.

```
sensor truk ─► KV260 (PL): segel SHA-256 + HMAC · mesin fisika · XGBoost 420 pohon
                 │  paket hasil per menit + bacaan mentah, lewat MQTT QoS 1
                 ▼
          mosquitto ─► worker-ingest ─► TimescaleDB (telemetry, edge_results)
                                            │ NOTIFY telemetry_arrived
                                            ▼
              worker-infer, jendela 1 menit:
                truk ber-chip  → edge.kondisi (hasil chip) + forecast GRU
                truk tanpa chip → mesin fisika + GRU + XGBoost TTB
                 + kesehatan sensor (aturan)
                                            │ predictions, truck_state, incidents, notifications
                                            ▼
                  api (REST /api/v1/fleet/*, SSE /stream) ─► dasbor Next.js
```

Satu image backend menjalankan semua peran (`api`, `worker-ingest`, `worker-infer`, `virtual-trucks`).
Penyebaran hanya lokal untuk demo. TLS, ACL per perangkat, hosting publik, dan backup belum dikerjakan.

## 1. Chip edge (`hw/`)

Chip membaca satu sampel per menit lalu menjalankan tiga blok paralel:

| Blok | Fungsi |
|---|---|
| Mesin fisika (`physics.sv`) | Status AMAN/WASPADA/KRITIS dan Time-to-Breach, sama dengan `backend/app/core/engine.py` |
| Fitur dan pohon (`features.sv`, `tree_engine.sv`) | 82 fitur bilangan bulat dari ring buffer 256 menit, lalu XGBoost 420 pohon untuk diagnosis 7 kelas |
| Segel (`seal.sv`, `sha256_core.sv`) | Rantai hash SHA-256 atas rekaman 23 byte, ditandatangani HMAC dengan kunci 32 byte yang terkunci |

Hasil dibaca driver ARM lewat AXI4-Lite (`0xA000_0000`) dan dikirim ke cloud. Alarm sopir keluar langsung ke pin,
tanpa lewat jaringan. Timing, resource, dan status verifikasi ada di [hw/README.md](../hw/README.md).

Cloud memeriksa HMAC dan rantai, mencocokkan rekaman dengan bacaan, lalu memakai hasil chip tanpa menghitung
ulang (`backend/app/edge.py`). Status verifikasi: `OK`, `OK_RANTAI_BARU`, `MAC_SALAH`, `RANTAI_PUTUS`,
`REKAMAN_BEDA`, `TANPA_KUNCI`. Formatnya ada di [device_contract.md](device_contract.md).

## 2. Backend (`backend/`)

- FastAPI dan Pydantic v2. Konfigurasi di `config.yaml`.
- `app/core/`: mesin fisika (penaksir suhu muatan, TTB, anggaran pintu, aturan sensor). Sumber status dan TTB
  yang ditampilkan. Rumusnya ada di [train_ai.md](train_ai.md) bagian 4.
- `app/inference.py`: provider diagnosis (GRU), aturan diagnosis, dan guard label.
- `app/edge.py`: verifikasi dan pemakaian hasil chip.
- `app/workers/`: `ingest` (MQTT ke database), `infer` (jendela 1 menit per truk), `virtual_trucks`
  (24 truk virtual yang memutar ulang trip val v4).
- `migrations/`: skema TimescaleDB.

Endpoint `POST /api/v1/analyze` menerima 60 bacaan atau lebih dan menjalankan jalur cloud penuh tanpa menyentuh
data armada. Kontraknya ada di [api_contract.md](api_contract.md), bersama API armada dan SSE.

## 3. Model (`backend/models/`)

| Berkas | Dipakai oleh | Isi |
|---|---|---|
| `coldtrack_v5.onnx` | provider `v3` (bawaan) | GRU 3x128 dengan label v5. Masukan `window [n, 60, 12]` dan `konteks [n, 6]`, keduanya mentah. Keluaran forecast t+15/30/60 dan peluang 7 kelas |
| `coldtrack_v5.labels.json` | provider `v3` | Urutan kelas, konfigurasi, metrik test, keterbatasan |
| `coldtrack_ttb_window.onnx` | provider `v3` | XGBoost TTB 300 pohon, hanya informasi (`ttb_model_min`) |
| `coldtrack_v3.onnx` dan `.labels.json` | rollback ke bobot v3 | GRU versi G3, masukan `window` saja |
| `coldtrack_gru.onnx`, `coldtrack_ttb.onnx` | provider `checkpoint2` | Model sebelumnya (3 kejadian), untuk rollback |

Metrik, seleksi, dan keterbatasan ada di [model_card.md](model_card.md).

### Provider diagnosis dan rollback

`model.diagnosis_provider` di `config.yaml` memilih sumber `forecast` dan `failure_mode`: `v3` (bawaan) atau
`checkpoint2`. Mengganti nilainya lalu me-restart backend sudah cukup untuk rollback. Mengembalikan bobot v3
cukup mengubah `gru_onnx_path`, `labels_path`, dan `version` di bagian provider `v3`. Setiap respons memuat
`diagnosis_provider` dan `model_version`.

Pembagian keputusan:

- Status dan TTB yang ditampilkan selalu dari mesin fisika, apa pun providernya.
- Masalah sensor hanya dari aturan sensor. Label `masalah_sensor` dari model tidak dipakai.
- `prapendinginan_buruk` dan `reefer_mati_total` diputuskan aturan diagnosis (`inference.aturan_diagnosis`),
  karena model mengenalinya hanya dari satu sinyal bersih simulator.
- Label tidak boleh `normal_sehat` saat status WASPADA atau KRITIS. Yang tampil `pintu_terbuka` atau
  `suhu_muatan_mendekati_batas`.
- Bila ada jeda lebih dari 90 detik di 60 bacaan terakhir, respons memuat `data_lengkap: false` dan keyakinan
  diagnosis dibatasi 0,5. Status tidak berubah.
- Konteks trip butuh bacaan pertama trip. Worker membacanya terpisah karena riwayat jendela dibatasi 240 menit.

## 4. Alur satu menit di cloud

1. Bacaan masuk lewat MQTT atau webhook vendor, divalidasi, dan disimpan. Duplikat dibuang dan data terlambat diterima.
2. `worker-infer` membangun jendela per truk: grid 1 menit, celah sampai 5 menit diisi bacaan terakhir, waktu
   dikonversi ke zona armada (Asia/Jakarta) karena fitur `hour_of_day` dilatih dengan jam lokal.
3. Truk ber-chip dengan hasil yang sah memakai `edge.kondisi`, dan GRU hanya dijalankan untuk forecast. Truk lain
   memakai jalur cloud penuh.
4. Aturan kesehatan sensor, lalu pembuatan insiden, notifikasi, dan estimasi kerugian.
5. Hasil ditulis ke database, dan dasbor menerima pembaruan lewat SSE.

Model hanya dijalankan untuk jendela terakhir, sedangkan mesin fisika membaca seluruh riwayat karena penaksir
suhu muatan butuh itu.

## 5. Frontend (`frontend/`)

Next.js 14 (App Router), TypeScript, Tailwind dengan komponen shadcn/ui, grafik Recharts, peta OpenStreetMap.
Halaman: Ringkasan, `/condition`, `/truck/[id]`, `/actions`, `/losses`, `/sensor`, `/location`, `/simulation`.
State disimpan lokal di React. Notifikasi memakai SSE.

## 6. Dokumen terkait

- [device_contract.md](device_contract.md): topik MQTT, payload, dan objek `edge`.
- [api_contract.md](api_contract.md): `/analyze` dan API armada.
- [fleet_assumptions.md](fleet_assumptions.md): asumsi `[ASUMSI]` dan `[DESAIN]` armada dan biaya.
- [train_ai.md](train_ai.md): data latih, simulator, mesin fisika.
- [model_card.md](model_card.md) dan [ai_governance.md](ai_governance.md): metrik, batas keputusan, risiko.
- [demo.md](demo.md): menjalankan demo.
