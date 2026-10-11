"""Worker inferensi streaming: telemetry -> predictions, truck_state, insiden, notifikasi (Fase 3).

  python -m app.workers.infer

Env: DATABASE_URL, SIM_SPEED / SIM_ANCHOR (app/clock.py, HARUS sama dengan simulator dan API).

- Pemicu: LISTEN telemetry_arrived (dikirim app/ingest/store.py) dengan debounce per truk
  (config fleet.infer_debounce_detik), ditambah tick tiap menit simulasi: truk tanpa bacaan baru selama
  fleet.offline_setelah_menit -> TIDAK_ADA_DATA (tidak pernah AMAN).
- Jendela: app/fleet/window.py (grid 1 menit, isi celah <= ffill_maks_menit, riwayat <= history_cap_min sejak
  awal trip). Model hanya dijalankan untuk jendela terakhir (inference.predict_last).
- Setelah menulis: NOTIFY fleet_events '{"type": "truck"|"notification", ...}' (SSE Fase 4).
- Data terlambat: prediksi dihitung ulang untuk menit TERAKHIR saja; prediksi menit lampau tidak ditulis ulang.
"""

import json
import logging
import math
import signal
import time
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app import clock
from app.config import settings
from app.db import dsn
from app.fleet import incidents as inc
from app.fleet.devices import perlu_diperbarui
from app.fleet.window import KOLOM, bangun_jendela
from app.models.base import Konteks
from app.models.orchestrator import orchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("coldtrack.infer")

CFG = settings.get("fleet", {})
CAP_MIN = int(CFG.get("history_cap_min", 240))
FFILL = int(CFG.get("ffill_maks_menit", 5))
ZONA = CFG.get("zona_waktu", "Asia/Jakarta")       # fitur hour_of_day = jam lokal (app/fleet/window.py)
OFFLINE = int(CFG.get("offline_setelah_menit", 10))
SENSOR_JAM = 3
TOLERANSI_JAM_PERANGKAT = timedelta(minutes=2)    # bacaan sedikit di depan jam server tetap dipakai
KOLOM_SQL = ", ".join(["ts", *KOLOM])


def _bersih(x: Any) -> Any:
    """NaN/inf -> None, numpy/pandas -> tipe Python, supaya aman untuk jsonb."""
    if isinstance(x, dict):
        return {k: _bersih(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_bersih(v) for v in x]
    if hasattr(x, "item") and not isinstance(x, str | bytes):
        x = x.item()
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, datetime | pd.Timestamp):
        return x.isoformat()
    return x


def muat(c: psycopg.Connection, truck_id: str, now: datetime) -> dict[str, Any]:
    cur = c.cursor(row_factory=dict_row)
    trip = cur.execute("SELECT id, cargo_profile, mass_kg, cargo_value_idr, started_at FROM trips "
                       "WHERE truck_id = %s AND ended_at IS NULL", (truck_id,)).fetchone()
    device = cur.execute("SELECT * FROM devices WHERE truck_id = %s ORDER BY id LIMIT 1", (truck_id,)).fetchone()
    batas_atas = now + TOLERANSI_JAM_PERANGKAT
    dari_sensor = now - timedelta(hours=SENSOR_JAM)
    dari = dari_sensor if trip is None else min(dari_sensor, max(trip["started_at"], now - timedelta(minutes=CAP_MIN)))
    rows = cur.execute(f"SELECT {KOLOM_SQL} FROM telemetry WHERE truck_id = %s AND ts >= %s AND ts <= %s ORDER BY ts",
                       (truck_id, dari, batas_atas)).fetchall()
    df = pd.DataFrame(rows, columns=["ts", *KOLOM])
    if not df.empty:
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
    trip_rows = df if trip is None else df[(df.ts >= trip["started_at"]) & (df.ts >= now - timedelta(minutes=CAP_MIN))]
    last_any = cur.execute("SELECT max(ts) FROM telemetry WHERE truck_id = %s AND ts <= %s",
                           (truck_id, batas_atas)).fetchone()["max"]
    return {"trip": trip, "device": device, "trip_rows": trip_rows.reset_index(drop=True),
            "raw": df[df.ts >= dari_sensor].reset_index(drop=True) if not df.empty else df, "last_any": last_any}


