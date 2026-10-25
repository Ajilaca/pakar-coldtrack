# docker/

Konfigurasi pendukung untuk `docker-compose.yml` di root repo.

| Path | Isi |
|---|---|
| `mosquitto/mosquitto.conf` | Broker MQTT dev, listener 1883, login dan ACL wajib. TLS 8883 belum ada |
| `mosquitto/acl` | Dua akun dev: `ingest` (baca `coldtrack/v1/#`) dan `simulator` (tulis `coldtrack/v1/#`). Akun per perangkat direncanakan untuk deploy |
| `mosquitto/entrypoint.sh` | Membuat berkas password dari `MQTT_INGEST_PASSWORD` dan `MQTT_SIMULATOR_PASSWORD` saat kontainer mulai |

Layanan di compose: `db` (TimescaleDB), `mosquitto`, `api`, `worker-ingest`, `worker-infer`,
`frontend`, dan `virtual-trucks` (hanya profil `dev`). `docker-compose.dev.yml` adalah compose terpisah yang
menjalankan backend saja dengan kode di-mount. Isi variabel dari `.env.example`.
