"""API armada (Fase 4): ringkasan, truk, riwayat, peta, sensor, kerugian, insiden, notifikasi, model, SSE.

Butuh TimescaleDB saat dipanggil; impor tidak membuka koneksi. "Sekarang" = app/clock.now().
Insiden: hanya fase operator (DITUGASKAN, DITANGANI, SELESAI) yang boleh di-PATCH, maju saja; TERDETEKSI dan
GAGAL milik Sistem (app/fleet/incidents.py). Setiap perubahan dicatat di incident_events (audit trail).
"""

import asyncio
import json
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from app import clock
from app.fleet import loss
from app.fleet import queries as q
from app.fleet.incidents import FASE_TERBUKA

router = APIRouter(prefix="/api/v1", tags=["armada"])

URUTAN_FASE = ["TERDETEKSI", "DITUGASKAN", "DITANGANI", "SELESAI"]
FASE_OPERATOR = {"DITUGASKAN", "DITANGANI", "SELESAI"}
SSE_HEARTBEAT_S = 15


def _conn():
    from app.db import conn

    return conn()


@router.get("/fleet/summary")
def fleet_summary() -> dict[str, Any]:
    with _conn() as c:
        return q.ringkasan(c, clock.now())


@router.get("/fleet/trucks")
def fleet_trucks(status: str | None = None) -> list[dict[str, Any]]:
    with _conn() as c:
        truk = q.daftar_truk(c)
    return [t for t in truk if status is None or t["status"] == status]


@router.get("/fleet/trucks/{truck_id}")
def fleet_truck(truck_id: str) -> dict[str, Any]:
    with _conn() as c:
        truck_id = q.cari_truk(c, truck_id) or truck_id
        truk = q.daftar_truk(c, truck_id)
        if not truk:
            raise HTTPException(404, f"truk tidak dikenal: {truck_id}")
        cur = c.cursor(row_factory=dict_row)
        state = cur.execute("SELECT sensor_health, perlu_diperbarui FROM truck_state WHERE truck_id = %s",
                            (truck_id,)).fetchone() or {}
        insiden = cur.execute("SELECT id, jenis, phase, status_puncak, failure_label, detected_at, breach_at, "
                              "recovered_at, closed_at, assignee FROM incidents WHERE truck_id = %s "
                              "ORDER BY detected_at DESC LIMIT 20", (truck_id,)).fetchall()
        notif = cur.execute("SELECT id, created_at, level, title, body, read_at FROM notifications "
                            "WHERE truck_id = %s ORDER BY created_at DESC LIMIT 20", (truck_id,)).fetchall()
        t = truk[0]
        label = ((t["kondisi"] or {}).get("failure_mode") or {}).get("label")
        profil = ((t["trip"] or {}).get("profil") or {}).get("id")
        detail = q.konteks_detail(c, truck_id, t["status"], label, profil, clock.now())
    return {**t, "sensor_health": state.get("sensor_health"), "perlu_diperbarui": state.get("perlu_diperbarui"),
            "insiden": insiden, "notifikasi": notif, **detail}


@router.get("/fleet/trucks/{truck_id}/history")
def fleet_truck_history(truck_id: str, menit: int = Query(240, ge=15, le=1440)) -> dict[str, Any]:
    with _conn() as c:
        tid = q.cari_truk(c, truck_id)
        if tid is None:
            raise HTTPException(404, f"truk tidak dikenal: {truck_id}")
        return q.riwayat(c, tid, clock.now(), menit)


@router.get("/fleet/map")
def fleet_map() -> dict[str, Any]:
    with _conn() as c:
        return q.peta(c)


@router.get("/fleet/sensors")
def fleet_sensors() -> dict[str, Any]:
    with _conn() as c:
        return q.sensor(c)


@router.get("/fleet/losses")
def fleet_losses(jam: int = Query(24 * 7, ge=1, le=24 * 90)) -> dict[str, Any]:
    with _conn() as c:
        return q.kerugian(c, clock.now(), jam)


