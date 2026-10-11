"""Fase 2 armada -- integrasi sungguhan: MQTT (Mosquitto) -> worker-ingest -> TimescaleDB, dan webhook vendor.

Butuh stack compose berjalan (db, mosquitto, api, worker-ingest). Dilewati kecuali COLDTRACK_FLEET_IT=1.

  COLDTRACK_FLEET_IT=1 INGEST_TEST_KEY=<kunci generic_json> pytest tests/test_fleet_integrasi.py

Bacaan uji memakai ts di tahun 2030 (tidak bertabrakan dengan simulator) dan dihapus lagi di akhir.
Urutan pesan QoS 1 pada satu topik dari satu klien dijaga broker, jadi "pesan penanda" yang dikirim
sesudah pesan uji membuktikan pesan uji sudah diproses worker.
"""

import json
import os
import time
from datetime import UTC, datetime, timedelta

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("COLDTRACK_FLEET_IT") != "1",
                                reason="integrasi armada: set COLDTRACK_FLEET_IT=1 dengan stack compose berjalan")

TRUK, KEY, DEV = "B 3036 WN", "B3036WN", "DEV-001"
T0 = datetime(2030, 1, 1, 6, 0, tzinfo=UTC)
TUNGGU_S = 20


def bacaan(menit: int, **ubah) -> dict:
    return {"ts": (T0 + timedelta(minutes=menit)).isoformat().replace("+00:00", "Z"), "temp_c": 4.0 + menit / 100,
            "humidity": 70.0, "ambient_c": 30.0, "door_open": False, "reefer_on": True, "speed_kmh": 40.0,
            "harsh_events": 0, "solar_radiation": 500.0, **ubah}


@pytest.fixture(scope="module")
def db():
    psycopg = pytest.importorskip("psycopg")
    c = psycopg.connect(os.environ.get("DATABASE_URL", "postgresql://coldtrack:coldtrack@localhost:5432/coldtrack"),
                        autocommit=True)
    hapus = "DELETE FROM telemetry WHERE truck_id = %s AND ts >= %s AND ts < %s"
    c.execute(hapus, (TRUK, T0 - timedelta(days=1), T0 + timedelta(days=1)))
    yield c
    c.execute(hapus, (TRUK, T0 - timedelta(days=1), T0 + timedelta(days=1)))
    c.execute("UPDATE devices SET online = true WHERE id = %s", (DEV,))
    c.close()


@pytest.fixture(scope="module")
def mq():
    mqtt = pytest.importorskip("paho.mqtt.client")
    cl = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="coldtrack-it")
    cl.username_pw_set("simulator", os.environ.get("MQTT_SIMULATOR_PASSWORD", "simulator-dev"))
    cl.connect(os.environ.get("MQTT_HOST", "localhost"), int(os.environ.get("MQTT_PORT", "1883")))
    cl.loop_start()
    yield cl
    cl.loop_stop()
    cl.disconnect()


def kirim(mq, readings: list[dict], seq: int, jenis: str = "telemetry", body: dict | None = None) -> None:
    payload = body or {"schema": "coldtrack.telemetry.v1", "device_id": DEV, "seq": seq, "readings": readings}
    mq.publish(f"coldtrack/v1/{KEY}/{jenis}", json.dumps(payload), qos=1).wait_for_publish(5)


def jumlah(db, dari: int, sampai: int) -> int:
    return db.execute("SELECT count(*) FROM telemetry WHERE truck_id = %s AND ts >= %s AND ts <= %s",
                      (TRUK, T0 + timedelta(minutes=dari), T0 + timedelta(minutes=sampai))).fetchone()[0]


def tunggu(cek, batas_s: float = TUNGGU_S) -> bool:
    akhir = time.monotonic() + batas_s
    while time.monotonic() < akhir:
        if cek():
            return True
        time.sleep(0.25)
    return False


def penanda(db, mq, menit: int, seq: int) -> None:
    """Kirim satu bacaan baru lalu tunggu tersimpan: semua pesan sebelumnya sudah diproses."""
    kirim(mq, [bacaan(menit)], seq)
    assert tunggu(lambda: jumlah(db, menit, menit) == 1), f"penanda menit {menit} tidak tersimpan"


def test_batch_mqtt_tersimpan(db, mq):
    kirim(mq, [bacaan(m) for m in range(10)], seq=1)
    assert tunggu(lambda: jumlah(db, 0, 9) == 10)
    row = db.execute("SELECT device_id, seq, temp_c FROM telemetry WHERE truck_id = %s AND ts = %s",
                     (TRUK, T0 + timedelta(minutes=3))).fetchone()
    assert row == (DEV, 1, pytest.approx(4.03))


def test_kirim_ulang_tidak_menggandakan(db, mq):
    kirim(mq, [bacaan(m) for m in range(10)], seq=1)          # buffer perangkat dikirim ulang
    kirim(mq, [bacaan(m) for m in range(5, 15)], seq=2)       # tumpang tindih sebagian
    penanda(db, mq, 100, seq=3)
    assert jumlah(db, 0, 14) == 15


def test_data_terlambat_diterima(db, mq):
    kirim(mq, [bacaan(m) for m in range(-40, -30)], seq=4)    # ts lebih tua dari bacaan yang sudah ada
    penanda(db, mq, 101, seq=5)
    assert jumlah(db, -40, -31) == 10


def test_bacaan_rusak_dibuang_sisanya_disimpan(db, mq):
    kirim(mq, [bacaan(200), bacaan(201, temp_c="rusak"), {**bacaan(202), "ts": "2030-01-01T09:22:00"},
               bacaan(203)], seq=6)
    penanda(db, mq, 204, seq=7)
    assert jumlah(db, 200, 203) == 2