def _ringkas_prediksi(cond: dict[str, Any], raw: pd.DataFrame) -> dict[str, Any]:
    keys = ("status", "reason", "risk_index", "time_to_breach_min", "ttb_model_min", "forecast", "failure_mode",
            "data_lengkap", "catatan_data", "t_cargo_est", "t_hi", "model_version", "provider")
    out = {k: cond.get(k) for k in keys}
    if not raw.empty:
        last = raw.iloc[-1]
        out["bacaan_terakhir"] = {"ts": last.ts, **{k: last[k] for k in KOLOM}}
    return _bersih(out)


def hitung(c: psycopg.Connection, truck_id: str) -> list[dict[str, Any]]:
    """Hitung satu truk dan tulis semuanya dalam satu transaksi. Kembalikan event untuk NOTIFY fleet_events."""
    now = clock.now()
    m = muat(c, truck_id, now)
    trip, device = m["trip"], m["device"]
    cur = c.cursor(row_factory=dict_row)
    prev = cur.execute("SELECT status FROM truck_state WHERE truck_id = %s", (truck_id,)).fetchone()
    prev_status = prev["status"] if prev else None

    if trip is None:
        jendela = bangun_jendela(pd.DataFrame(), now)
        sh = orchestrator.provider("sensor_health").run(Konteks(truck_id, now, jendela, device=device, raw=m["raw"]))
        pdb = perlu_diperbarui(device or {}, sh, now, CFG.get("perangkat", {}), m["last_any"])
        cur.execute(
            "INSERT INTO truck_state (truck_id, status, last_ts, last_prediction, trip_id, sensor_health, "
            "perlu_diperbarui, computed_at, updated_at) VALUES (%s, 'TANPA_TRIP', %s, NULL, NULL, %s, %s, %s, now()) "
            "ON CONFLICT (truck_id) DO UPDATE SET status = 'TANPA_TRIP', last_ts = EXCLUDED.last_ts, "
            "last_prediction = NULL, trip_id = NULL, sensor_health = EXCLUDED.sensor_health, "
            "perlu_diperbarui = EXCLUDED.perlu_diperbarui, computed_at = EXCLUDED.computed_at, updated_at = now()",
            (truck_id, m["last_any"], Jsonb(_bersih(sh)), Jsonb(_bersih(pdb)), now))
        c.commit()
        return [{"type": "truck", "truck_id": truck_id, "status": "TANPA_TRIP"}]

    jendela = bangun_jendela(m["trip_rows"], now, FFILL, OFFLINE, ZONA)
    ctx = Konteks(truck_id, now, jendela, trip["cargo_profile"], trip["mass_kg"], device, m["raw"])
    hasil = orchestrator.analyze(ctx)
    cond, sh = hasil["condition"], hasil["sensor_health"]
    status = cond["status"]
    pdb = perlu_diperbarui(device or {}, sh, now, CFG.get("perangkat", {}), m["last_any"])
    ts = jendela.readings[-1].ts if jendela.keadaan == "OK" else (
        jendela.last_ts if jendela.keadaan == "MENUNGGU_DATA" else now.replace(second=0, microsecond=0))
    fm = cond.get("failure_mode") or {}
    cur.execute(
        "INSERT INTO predictions (truck_id, ts, trip_id, status, risk_index, ttb_show_min, ttb_model_min, "
        "failure_label, failure_conf, probabilities, forecast, data_lengkap, sensor_health, model_version, provider) "
        "VALUES (%(truck_id)s, %(ts)s, %(trip_id)s, %(status)s, %(risk)s, %(ttb)s, %(ttbm)s, %(label)s, %(conf)s, "
        "%(prob)s, %(fc)s, %(lengkap)s, %(sh)s, %(mv)s, %(prov)s) ON CONFLICT (truck_id, ts) DO UPDATE SET "
        "trip_id = EXCLUDED.trip_id, status = EXCLUDED.status, risk_index = EXCLUDED.risk_index, "
        "ttb_show_min = EXCLUDED.ttb_show_min, ttb_model_min = EXCLUDED.ttb_model_min, "
        "failure_label = EXCLUDED.failure_label, failure_conf = EXCLUDED.failure_conf, "
        "probabilities = EXCLUDED.probabilities, forecast = EXCLUDED.forecast, data_lengkap = EXCLUDED.data_lengkap, "
        "sensor_health = EXCLUDED.sensor_health, model_version = EXCLUDED.model_version, "
        "provider = EXCLUDED.provider, created_at = now()",
        {"truck_id": truck_id, "ts": ts, "trip_id": trip["id"], "status": status, "risk": cond.get("risk_index"),
         "ttb": _bersih(cond.get("time_to_breach_min")), "ttbm": _bersih(cond.get("ttb_model_min")),
         "label": fm.get("label"), "conf": fm.get("confidence"),
         "prob": Jsonb(_bersih(fm.get("probabilities"))) if fm.get("probabilities") else None,
         "fc": Jsonb(_bersih(cond["forecast"])) if cond.get("forecast") else None,
         "lengkap": cond.get("data_lengkap"), "sh": Jsonb(_bersih(sh)), "mv": cond.get("model_version"),
         "prov": cond.get("provider")})

    breach = cond.get("t_cargo_est") is not None and cond["t_cargo_est"] >= cond["t_hi"]
    events = [{"type": "truck", "truck_id": truck_id, "status": status, "prev_status": prev_status,
               "ts": ts.isoformat()}]
    for jenis in inc.EPISODE:
        terbuka = cur.execute("SELECT id, phase, status_puncak, breach_at, recovered_at FROM incidents WHERE truck_id = %s "
                              "AND jenis = %s AND trip_id = %s AND phase = ANY(%s) FOR UPDATE",
                              (truck_id, jenis, trip["id"], list(inc.FASE_TERBUKA))).fetchone()
        rencana = inc.langkah(jenis, truck_id, prev_status, status, terbuka, ts, breach, fm.get("label"),
                              cond.get("reason"), trip["id"], trip["cargo_value_idr"])
        events += terapkan(cur, rencana, terbuka, truck_id, ts)

    cur.execute(
        "INSERT INTO truck_state (truck_id, status, last_ts, last_prediction, trip_id, sensor_health, perlu_diperbarui, "
        "computed_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now()) ON CONFLICT (truck_id) DO UPDATE SET "
        "status = EXCLUDED.status, last_ts = EXCLUDED.last_ts, last_prediction = EXCLUDED.last_prediction, "
        "trip_id = EXCLUDED.trip_id, sensor_health = EXCLUDED.sensor_health, perlu_diperbarui = EXCLUDED.perlu_diperbarui, "
        "computed_at = EXCLUDED.computed_at, updated_at = now()",
        (truck_id, status, m["last_any"], Jsonb(_ringkas_prediksi(cond, m["raw"])), trip["id"], Jsonb(_bersih(sh)),
         Jsonb(_bersih(pdb)), now))
    c.commit()
    return events