# --- insiden -----------------------------------------------------------------------------------------------

@router.get("/incidents")
def incidents(phase: str | None = None, jenis: str | None = "kondisi", truck_id: str | None = None,
              terbuka: bool | None = None, limit: int = Query(100, ge=1, le=500)) -> list[dict[str, Any]]:
    syarat, p = ["true"], []
    for kolom, nilai in (("phase", phase), ("jenis", jenis), ("truck_id", truck_id)):
        if nilai:
            syarat.append(f"i.{kolom} = %s")
            p.append(nilai)
    if terbuka is not None:
        syarat.append(("" if terbuka else "NOT ") + "(i.phase = ANY(%s))")
        p.append(list(FASE_TERBUKA))
    with _conn() as c:
        rows = c.cursor(row_factory=dict_row).execute(
            "SELECT i.*, t.label, tr.cargo_profile, s.last_prediction->>'risk_index' AS risk_now, "
            "s.last_prediction->>'time_to_breach_min' AS ttb_now, "
            "(SELECT row_to_json(e) FROM (SELECT actor, at, from_phase, to_phase, note FROM incident_events "
            " WHERE incident_id = i.id ORDER BY at DESC, id DESC LIMIT 1) e) AS last_event "
            "FROM incidents i JOIN trucks t ON t.id = i.truck_id LEFT JOIN trips tr ON tr.id = i.trip_id "
            "LEFT JOIN truck_state s ON s.truck_id = i.truck_id AND s.trip_id = i.trip_id "
            f"WHERE {' AND '.join(syarat)} ORDER BY i.detected_at DESC LIMIT %s", (*p, limit)).fetchall()
    for r in rows:                                   # nilai kerugian per insiden (estimasi [ASUMSI])
        risk = r.pop("risk_now")
        ttb = r.pop("ttb_now")
        r["ttb_now_min"] = float(ttb) if ttb is not None else None
        r["loss"] = loss.per_insiden(r, float(risk) if risk is not None else None)
    return rows


@router.get("/incidents/events")
def incident_events(limit: int = Query(20, ge=1, le=200)) -> list[dict[str, Any]]:
    """Audit trail lintas insiden (perubahan fase terbaru dulu)."""
    with _conn() as c:
        return c.cursor(row_factory=dict_row).execute(
            "SELECT e.*, i.truck_id, i.jenis FROM incident_events e JOIN incidents i ON i.id = e.incident_id "
            "ORDER BY e.at DESC, e.id DESC LIMIT %s", (limit,)).fetchall()


