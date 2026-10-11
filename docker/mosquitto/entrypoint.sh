#!/bin/sh
# Bangkitkan berkas password dari env saat start (nilai dev ada di .env.example, bukan di image).
set -e
: "${MQTT_INGEST_PASSWORD:?MQTT_INGEST_PASSWORD wajib}"
: "${MQTT_SIMULATOR_PASSWORD:?MQTT_SIMULATOR_PASSWORD wajib}"
mkdir -p /mosquitto/config
cp /etc/coldtrack/mosquitto.conf /etc/coldtrack/acl /mosquitto/config/
rm -f /mosquitto/config/passwd && touch /mosquitto/config/passwd
mosquitto_passwd -b /mosquitto/config/passwd ingest "$MQTT_INGEST_PASSWORD"
mosquitto_passwd -b /mosquitto/config/passwd simulator "$MQTT_SIMULATOR_PASSWORD"
chown -R mosquitto:mosquitto /mosquitto/config /mosquitto/data 2>/dev/null || true
chmod 0700 /mosquitto/config/passwd
exec mosquitto -c /mosquitto/config/mosquitto.conf
