"""Worker ingest: MQTT -> TimescaleDB (docs/device_contract.md).

  python -m app.workers.ingest

Env: MQTT_HOST (mosquitto), MQTT_PORT (1883), MQTT_USER (ingest), MQTT_PASSWORD, DATABASE_URL.
Berlangganan QoS 1 ke coldtrack/v1/+/telemetry dan coldtrack/v1/+/status dengan sesi persisten
(clean_start False) supaya pesan yang datang saat worker restart tidak hilang dari broker.
"""

import json
import logging
import os
import signal

import paho.mqtt.client as mqtt

from app.db import conn
from app.ingest.store import (
    resolve_truck,
    store_readings,
    store_status,
    validate_readings,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("coldtrack.ingest")

TOPIK = [("coldtrack/v1/+/telemetry", 1), ("coldtrack/v1/+/status", 1)]


def tangani(topic: str, payload: bytes) -> None:
    bagian = topic.split("/")
    if len(bagian) != 4:
        logger.warning("topik tidak dikenal: %s", topic)
        return
    key, jenis = bagian[2], bagian[3]
    try:
        body = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("payload bukan JSON di %s", topic)
        return
    with conn() as c:
        truck_id = resolve_truck(c.cursor(), key)
        if truck_id is None:
            logger.warning("truk tak dikenal: %s", key)
            return
        if jenis == "status":
            store_status(c, truck_id, body)
            return
        if jenis != "telemetry" or body.get("schema") != "coldtrack.telemetry.v1":
            logger.warning("skema tidak didukung di %s: %s", topic, body.get("schema"))
            return
        ok, errors = validate_readings(body.get("readings", []))
        for e in errors:
            logger.warning("%s: %s", truck_id, e)
        baru = store_readings(c, truck_id, body.get("device_id"), body.get("seq"), ok)
        logger.info("%s: %d bacaan diterima, %d baru, %d ditolak", truck_id, len(ok), baru, len(errors))


def main() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="coldtrack-ingest",
                         protocol=mqtt.MQTTv5)
    client.username_pw_set(os.environ.get("MQTT_USER", "ingest"), os.environ.get("MQTT_PASSWORD", ""))
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    def on_connect(cl, userdata, flags, reason_code, properties):
        logger.info("terhubung ke broker: %s", reason_code)
        cl.subscribe(TOPIK)

    def on_message(cl, userdata, msg):
        try:
            tangani(msg.topic, msg.payload)
        except Exception:
            logger.exception("gagal memproses pesan di %s", msg.topic)

    client.on_connect = on_connect
    client.on_message = on_message
    props = mqtt.Properties(mqtt.PacketTypes.CONNECT)
    props.SessionExpiryInterval = 3600            # sesi persisten 1 jam
    # connect_async + retry_first_connection: worker tetap hidup bila broker belum siap saat start
    client.connect_async(os.environ.get("MQTT_HOST", "localhost"), int(os.environ.get("MQTT_PORT", "1883")),
                         clean_start=False, properties=props)
    signal.signal(signal.SIGTERM, lambda *_: client.disconnect())
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