def terapkan(cur, rencana: inc.Rencana, terbuka: dict[str, Any] | None, truck_id: str,
             ts: datetime) -> list[dict[str, Any]]:
    """Tulis Rencana insiden (buka/ubah/events/notifikasi). Kembalikan event notifikasi untuk SSE."""
    inc_id = terbuka["id"] if terbuka else None
    if rencana.buka:
        kolom = list(rencana.buka)
        inc_id = cur.execute(f"INSERT INTO incidents ({', '.join(kolom)}) VALUES "
                             f"({', '.join(f'%({k})s' for k in kolom)}) RETURNING id", rencana.buka).fetchone()["id"]
    if rencana.ubah and inc_id is not None:
        kolom = ", ".join(f"{k} = %({k})s" for k in rencana.ubah)
        cur.execute(f"UPDATE incidents SET {kolom}, updated_at = now() WHERE id = %(id)s", {**rencana.ubah, "id": inc_id})
    for e in rencana.events:
        cur.execute("INSERT INTO incident_events (incident_id, at, actor, from_phase, to_phase, note) "
                    "VALUES (%s, %s, %s, %s, %s, %s)", (inc_id, ts, e["actor"], e["from_phase"], e["to_phase"], e["note"]))
    out = []
    for n in rencana.notifikasi:
        nid = cur.execute("INSERT INTO notifications (created_at, truck_id, incident_id, level, title, body) "
                          "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                          (ts, truck_id, inc_id, n["level"], n["title"], n["body"])).fetchone()["id"]
        out.append({"type": "notification", "id": nid, "truck_id": truck_id, "incident_id": inc_id,
                    "jenis": rencana.jenis, "level": n["level"], "title": n["title"]})
    return out


def kirim_events(c: psycopg.Connection, events: list[dict[str, Any]]) -> None:
    for e in events:
        c.execute("SELECT pg_notify('fleet_events', %s)", (json.dumps(_bersih(e)),))
    c.commit()


def truk_perlu_tick(c: psycopg.Connection, now: datetime) -> list[str]:
    """Truk ber-trip aktif yang belum pernah dihitung, atau bacaan terakhirnya sudah melewati ambang offline
    tetapi statusnya belum TIDAK_ADA_DATA; plus truk yang trip-nya berubah (buka/tutup)."""
    batas = now - timedelta(minutes=OFFLINE)
    rows = c.execute(
        "SELECT t.id FROM trucks t LEFT JOIN trips tr ON tr.truck_id = t.id AND tr.ended_at IS NULL "
        "LEFT JOIN truck_state s ON s.truck_id = t.id WHERE t.active AND ("
        " s.truck_id IS NULL"
        " OR (tr.id IS NOT NULL AND s.status <> 'TIDAK_ADA_DATA' AND (s.last_ts IS NULL OR s.last_ts < %s))"
        " OR (tr.id IS DISTINCT FROM s.trip_id))", (batas,)).fetchall()
    return [r[0] for r in rows]


def main() -> None:
    debounce = float(CFG.get("infer_debounce_detik", 2))
    tick_s = max(1.0, min(60.0, clock.wall_seconds_for(60)))
    berhenti = False

    def stop(*_):
        nonlocal berhenti
        berhenti = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    pending: dict[str, float] = {}
    tick_berikut = 0.0
    while not berhenti:
        try:
            with psycopg.connect(dsn(), autocommit=True) as listen, psycopg.connect(dsn()) as kerja:
                listen.execute("LISTEN telemetry_arrived")
                logger.info("worker-infer siap: debounce %.1fs, tick %.1fs, SIM_SPEED=%s, provider %s",
                            debounce, tick_s, clock.speed(), orchestrator.pilihan)
                while not berhenti:
                    for n in listen.notifies(timeout=0.5, stop_after=500):
                        pending.setdefault(n.payload, time.monotonic() + debounce)
                    if time.monotonic() >= tick_berikut:
                        tick_berikut = time.monotonic() + tick_s
                        for t in truk_perlu_tick(kerja, clock.now()):
                            pending.setdefault(t, 0.0)
                    siap = [t for t, d in pending.items() if d <= time.monotonic()]
                    for t in siap:
                        pending.pop(t, None)
                        t0 = time.perf_counter()
                        try:
                            events = hitung(kerja, t)
                            kirim_events(kerja, events)
                            logger.info("%s: %s (%.0f ms)", t, events[0]["status"], 1000 * (time.perf_counter() - t0))
                        except Exception:
                            kerja.rollback()
                            logger.exception("gagal menghitung %s", t)
        except psycopg.OperationalError:
            logger.exception("koneksi DB putus; mencoba lagi dalam 5 detik")
            time.sleep(5)


if __name__ == "__main__":
    main()
