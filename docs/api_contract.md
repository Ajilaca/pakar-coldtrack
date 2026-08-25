# Kontrak API — ColdTrack AI

Kontrak resmi antara antarmuka dan layanan backend ColdTrack AI. Dokumen ini
menetapkan bentuk permintaan, bentuk respons, dan semantik tiap field — termasuk
kapan sebuah field bernilai `null` dan apa artinya bagi tampilan.

Implementasi: `backend/app/schemas.py`, `backend/app/main.py`.
Status: **dibekukan untuk demo COMPFEST 18**.

---

## 1. Endpoint Inti

```
POST /api/v1/analyze
```

Satu-satunya endpoint yang dipakai untuk alur inti (satu input → satu output AI).

- `GET /health` — probe Docker healthcheck.
- `GET /api/v1/scenarios` — daftar metadata 5 skenario demo.
- **Tidak ada endpoint lain.**

---

## 2. Request — Kontrak Field

```
{
  "shipment_id": "TRK-JKT-0417",
  "cargo_profile": "vaksin_2_8C",
  "readings": [ <TelemetryReading>, ... ]
}
```

### `readings[]` — satu elemen `TelemetryReading`

| Field | Tipe | Wajib? | Keterangan |
|---|---|---|---|
| `ts` | ISO 8601 datetime | **wajib** | Waktu bacaan, contoh `2026-08-20T07:00:00+07:00` |
| `temp_c` | float | **wajib** | Suhu kargo °C |
| `humidity` | float | **wajib** | Kelembapan relatif % |
| `ambient_c` | float | **wajib** | Suhu ambien °C |
| `door_open` | bool | **wajib** | Status pintu kargo |
| `reefer_on` | bool | **wajib** | Status unit pendingin |
| `speed_kmh` | float | **wajib** | Kecepatan kendaraan km/h |
| `harsh_events` | int | **wajib** | Jumlah event mengemudi kasar |
| `lat` | float | opsional | Bukan fitur model; default `0.0` |
| `lon` | float | opsional | Bukan fitur model; default `0.0` |
| `solar_radiation` | float | opsional | Default `0.0` |

> **Nama field wajib persis seperti di atas.** Validasi Pydantic v2 menolak
> penamaan lain — misalnya `temperature_c`, `ambient_temp_c`, atau `timestamp` —
> dengan **HTTP 422**. Penolakan ini disengaja: field yang salah nama akan
> terbaca sebagai field yang hilang, dan model tidak boleh menerima jendela
> yang diam-diam tidak lengkap.

### `cargo_profile`

Harus salah satu profil yang ada di `backend/config.yaml`:

- `vaksin_2_8C`
- `daging_beku_-18C`
- `buah_segar_2_4C`
- `ikan_segar_0_5C`
- `produk_susu_2_4C`

Profil di luar daftar di-fallback ke `vaksin_2_8C` di sisi rules (tidak menolak
permintaan), tetapi perilaku ini tidak dijamin untuk demo — gunakan daftar resmi.

---

## 3. Aturan Jumlah Bacaan

- **Minimum 60 bacaan** per `readings[]`. Payload kurang dari 60 ditolak dengan
  **HTTP 400** (bukan 422).
- Model GRU fusion menghitung statistik ringkasan jendela (std/trend) internal;
  jendela yang di-pad menghasilkan prediksi diam-diam salah. Karena itu
  frontend **tidak boleh** mengirim jendela pendek.
- Kelima skenario demo yang dikemas bersama layanan masing-masing berisi
  ≥ 60 bacaan berinterval 1 menit, sehingga memenuhi syarat ini.

---

## 4. Response 200 OK

```
{
  "status": "KRITIS",
  "risk_index": 0.87,
  "time_to_breach_min": 23.4,          // null bila sehat / di luar display cap 30 menit
  "failure_mode": { "label": "degradasi_pendinginan", "confidence": 0.91 },
  "forecast": { "t15": 6.9, "t30": 8.4, "t60": 11.2 },
  "drivers": [
    { "feature": "laju_kenaikan_suhu", "value": "+0.13 C/mnt", "contribution": 0.44 },
    { "feature": "delta_suhu_ambien",  "value": "27.2 C",      "contribution": 0.31 },
    { "feature": "durasi_reefer_aktif","value": "196 mnt",     "contribution": 0.18 }
  ],
  "actions": [
    { "priority": 1, "text": "...", "eta_min": 5 },
    { "priority": 2, "text": "...", "eta_min": 19 },
    { "priority": 3, "text": "...", "eta_min": 10 }
  ],
  "model_version": "coldtrack-gru-v2-fusion-v4",
  "inference_ms": 3
}
```

`inference_ms` adalah waktu pemrosesan sisi server, bukan waktu bolak-balik
jaringan; nilainya biasa berada di angka satu digit (lihat profil latensi pada
proposal §4.3.7).

### Semantik penting untuk tampilan

- `status` ∈ {`AMAN`, `WASPADA`, `KRITIS`}.
- `time_to_breach_min` adalah `null` untuk truk sehat (label `normal_sehat`)
  dan untuk TTB di atas display cap 30 menit. Tampilkan "—" atau status risiko,
  bukan angka.
- **Cadangan berbasis aturan.** Bila model mengembalikan `null` sementara
  `status` berakhir `WASPADA` atau `KRITIS`, backend mengisi angkanya dengan
  ekstrapolasi linear dari laju kenaikan suhu lima menit terakhir:
  `(ambang profil − suhu terkini) ÷ Δtemp rata-rata` (0,0 bila suhu sudah
  melewati ambang). Angka ini **tidak** berasal dari `coldtrack_ttb.onnx`,
  sehingga MAE 7,08 menit tidak berlaku untuknya dan nilainya tidak dibatasi
  display cap 30 menit.
- **Sensor bermasalah menimpa semua di atas.** Bila `failure_mode.label`
  mengandung "sensor", `time_to_breach_min` selalu `null` — termasuk hasil
  cadangan — dan `status` dikunci `WASPADA` dengan indeks risiko dijepit ke
  0,45–0,60.
- `failure_mode.label` memakai nama Indonesia: `normal_sehat`,
  `pintu_terbuka_lama`, `kegagalan_reefer_total`, `fluktuasi_ambien_ekstrem`,
  `prapendinginan_buruk`, `degradasi_pendinginan`, `masalah_sensor`.
- `drivers` selalu 3 item; `actions` selalu 3 item.

---

## 5. Catatan integrasi antarmuka

- Antarmuka boleh memakai penomoran menit relatif untuk sumbu-x grafik, tetapi
  yang dikirim ke backend harus `ts` absolut — fitur `hour_of_day` diturunkan
  dari situ.
- `lat`/`lon` hanya dipakai untuk peta di antarmuka; keduanya tidak pernah masuk
  ke matriks fitur model.
- Antarmuka memanggil backend sungguhan bila `NEXT_PUBLIC_USE_MOCK=false`. Nilai
  ini ditanamkan saat kompilasi Next.js, sehingga harus diteruskan sebagai
  *build argument* Docker, bukan variabel runtime.

---

## 6. Referensi Implementasi

- Skema Pydantic: `backend/app/schemas.py`
- Penegakan min 60 bacaan: `backend/app/main.py` (`analyze_telemetry`)
- Kontrak fitur model: `docs/feature_schema.md`