"""Isi depo, truk, dan perangkat armada demo dari backend/data/fleet/*.json (ml/preprocess/export_fleet.py).

  python -m app.db.seed          (setelah app.db.migrate; idempoten)

Trip TIDAK diisi di sini: dibuka oleh simulator truk virtual lewat API saat perjalanan mulai.
Semua data perangkat dan rute adalah SINTETIK (docs/fleet_assumptions.md).
"""

import json
from pathlib import Path

from app.db import conn

FLEET = Path(__file__).resolve().parents[2] / "data" / "fleet"


def load(name: str) -> list[dict]:
    return json.loads((FLEET / f"{name}.json").read_text(encoding="utf-8"))


def main() -> None:
    with conn() as c, c.cursor() as cur:
        cur.executemany(
            "INSERT INTO depots (id, name, city, lat, lon) VALUES (%(id)s, %(name)s, %(city)s, %(lat)s, %(lon)s) "
            "ON CONFLICT (id) DO NOTHING", load("depots"))
        cur.executemany(
            "INSERT INTO trucks (id, depot_id, label) VALUES (%(id)s, %(depot_id)s, %(label)s) "
            "ON CONFLICT (id) DO NOTHING", load("trucks"))
        cur.executemany(
            "INSERT INTO devices (id, truck_id, firmware, gateway_version, calibrated_at, calibration_offset_c, "
            "battery_v) VALUES (%(id)s, %(truck_id)s, %(firmware)s, %(gateway_version)s, %(calibrated_at)s, "
            "%(calibration_offset_c)s, %(battery_v)s) ON CONFLICT (id) DO NOTHING", load("devices"))
        for tbl in ("depots", "trucks", "devices"):
            print(tbl, cur.execute(f"SELECT count(*) FROM {tbl}").fetchone()[0])  # tabel konstan


if __name__ == "__main__":
    main()