@router.get("/incidents/{incident_id}")
def incident(incident_id: int) -> dict[str, Any]:
    with _conn() as c:
        cur = c.cursor(row_factory=dict_row)
        row = cur.execute("SELECT * FROM incidents WHERE id = %s", (incident_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "insiden tidak ada")
        row["events"] = cur.execute("SELECT * FROM incident_events WHERE incident_id = %s ORDER BY at, id",
                                    (incident_id,)).fetchall()
    return row


class InsidenUbah(BaseModel):
    phase: str | None = None
    assignee: str | None = Field(None, max_length=120)
    note: str | None = Field(None, max_length=2000)
    actor: str = Field("Operator", min_length=1, max_length=120)   # tanpa login (di luar cakupan): nama bebas


@router.patch("/incidents/{incident_id}")
def ubah_insiden(incident_id: int, body: InsidenUbah) -> dict[str, Any]:
    if body.phase is not None and body.phase not in FASE_OPERATOR:
        raise HTTPException(422, f"fase operator hanya {sorted(FASE_OPERATOR)}; TERDETEKSI/GAGAL diisi Sistem")
    now = clock.now()
    with _conn() as c:
        cur = c.cursor(row_factory=dict_row)
        row = cur.execute("SELECT * FROM incidents WHERE id = %s FOR UPDATE", (incident_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "insiden tidak ada")
        if row["phase"] not in FASE_TERBUKA:
            raise HTTPException(409, f"insiden sudah ditutup ({row['phase']})")
        fase = body.phase or row["phase"]
        if URUTAN_FASE.index(fase) < URUTAN_FASE.index(row["phase"]):
            raise HTTPException(409, f"fase tidak boleh mundur: {row['phase']} -> {fase}")
        if fase == row["phase"] and body.assignee is None and not body.note:
            raise HTTPException(422, "tidak ada perubahan")
        cur.execute("UPDATE incidents SET phase = %s, assignee = coalesce(%s, assignee), "
                    "closed_at = CASE WHEN %s = 'SELESAI' THEN %s ELSE closed_at END, updated_at = now() WHERE id = %s",
                    (fase, body.assignee, fase, now, incident_id))
        catatan = body.note or (f"Ditugaskan ke {body.assignee}" if body.assignee else None)
        cur.execute("INSERT INTO incident_events (incident_id, at, actor, from_phase, to_phase, note) "
                    "VALUES (%s, %s, %s, %s, %s, %s)", (incident_id, now, body.actor, row["phase"], fase, catatan))
        cur.execute("SELECT pg_notify('fleet_events', %s)", (json.dumps(
            {"type": "incident", "id": incident_id, "truck_id": row["truck_id"], "phase": fase}),))
        c.commit()
    return incident(incident_id)


# --- notifikasi --------------------------------------------------------------------------------------------

@router.get("/notifications")
def notifications(unread: bool = False, limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    with _conn() as c:
        cur = c.cursor(row_factory=dict_row)
        rows = cur.execute("SELECT * FROM notifications " + ("WHERE read_at IS NULL " if unread else "")
                           + "ORDER BY created_at DESC, id DESC LIMIT %s", (limit,)).fetchall()
        belum = cur.execute("SELECT count(*) n FROM notifications WHERE read_at IS NULL").fetchone()["n"]
    return {"belum_dibaca": belum, "items": rows}


@router.post("/notifications/{notification_id}/read")
def notification_read(notification_id: int) -> dict[str, Any]:
    with _conn() as c:
        row = c.execute("UPDATE notifications SET read_at = coalesce(read_at, now()) WHERE id = %s RETURNING id",
                        (notification_id,)).fetchone()
        c.commit()
    if row is None:
        raise HTTPException(404, "notifikasi tidak ada")
    return {"id": notification_id, "dibaca": True}


@router.post("/notifications/read-all")
def notification_read_all() -> dict[str, Any]:
    with _conn() as c:
        n = c.execute("UPDATE notifications SET read_at = now() WHERE read_at IS NULL").rowcount
        c.commit()
    return {"ditandai": n}


# --- model ---------------------------------------------------------------------------------------------------

@router.get("/models")
def models() -> dict[str, Any]:
    from app.models.orchestrator import orchestrator

    return {"providers": orchestrator.cards(), "pilihan": orchestrator.pilihan}


# --- SSE ---------------------------------------------------------------------------------------------------

@router.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    """Server-Sent Events dari LISTEN fleet_events (worker-infer dan PATCH insiden). Heartbeat tiap 15 detik.
    Klien: EventSource; bila putus, frontend jatuh ke polling 30 detik (Fase 5)."""
    import psycopg

    from app.db import dsn

    async def gen():
        aconn = await psycopg.AsyncConnection.connect(dsn(), autocommit=True)
        try:
            await aconn.execute("LISTEN fleet_events")
            yield f"event: hello\ndata: {json.dumps({'now': clock.now().isoformat()})}\n\n"
            while not await request.is_disconnected():
                # notifies(timeout=...) berhenti sendiri setelah timeout; lalu kirim heartbeat dan ulangi
                async for n in aconn.notifies(timeout=SSE_HEARTBEAT_S, stop_after=100):
                    tipe = json.loads(n.payload).get("type", "message")
                    yield f"event: {tipe}\ndata: {n.payload}\n\n"
                yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await aconn.close()

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def cors_origins() -> list[str]:
    """CORS_ORIGINS (dipisah koma). Bawaan: frontend dev lokal saja."""
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]