def test_status_perangkat_offline_lalu_online(db, mq):
    def online():
        return db.execute("SELECT online FROM devices WHERE id = %s", (DEV,)).fetchone()[0]

    def baterai():
        return db.execute("SELECT battery_v FROM devices WHERE id = %s", (DEV,)).fetchone()[0]

    # Keadaan awal harus BEDA dari yang diharapkan; tanpa ini tunggu() bisa lolos sebelum pesan diproses
    # (online bawaan seed = false, dan LWT simulator yang dimatikan juga menulis false).
    db.execute("UPDATE devices SET online = true, battery_v = 3.0 WHERE id = %s", (DEV,))
    st = {"schema": "coldtrack.status.v1", "device_id": DEV, "online": False, "firmware": "1.5.0",
          "battery_v": 2.31, "ts": T0.isoformat()}
    kirim(mq, [], 0, jenis="status", body=st)                 # tanpa retain: tidak mengotori broker
    assert tunggu(lambda: online() is False and baterai() == pytest.approx(2.31))
    kirim(mq, [], 0, jenis="status", body={**st, "online": True})
    assert tunggu(lambda: online() is True)


def test_webhook_vendor(db):
    httpx = pytest.importorskip("httpx")
    api = httpx.Client(base_url=os.environ.get("API_URL", "http://localhost:8000"), timeout=15)
    body = {"readings": [{"truck_id": TRUK, "device_id": DEV, **bacaan(m)} for m in (300, 301)]
            + [{"truck_id": "Z 0000 ZZ", **bacaan(302)}]}
    assert api.post("/api/v1/ingest/vendor/generic_json", json=body, headers={"X-API-Key": "salah"}).status_code == 401
    assert api.post("/api/v1/ingest/vendor/tak_ada", json=body).status_code == 404
    kunci = os.environ.get("INGEST_TEST_KEY")
    if not kunci:
        pytest.skip("INGEST_TEST_KEY tidak di-set (kunci generic_json di INGEST_API_KEYS api)")
    r = api.post("/api/v1/ingest/vendor/generic_json", json=body, headers={"X-API-Key": kunci})
    assert r.status_code == 200, r.text
    assert r.json() == {"diterima": 2, "baru": 2, "ditolak": [], "truk_tak_dikenal": ["Z 0000 ZZ"]}
    r = api.post("/api/v1/ingest/vendor/generic_json", json=body, headers={"X-API-Key": kunci})
    assert r.json()["baru"] == 0                                # kirim ulang: dedupe
    assert jumlah(db, 300, 301) == 2


# --- Fase 3: publish -> prediksi muncul (butuh worker-infer berjalan dengan SIM_SPEED/SIM_ANCHOR yang sama) ---

TRUK_IT, KEY_IT = "IT 0001 ZZ", "IT0001ZZ"


@pytest.fixture
def truk_uji(db):
    from app import clock

    now = clock.now().replace(second=0, microsecond=0)
    db.execute("INSERT INTO trucks (id, depot_id, label) SELECT %s, id, 'Truk uji integrasi' FROM depots LIMIT 1",
               (TRUK_IT,))
    trip_id = db.execute("INSERT INTO trips (truck_id, cargo_profile, mass_kg, cargo_value_idr, started_at) "
                         "VALUES (%s, 'vaksin_2_8C', 800, 1000, %s) RETURNING id",
                         (TRUK_IT, now - timedelta(minutes=80))).fetchone()[0]
    yield now, trip_id
    for tabel in ("notifications", "incident_events", "incidents", "predictions", "truck_state", "telemetry", "trips"):
        if tabel == "incident_events":
            db.execute("DELETE FROM incident_events WHERE incident_id IN (SELECT id FROM incidents WHERE truck_id = %s)",
                       (TRUK_IT,))
        else:
            db.execute(f"DELETE FROM {tabel} WHERE truck_id = %s", (TRUK_IT,))
    db.execute("DELETE FROM trucks WHERE id = %s", (TRUK_IT,))


def test_publish_lalu_prediksi_muncul(db, mq, truk_uji):
    now, trip_id = truk_uji
    rd = [{**bacaan(0), "ts": (now - timedelta(minutes=70 - m)).isoformat(), "temp_c": 5.0}
          for m in range(70)]
    mq.publish(f"coldtrack/v1/{KEY_IT}/telemetry", json.dumps(
        {"schema": "coldtrack.telemetry.v1", "device_id": None, "seq": 1, "readings": rd}), qos=1).wait_for_publish(5)

    def prediksi():
        return db.execute("SELECT status, forecast, failure_label, model_version FROM predictions "
                          "WHERE truck_id = %s AND trip_id = %s ORDER BY ts DESC LIMIT 1",
                          (TRUK_IT, trip_id)).fetchone()

    assert tunggu(lambda: prediksi() is not None, 30), "worker-infer tidak menulis prediksi"
    status, forecast, label, versi = prediksi()
    assert status in ("AMAN", "WASPADA", "KRITIS", "DATA_TIDAK_LENGKAP")
    assert set(forecast) == {"t15", "t30", "t60"} and label and versi
    st = db.execute("SELECT status, sensor_health->>'grade', trip_id FROM truck_state WHERE truck_id = %s",
                    (TRUK_IT,)).fetchone()
    assert st[0] == status and st[1] in ("Sehat", "Perlu cek", "Ganti", "Data kurang") and st[2] == trip_id
