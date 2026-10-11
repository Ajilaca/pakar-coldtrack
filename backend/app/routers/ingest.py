"""Ingest HTTP (webhook vendor) dan pembukaan/penutupan trip.

- POST /api/v1/ingest/vendor/{vendor}  header X-API-Key; kunci dari env INGEST_API_KEYS
  ("generic_json=kunci1;generic_csv=kunci2"). Tanpa kunci terkonfigurasi, endpoint menolak semua.
- POST /api/v1/trips                     buka trip (trip aktif lama di truk itu ditutup dulu)
- PATCH /api/v1/trips/{trip_id}          tutup trip
"""

import hmac
import os
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app import clock
from app.adapters import REGISTRY
from app.config import settings

router = APIRouter(prefix="/api/v1", tags=["armada-ingest"])


def _kunci(vendor: str) -> str | None:
    for pasangan in os.environ.get("INGEST_API_KEYS", "").split(";"):
        nama, _, kunci = pasangan.partition("=")
        if nama.strip() == vendor and kunci.strip():
            return kunci.strip()
    return None


@router.post("/ingest/vendor/{vendor}")
async def ingest_vendor(vendor: str, request: Request, x_api_key: str = Header("")) -> dict:
    from app.db import conn
    from app.ingest.store import store_readings, validate_readings

    adapter = REGISTRY.get(vendor)
    if adapter is None:
        raise HTTPException(404, f"vendor tidak dikenal: {vendor}")
    kunci = _kunci(vendor)
    if kunci is None or not hmac.compare_digest(kunci, x_api_key):
        raise HTTPException(401, "X-API-Key tidak valid")
    try:
        batches = adapter.normalize(await request.body(), request.headers.get("content-type", ""))
    except (ValueError, KeyError) as e:
        raise HTTPException(422, f"payload vendor tidak dapat dibaca: {e}") from e
    hasil = {"diterima": 0, "baru": 0, "ditolak": [], "truk_tak_dikenal": []}
    with conn() as c:
        for b in batches:
            if c.execute("SELECT 1 FROM trucks WHERE id = %s", (b.truck_id,)).fetchone() is None:
                hasil["truk_tak_dikenal"].append(b.truck_id)
                continue
            ok, errors = validate_readings(b.readings)
            hasil["diterima"] += len(ok)
            hasil["ditolak"] += [f"{b.truck_id}: {e}" for e in errors]
            hasil["baru"] += store_readings(c, b.truck_id, b.device_id, None, ok)
    return hasil


class TripBuka(BaseModel):
    truck_id: str
    cargo_profile: str
    mass_kg: float | None = Field(None, gt=0)
    depot_id: str | None = None
    started_at: datetime | None = None


class TripTutup(BaseModel):
    ended_at: datetime | None = None


def nilai_muatan(cargo_profile: str, mass_kg: float | None) -> int | None:
    """[ASUMSI] massa x harga per kg dari config.yaml fleet.harga_per_kg_idr (docs/fleet_assumptions.md)."""
    harga = settings.get("fleet", {}).get("harga_per_kg_idr", {}).get(cargo_profile)
    massa = mass_kg or settings.get("cargo_profiles", {}).get(cargo_profile, {}).get("mass_kg_default")
    return int(harga * massa) if harga and massa else None


@router.post("/trips", status_code=201)
def buka_trip(t: TripBuka) -> dict:
    from app.db import conn

    if t.cargo_profile not in settings.get("cargo_profiles", {}):
        raise HTTPException(422, f"cargo_profile tidak dikenal: {t.cargo_profile}")
    mulai = t.started_at or clock.now()
    with conn() as c:
        if c.execute("SELECT 1 FROM trucks WHERE id = %s", (t.truck_id,)).fetchone() is None:
            raise HTTPException(404, f"truk tidak dikenal: {t.truck_id}")
        c.execute("UPDATE trips SET ended_at = %s WHERE truck_id = %s AND ended_at IS NULL", (mulai, t.truck_id))
        row = c.execute(
            "INSERT INTO trips (truck_id, cargo_profile, mass_kg, cargo_value_idr, depot_id, started_at) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, cargo_value_idr",
            (t.truck_id, t.cargo_profile, t.mass_kg, nilai_muatan(t.cargo_profile, t.mass_kg), t.depot_id, mulai),
        ).fetchone()
        c.commit()
    return {"trip_id": row[0], "cargo_value_idr": row[1], "started_at": mulai}


@router.patch("/trips/{trip_id}")
def tutup_trip(trip_id: int, t: TripTutup) -> dict:
    from app.db import conn

    with conn() as c:
        row = c.execute("UPDATE trips SET ended_at = %s WHERE id = %s AND ended_at IS NULL RETURNING id",
                        (t.ended_at or clock.now(), trip_id)).fetchone()
        c.commit()
    if row is None:
        raise HTTPException(404, "trip tidak ada atau sudah ditutup")
    return {"trip_id": trip_id, "ditutup": True}
