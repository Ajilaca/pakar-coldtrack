# Kontrak perangkat (MQTT) — ColdTrack AI armada

Perangkat di truk (logger/gateway, atau adapter telematika vendor) mengirim telemetri ke broker MQTT.
Sinyal seluler putus-sambung, jadi perangkat **wajib menyangga (buffer) bacaan lokal** dan mengirimnya
sebagai batch saat tersambung kembali. Server menerima data terlambat dan mengabaikan duplikat.

## Identitas truk di topik

`{truck_key}` = nomor polisi tanpa spasi, huruf besar (`B 9012 KQ` → `B9012KQ`). Spasi diizinkan
MQTT tetapi rawan salah ketik, jadi tidak dipakai di topik.

## Topik

| Topik | QoS | Retained | Isi |
|---|---|---|---|
| `coldtrack/v1/{truck_key}/telemetry` | 1 | tidak | batch bacaan (di bawah) |
| `coldtrack/v1/{truck_key}/status` | 1 | **ya** | status perangkat; juga dipasang sebagai **LWT** dengan `online: false` |

## Payload telemetri (JSON, UTF-8)

```json
{
  "schema": "coldtrack.telemetry.v1",
  "device_id": "DEV-001",
  "seq": 1842,
  "readings": [
    {"ts": "2026-10-11T03:15:00Z", "temp_c": 4.8, "humidity": 71.0, "ambient_c": 31.2,
     "door_open": false, "reefer_on": true, "speed_kmh": 52.0, "harsh_events": 0,
     "solar_radiation": 640.0, "lat": -6.91, "lon": 107.61}
  ]
}
```

- `ts` **wajib UTC** (akhiran `Z` atau `+00:00`), satu bacaan per menit.
- Field bacaan = `TelemetryReading` (`backend/app/schemas.py`); `lat`/`lon` opsional.
- `seq` naik per batch per perangkat (untuk diagnosis kehilangan paket; server tidak menolak lompatan).
- Duplikat (`truck_key`, `ts` sama) diabaikan: kirim ulang batch aman.
- Bacaan yang tidak lolos validasi dibuang satu per satu dan dicatat di log ingest; sisa batch tetap
  disimpan.

## Payload status

```json
{"schema": "coldtrack.status.v1", "device_id": "DEV-001", "online": true,
 "firmware": "1.5.0", "gateway_version": "0.9.3", "battery_v": 2.71, "ts": "2026-10-11T03:15:00Z"}
```

LWT yang dipasang saat connect: payload yang sama dengan `"online": false`.

## Keamanan

Dev: satu akun `simulator` (publish) dan `ingest` (subscribe), password dari `.env`.
Produksi (Fase 6): TLS port 8883, akun per perangkat, ACL `pattern write coldtrack/v1/%u/#`
(username = `truck_key`); port 1883 hanya di jaringan internal.

## Jalur alternatif: webhook vendor

Telematika reefer vendor yang sudah ada dapat mengirim lewat HTTP:
`POST /api/v1/ingest/vendor/{vendor}` dengan header `X-API-Key`. Adapter (`app/adapters/`) menerjemahkan
format vendor ke `TelemetryReading`, lalu jalur penyimpanan sama dengan MQTT.
