"""Simpan bacaan dan status perangkat ke TimescaleDB.

- Dedupe lewat PK (truck_id, ts): kirim ulang batch dari buffer perangkat aman.
- Bacaan divalidasi satu per satu (TelemetryReading); yang gagal dibuang dan dicatat, sisanya disimpan.
- ts wajib ber-zona waktu (UTC); ts tanpa zona ditolak.
- Setelah ada bacaan baru: NOTIFY telemetry_arrived '<truck_id>' (dipakai worker inferensi).
"""

import logging
from typing import Any

from pydantic import ValidationError

from app.schemas import TelemetryReading

logger = logging.getLogger("coldtrack.ingest")

INSERT_TELEMETRY = (
    "INSERT INTO telemetry (truck_id, ts, device_id, seq, temp_c, humidity, ambient_c, door_open, reefer_on, "
    "speed_kmh, harsh_events, solar_radiation, lat, lon) VALUES (%(truck_id)s, %(ts)s, %(device_id)s, %(seq)s, "
    "%(temp_c)s, %(humidity)s, %(ambient_c)s, %(door_open)s, %(reefer_on)s, %(speed_kmh)s, %(harsh_events)s, "
    "%(solar_radiation)s, %(lat)s, %(lon)s) ON CONFLICT (truck_id, ts) DO NOTHING"
)


def truck_key(truck_id: str) -> str:
    """Identitas truk di topik MQTT: nomor polisi tanpa spasi, huruf besar."""
    return truck_id.replace(" ", "").upper()


def resolve_truck(cur, key: str) -> str | None:
    row = cur.execute("SELECT id FROM trucks WHERE upper(replace(id, ' ', '')) = %s", (key.upper(),)).fetchone()
    return row[0] if row else None


def validate_readings(raw: list[dict[str, Any]]) -> tuple[list[TelemetryReading], list[str]]:
    ok, errors = [], []
    for i, r in enumerate(raw):
        try:
            rd = TelemetryReading.model_validate(r)
        except ValidationError as e:
            errors.append(f"bacaan {i}: {e.errors()[0]['msg']}")
            continue
        if rd.ts.tzinfo is None:
            errors.append(f"bacaan {i}: ts tanpa zona waktu (wajib UTC)")
            continue
        ok.append(rd)
    return ok, errors


def store_readings(conn, truck_id: str, device_id: str | None, seq: int | None,
                   readings: list[TelemetryReading]) -> int:
    """Simpan bacaan valid; kembalikan jumlah baris BARU (duplikat tidak dihitung)."""
    if not readings:
        return 0
    rows = [{"truck_id": truck_id, "device_id": device_id, "seq": seq, **r.model_dump(include={
        "ts", "temp_c", "humidity", "ambient_c", "door_open", "reefer_on", "speed_kmh", "harsh_events",
        "solar_radiation", "lat", "lon"})} for r in readings]
    with conn.cursor() as cur:
        baru = 0
        for row in rows:                       # rowcount per baris: 1 = baru, 0 = duplikat
            cur.execute(INSERT_TELEMETRY, row)
            baru += cur.rowcount
        if baru:
            cur.execute("SELECT pg_notify('telemetry_arrived', %s)", (truck_id,))
    conn.commit()
    return baru


def store_status(conn, truck_id: str, payload: dict[str, Any]) -> None:
    """Perbarui perangkat dari topik status (retained + LWT)."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE devices SET online = %(online)s, firmware = coalesce(%(firmware)s, firmware), "
            "gateway_version = coalesce(%(gateway_version)s, gateway_version), "
            "battery_v = coalesce(%(battery_v)s, battery_v), last_status_at = coalesce(%(ts)s::timestamptz, now()) "
            "WHERE id = %(device_id)s AND truck_id = %(truck_id)s",
            {"truck_id": truck_id, "device_id": payload.get("device_id"), "online": bool(payload.get("online")),
             "firmware": payload.get("firmware"), "gateway_version": payload.get("gateway_version"),
             "battery_v": payload.get("battery_v"), "ts": payload.get("ts")},
        )
        if cur.rowcount == 0:
            logger.warning("status untuk perangkat tak dikenal: %s / %s", truck_id, payload.get("device_id"))
    conn.commit()
