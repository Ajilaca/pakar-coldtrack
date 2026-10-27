"""Driver ARM ColdTrack: sampel per menit -> chip (hitung sekali) -> MQTT berisi bacaan + hasil edge tersegel.

Untuk demo tanpa sensor sungguhan, driver memutar ulang trip v4 milik satu truk armada seed
(backend/data/fleet/trips.json, kolom sumber_trip_v4) dengan siklus kerja kompresor sintetis B9. Cloud
(app/edge.py) memverifikasi MAC dan rantai lalu memakai hasil chip tanpa menghitung ulang.

  python -m hw.driver.edge_driver --truck "B 3036 WN" --chip golden --kunci <64 hex>

Truk yang diputar driver ini harus dilewati simulator cloud (env SIM_LEWATI di virtual-trucks), dan kunci
perangkatnya harus terdaftar di EDGE_KEYS worker-ingest. Env: MQTT_HOST, MQTT_PORT, MQTT_USER (simulator),
MQTT_PASSWORD, API_URL, SIM_SPEED, SIM_ANCHOR (sama dengan stack compose).
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from hw.driver.chip import ChipAxi, ChipGolden, ChipSpi, Sampel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("coldtrack.edge_driver")

FLEET = ROOT / "backend" / "data" / "fleet"
MODEL = ROOT / "bench/results/local-cpu/B10/b9_xgb_chip_v5_context_synthetic_duty.json"


def trip_truk(truck_id: str) -> tuple[dict, dict, pd.DataFrame, dict]:
    """Trip seed truk -> (trip, device, DataFrame trip v4 urut menit, array kuantisasi)."""
    from hw.golden import trees as ph
    from hw.golden.check_trees import duty_trip

    trip = next(t for t in json.loads((FLEET / "trips.json").read_text(encoding="utf-8")) if t["truck_id"] == truck_id)
    device = next(d for d in json.loads((FLEET / "devices.json").read_text(encoding="utf-8")) if d["truck_id"] == truck_id)
    tid = int(trip["sumber_trip_v4"])
    df = pd.read_parquet(ROOT / "data/processed/v4_seed1000_700trips.parquet")
    g = df[df.trip_id == tid].sort_values("minute").reset_index(drop=True)
    return trip, device, g, ph.kuantisasi_trip(g, duty_trip(g, tid))


def bacaan(q: dict, t: int, ts: pd.Timestamp) -> dict | None:
    """Bacaan kontrak MQTT dari nilai yang sama persis dengan yang masuk chip (satuan rekaman / 100)."""
    if q["nan"][t]:
        return None
    return {"ts": ts.isoformat().replace("+00:00", "Z"), "temp_c": int(q["temp"][t]) / 100,
            "humidity": int(q["rh"][t]) / 100, "ambient_c": int(q["amb"][t]) / 100, "door_open": bool(q["door"][t]),
            "reefer_on": bool(q["reefer"][t]), "speed_kmh": int(q["speed"][t]) / 100,
            "harsh_events": int(q["harsh"][t]), "solar_radiation": int(q["solar"][t]) / 16}


def sampel(q: dict, t: int, ts: pd.Timestamp) -> Sampel:
    return Sampel(seq=t, ts=int(ts.timestamp()), temp=None if q["nan"][t] else int(q["temp"][t]), rh=int(q["rh"][t]),
                  amb=int(q["amb"][t]), solar=int(q["solar"][t]), speed=int(q["speed"][t]), door=bool(q["door"][t]),
                  reefer=bool(q["reefer"][t]), duty=int(q["duty"][t]), harsh=int(q["harsh"][t]), hour=int(q["hour"][t]))


def main() -> None:
    import httpx
    import paho.mqtt.client as mqtt
    from app import clock
    from app.inference import cargo_params
    from app.ingest.store import truck_key

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--truck", required=True, help="nomor polisi truk seed, mis. 'B 3036 WN'")
    ap.add_argument("--chip", choices=["golden", "axi", "spi"], default="golden")
    ap.add_argument("--kunci", default=os.environ.get("EDGE_KEY", ""), help="kunci HMAC perangkat, 64 hex")
    a = ap.parse_args()
    kunci = bytes.fromhex(a.kunci)
    if len(kunci) != 32:
        sys.exit("--kunci harus 32 byte (64 hex), sama dengan EDGE_KEYS di worker-ingest")

    trip, device, g, q = trip_truk(a.truck)
    prod = cargo_params(trip["cargo_profile"], trip["mass_kg"])
    chip = {"golden": lambda: ChipGolden(MODEL), "axi": ChipAxi, "spi": ChipSpi}[a.chip]()
    key = truck_key(a.truck)
    cl = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"edge-{key}")
    cl.username_pw_set(os.environ.get("MQTT_USER", "simulator"), os.environ.get("MQTT_PASSWORD", ""))
    status = {"schema": "coldtrack.status.v1", "device_id": device["id"], "firmware": device["firmware"],
              "gateway_version": device["gateway_version"], "battery_v": device["battery_v"]}
    cl.will_set(f"coldtrack/v1/{key}/status", json.dumps({**status, "online": False}), qos=1, retain=True)
    cl.connect(os.environ.get("MQTT_HOST", "localhost"), int(os.environ.get("MQTT_PORT", "1883")))
    cl.loop_start()
    cl.publish(f"coldtrack/v1/{key}/status", json.dumps({**status, "online": True, "ts": clock.now().isoformat()}),
               qos=1, retain=True)
    api = httpx.Client(base_url=os.environ.get("API_URL", "http://localhost:8000"), timeout=30)
    jeda, seq_mqtt = clock.wall_seconds_for(60), 0
    logger.info("%s: chip %s, trip v4 %s (%d menit), SIM_SPEED=%s", a.truck, a.chip, trip["sumber_trip_v4"], len(g),
                clock.speed())
    while True:
        r = api.post("/api/v1/trips", json={"truck_id": a.truck, "cargo_profile": trip["cargo_profile"],
                                            "mass_kg": trip["mass_kg"], "depot_id": trip["depot_id"],
                                            "started_at": clock.now().isoformat()})
        r.raise_for_status()
        trip_id = r.json()["trip_id"]
        chip.mulai_trip(prod, kunci)
        for t in range(len(g)):
            t0 = time.monotonic()
            ts = pd.Timestamp(clock.now()).floor("min")
            h = chip.proses(sampel(q, t, ts))
            b = bacaan(q, t, ts)
            e = {"rek": h.rek.hex(), "rantai": h.rantai.hex(), "paket": h.paket.hex(), "mac": h.mac.hex(), "skor": h.skor}
            payload = {"schema": "coldtrack.telemetry.v1", "device_id": device["id"], "seq": seq_mqtt + 1, "readings": []}
            if b is not None:
                payload["readings"] = [{**b, "edge": e}]
            else:                                 # bacaan suhu gagal: rekaman tetap disegel, rantai tidak terputus
                payload["rekaman_tanpa_bacaan"] = [e]
            seq_mqtt += 1
            cl.publish(f"coldtrack/v1/{key}/telemetry", json.dumps(payload), qos=1)
            if t % 15 == 0:
                logger.info("%s menit %d: status %d, diagnosis %s", a.truck, t, h.status,
                            h.kelas if h.diag_valid else "-")
            time.sleep(max(0.0, jeda - (time.monotonic() - t0)))
        api.patch(f"/api/v1/trips/{trip_id}", json={"ended_at": clock.now().isoformat()})


if __name__ == "__main__":
    main()
