"""Fase 2 armada -- bagian ingest yang tidak butuh DB/broker (integrasi DB diuji terpisah)."""

from datetime import UTC, datetime, timedelta

from app import clock
from app.adapters import REGISTRY
from app.ingest.store import truck_key, validate_readings
from app.routers.ingest import nilai_muatan

BACAAN = {"ts": "2026-10-11T03:15:00Z", "temp_c": 4.8, "humidity": 71.0, "ambient_c": 31.2, "door_open": False,
          "reefer_on": True, "speed_kmh": 52.0, "harsh_events": 0, "solar_radiation": 640.0}


def test_truck_key_tanpa_spasi_huruf_besar():
    assert truck_key("b 9012 kq") == "B9012KQ"


def test_validasi_per_bacaan_dan_wajib_utc():
    ok, err = validate_readings([BACAAN, {**BACAAN, "temp_c": "rusak"}, {**BACAAN, "ts": "2026-10-11T03:16:00"}])
    assert len(ok) == 1 and len(err) == 2
    assert any("zona waktu" in e for e in err)


def test_adapter_generic_json_mengelompokkan_per_truk():
    body = ('{"readings": [' + ",".join(
        f'{{"truck_id": "{t}", "device_id": "DEV-1", "ts": "2026-10-11T03:1{i}:00Z", "temp_c": 4.0, '
        f'"humidity": 70, "ambient_c": 30, "door_open": false, "reefer_on": true, "speed_kmh": 40}}'
        for i, t in enumerate(["B 1 A", "B 1 A", "D 2 B"])) + "]}").encode()
    batches = REGISTRY["generic_json"].normalize(body, "application/json")
    assert {b.truck_id: len(b.readings) for b in batches} == {"B 1 A": 2, "D 2 B": 1}
    ok, err = validate_readings(batches[0].readings)
    assert len(ok) == 2 and not err


def test_adapter_generic_csv_mengubah_boolean():
    body = (b"truck_id,device_id,ts,temp_c,humidity,ambient_c,door_open,reefer_on,speed_kmh\n"
            b"B 1 A,DEV-1,2026-10-11T03:15:00Z,4.5,70,30,1,true,40\n")
    (b,) = REGISTRY["generic_csv"].normalize(body, "text/csv")
    ok, err = validate_readings(b.readings)
    assert not err and ok[0].door_open is True and ok[0].reefer_on is True


def test_nilai_muatan_dari_harga_per_kg_asumsi():
    assert nilai_muatan("daging_beku_-18C", 1000) == 140_000 * 1000
    assert nilai_muatan("profil_tak_ada", 1000) is None


def test_jam_simulasi_dipercepat(monkeypatch):
    monkeypatch.setenv("SIM_SPEED", "60")
    anchor = datetime.now(UTC) - timedelta(minutes=1)
    monkeypatch.setenv("SIM_ANCHOR", anchor.isoformat())
    selisih = (clock.now() - anchor).total_seconds()
    assert 3500 < selisih < 3700                    # 1 menit dinding = 60 menit simulasi
    assert clock.wall_seconds_for(60) == 1.0
    monkeypatch.setenv("SIM_SPEED", "1")
    assert abs((clock.now() - datetime.now(UTC)).total_seconds()) < 1
