"""Simulator truk virtual: memutar ulang trip seed (backend/data/fleet/) lewat MQTT, waktu simulasi.

  python -m app.workers.virtual_trucks

Env: MQTT_HOST, MQTT_PORT, MQTT_USER (simulator), MQTT_PASSWORD, API_URL (http://api:8000),
     SIM_SPEED / SIM_ANCHOR (app/clock.py), SIM_SEED.

- Satu menit simulasi = satu bacaan per truk; ts = jam bersama (app/clock.now) dibulatkan ke menit.
- Putus sinyal: tiap truk punya peluang mulai putus per menit (P_PUTUS) selama 3-25 menit; selama itu
  bacaan DISANGGA lalu dikirim sebagai satu batch saat tersambung kembali (perilaku logger sungguhan).
- Dua truk perangkatnya "mati" setelah 60-120 menit: status offline (retained) lalu berhenti kirim,
  supaya dashboard menampilkan TIDAK_ADA_DATA.
- Trip dibuka lewat POST /api/v1/trips; saat data trip habis, trip ditutup dan diputar ulang.
"""

import json
import logging
import os
import random
import time
from pathlib import Path

import httpx
import paho.mqtt.client as mqtt
import pandas as pd

from app import clock
from app.ingest.store import truck_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("coldtrack.sim")

FLEET = Path(__file__).resolve().parents[2] / "data" / "fleet"
P_PUTUS = 0.01
N_MATI = 2
KOLOM = ["temp_c", "humidity", "ambient_c", "door_open", "reefer_on", "speed_kmh", "harsh_events",
         "solar_radiation", "lat", "lon"]


class TrukVirtual:
    def __init__(self, truck: dict, device: dict, trip: dict, rows: pd.DataFrame, rng: random.Random,
                 mati_pada: int | None):
        self.id, self.key, self.device, self.trip, self.rows = truck["id"], truck_key(truck["id"]), device, trip, rows
        self.rng, self.mati_pada = rng, mati_pada
        self.k, self.menit, self.seq, self.buffer, self.putus_sisa, self.trip_id = 0, 0, 0, [], 0, None
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sim-{self.key}")
        self.client.username_pw_set(os.environ.get("MQTT_USER", "simulator"), os.environ.get("MQTT_PASSWORD", ""))
        self.client.will_set(self.topik("status"), self.status(False), qos=1, retain=True)

    def topik(self, jenis: str) -> str:
        return f"coldtrack/v1/{self.key}/{jenis}"

    def status(self, online: bool) -> str:
        return json.dumps({"schema": "coldtrack.status.v1", "device_id": self.device["id"], "online": online,
                           "firmware": self.device["firmware"], "gateway_version": self.device["gateway_version"],
                           "battery_v": self.device["battery_v"], "ts": clock.now().isoformat()})

    def mulai(self, api: httpx.Client) -> None:
        self.client.connect_async(os.environ.get("MQTT_HOST", "localhost"), int(os.environ.get("MQTT_PORT", "1883")))
        self.client.loop_start()
        self.client.publish(self.topik("status"), self.status(True), qos=1, retain=True)
        self.buka_trip(api)

    def buka_trip(self, api: httpx.Client) -> None:
        r = api.post("/api/v1/trips", json={"truck_id": self.id, "cargo_profile": self.trip["cargo_profile"],
                                            "mass_kg": self.trip["mass_kg"], "depot_id": self.trip["depot_id"],
                                            "started_at": clock.now().isoformat()})
        r.raise_for_status()
        self.trip_id, self.k = r.json()["trip_id"], 0

    def langkah(self, ts: pd.Timestamp, api: httpx.Client) -> None:
        if self.mati_pada is not None and self.menit >= self.mati_pada:
            if self.menit == self.mati_pada:
                self.client.publish(self.topik("status"), self.status(False), qos=1, retain=True)
                logger.info("%s: perangkat mati (simulasi)", self.id)
            self.menit += 1
            return
        if self.k >= len(self.rows):
            api.patch(f"/api/v1/trips/{self.trip_id}", json={"ended_at": ts.isoformat()})
            self.buka_trip(api)
        r = self.rows.iloc[self.k]
        bacaan = {"ts": ts.isoformat(), **{c: (bool(r[c]) if c in ("door_open", "reefer_on") else
                                                (None if pd.isna(r[c]) else float(r[c]))) for c in KOLOM}}
        if bacaan["temp_c"] is not None:          # paket hilang di data v4 = tidak ada bacaan menit itu
            bacaan["harsh_events"] = int(bacaan["harsh_events"] or 0)
            self.buffer.append(bacaan)
        self.k, self.menit = self.k + 1, self.menit + 1
        if self.putus_sisa == 0 and self.rng.random() < P_PUTUS:
            self.putus_sisa = self.rng.randint(3, 25)
        if self.putus_sisa > 0:
            self.putus_sisa -= 1
            return
        if self.buffer:
            self.seq += 1
            payload = {"schema": "coldtrack.telemetry.v1", "device_id": self.device["id"], "seq": self.seq,
                       "readings": self.buffer}
            self.client.publish(self.topik("telemetry"), json.dumps(payload), qos=1)
            self.buffer = []


def main() -> None:
    rng = random.Random(int(os.environ.get("SIM_SEED", "7")))
    rows = pd.read_parquet(FLEET / "telemetry.parquet")
    trucks = json.loads((FLEET / "trucks.json").read_text(encoding="utf-8"))
    devices = {d["truck_id"]: d for d in json.loads((FLEET / "devices.json").read_text(encoding="utf-8"))}
    trips = {t["truck_id"]: t for t in json.loads((FLEET / "trips.json").read_text(encoding="utf-8"))}
    mati = set(rng.sample([t["id"] for t in trucks], N_MATI))
    armada = [TrukVirtual(t, devices[t["id"]], trips[t["id"]], rows[rows.truck_id == t["id"]].reset_index(drop=True),
                          random.Random(rng.random()), rng.randint(60, 120) if t["id"] in mati else None)
              for t in trucks]
    api = httpx.Client(base_url=os.environ.get("API_URL", "http://localhost:8000"), timeout=30)
    for t in armada:
        t.mulai(api)
    logger.info("%d truk virtual berjalan, SIM_SPEED=%s", len(armada), clock.speed())
    jeda = clock.wall_seconds_for(60)
    while True:
        t0 = time.monotonic()
        ts = pd.Timestamp(clock.now()).floor("min")
        for t in armada:
            t.langkah(ts, api)
        time.sleep(max(0.0, jeda - (time.monotonic() - t0)))


if __name__ == "__main__":
    main()
