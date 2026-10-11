"""Query baca untuk API armada (Fase 4). Semua fungsi menerima koneksi psycopg dan mengembalikan dict siap-JSON.

"Sekarang" selalu app/clock.now() (jam simulasi di dev), sama dengan worker-infer.
"""

from datetime import datetime, timedelta
from typing import Any

from psycopg.rows import dict_row

from app.config import settings
from app.fleet import loss
from app.fleet.incidents import FASE_TERBUKA

URUTAN_STATUS = ["KRITIS", "WASPADA", "TIDAK_ADA_DATA", "DATA_TIDAK_LENGKAP", "MENUNGGU_DATA", "AMAN", "TANPA_TRIP"]
BURUK = {s: i for i, s in enumerate(URUTAN_STATUS)}            # makin kecil makin buruk


def _profil(cargo_profile: str | None) -> dict[str, Any] | None:
    if not cargo_profile:
        return None
    p = settings.get("cargo_profiles", {}).get(cargo_profile, {})
    return {"id": cargo_profile, "nama": p.get("name", cargo_profile), "t_lo": p.get("min_temp_c"),
            "t_hi": p.get("max_temp_c"), "t_kritis": p.get("critical_temp_c")}


TRUK_SQL = """
SELECT t.id AS truck_id, t.label, t.depot_id, d.name AS depot_nama, d.city AS depot_kota,
       coalesce(s.status, 'TANPA_TRIP') AS status, s.last_ts, s.computed_at, s.last_prediction, s.sensor_health,
       s.perlu_diperbarui,
       tr.id AS trip_id, tr.cargo_profile, tr.mass_kg, tr.cargo_value_idr, tr.started_at,
       dv.id AS device_id, dv.online, dv.battery_v, dv.firmware, dv.gateway_version, dv.calibrated_at,
       dv.last_status_at,
       (SELECT row_to_json(i) FROM (SELECT id, phase, status_puncak, detected_at, assignee FROM incidents
         WHERE truck_id = t.id AND jenis = 'kondisi' AND phase = ANY(%(terbuka)s)
         ORDER BY detected_at DESC LIMIT 1) i) AS insiden_terbuka
FROM trucks t
JOIN depots d ON d.id = t.depot_id
LEFT JOIN truck_state s ON s.truck_id = t.id
LEFT JOIN trips tr ON tr.truck_id = t.id AND tr.ended_at IS NULL
LEFT JOIN LATERAL (SELECT * FROM devices WHERE truck_id = t.id ORDER BY id LIMIT 1) dv ON true
WHERE t.active {filter}
"""


def _truk(r: dict[str, Any]) -> dict[str, Any]:
    pred = r["last_prediction"] or {}
    # trip ditutup tetapi worker belum menghitung ulang: jangan tampilkan status trip lama
    status = r["status"] if r["trip_id"] is not None else "TANPA_TRIP"
    sh = r["sensor_health"] or {}
    return {
        "truck_id": r["truck_id"], "label": r["label"],
        "depot": {"id": r["depot_id"], "nama": r["depot_nama"], "kota": r["depot_kota"]},
        "status": status, "last_ts": r["last_ts"], "computed_at": r["computed_at"],
        "trip": None if r["trip_id"] is None else {
            "id": r["trip_id"], "profil": _profil(r["cargo_profile"]), "mass_kg": r["mass_kg"],
            "cargo_value_idr": r["cargo_value_idr"], "started_at": r["started_at"]},
        "kondisi": None if r["trip_id"] is None else {
            k: pred.get(k) for k in ("reason", "risk_index", "time_to_breach_min", "ttb_model_min", "forecast",
                                     "failure_mode", "data_lengkap", "catatan_data", "t_cargo_est",
                                     "model_version", "provider")},
        "bacaan_terakhir": pred.get("bacaan_terakhir"),
        "sensor": {"score": sh.get("score"), "grade": sh.get("grade")},
        "perangkat": None if r["device_id"] is None else {
            "id": r["device_id"], "online": r["online"], "battery_v": r["battery_v"], "firmware": r["firmware"],
            "gateway_version": r["gateway_version"], "calibrated_at": r["calibrated_at"],
            "last_status_at": r["last_status_at"]},
        "n_perlu_diperbarui": len(r["perlu_diperbarui"] or []),
        "insiden_terbuka": r["insiden_terbuka"],
    }


def cari_truk(c, truck_id: str) -> str | None:
    """Terima nomor polisi apa adanya ("B 3036 WN") atau kunci topik ("B3036WN")."""
    row = c.execute("SELECT id FROM trucks WHERE id = %s OR replace(id, ' ', '') = upper(replace(%s, ' ', ''))",
                    (truck_id, truck_id)).fetchone()
    return row[0] if row else None


def daftar_truk(c, truck_id: str | None = None) -> list[dict[str, Any]]:
    filt, params = ("AND t.id = %(id)s", {"id": truck_id}) if truck_id else ("", {})
    rows = c.cursor(row_factory=dict_row).execute(TRUK_SQL.format(filter=filt),
                                                  {"terbuka": list(FASE_TERBUKA), **params}).fetchall()
    out = [_truk(r) for r in rows]
    out.sort(key=lambda t: (BURUK.get(t["status"], 99), -((t["kondisi"] or {}).get("risk_index") or 0), t["truck_id"]))
    return out


def ringkasan(c, now: datetime) -> dict[str, Any]:
    truk = daftar_truk(c)
    per_status = {s: 0 for s in URUTAN_STATUS}
    per_diag: dict[str, int] = {}
    per_grade: dict[str, int] = {}
    for t in truk:
        per_status[t["status"]] = per_status.get(t["status"], 0) + 1
        fm = (t["kondisi"] or {}).get("failure_mode") or {}
        if fm.get("label"):
            per_diag[fm["label"]] = per_diag.get(fm["label"], 0) + 1
        if t["sensor"]["grade"]:
            per_grade[t["sensor"]["grade"]] = per_grade.get(t["sensor"]["grade"], 0) + 1
    cur = c.cursor(row_factory=dict_row)
    fase = {r["phase"]: r["n"] for r in cur.execute(
        "SELECT phase, count(*) n FROM incidents WHERE jenis = 'kondisi' AND phase = ANY(%s) GROUP BY 1",
        (list(FASE_TERBUKA),)).fetchall()}
    belum = cur.execute("SELECT count(*) n FROM notifications WHERE read_at IS NULL").fetchone()["n"]
    aktif = [t for t in truk if t["trip"] is not None]
    return {
        "now": now, "n_truk": len(truk), "n_trip_aktif": len(aktif),
        "per_status": per_status,
        "kritis_vs_tidak": {"kritis": per_status["KRITIS"], "tidak_kritis": len(aktif) - per_status["KRITIS"]},
        "per_diagnosis": dict(sorted(per_diag.items(), key=lambda kv: -kv[1])),
        "per_grade_sensor": per_grade,
        "insiden_terbuka_per_fase": {f: fase.get(f, 0) for f in FASE_TERBUKA},
        "notifikasi_belum_dibaca": belum,
        "nilai_muatan_aktif_idr": sum(t["trip"]["cargo_value_idr"] or 0 for t in aktif),
        "kerugian_24j": kerugian(c, now, jam=24)["ringkasan"],
    }


def riwayat(c, truck_id: str, now: datetime, menit: int = 240) -> dict[str, Any]:
    cur = c.cursor(row_factory=dict_row)
    trip = cur.execute("SELECT id, cargo_profile, started_at FROM trips WHERE truck_id = %s AND ended_at IS NULL",
                       (truck_id,)).fetchone()
    dari = now - timedelta(minutes=menit)
    if trip:
        dari = max(dari, trip["started_at"])
    aktual = cur.execute(
        "SELECT ts, temp_c, ambient_c, humidity, door_open, reefer_on, speed_kmh FROM telemetry "
        "WHERE truck_id = %s AND ts >= %s AND ts <= %s ORDER BY ts", (truck_id, dari, now + timedelta(minutes=2))
    ).fetchall()
    prediksi = cur.execute(
        "SELECT ts, status, risk_index, ttb_show_min, failure_label, failure_conf, forecast, data_lengkap "
        "FROM predictions WHERE truck_id = %s AND ts >= %s AND ts <= %s ORDER BY ts",
        (truck_id, dari, now + timedelta(minutes=2))).fetchall()
    terakhir = next((p for p in reversed(prediksi) if p["forecast"]), None)
    garis_prediksi = None
    if terakhir:                                     # grafik "aktual dan prediksi": +15/+30/+60 dari menit terakhir
        garis_prediksi = [{"horizon_min": h, "ts": terakhir["ts"] + timedelta(minutes=h),
                           "temp_c": terakhir["forecast"][f"t{h}"]} for h in (15, 30, 60)]
    return {"truck_id": truck_id, "dari": dari, "sampai": now, "profil": _profil(trip["cargo_profile"]) if trip else None,
            "aktual": aktual, "prediksi": prediksi, "garis_prediksi": garis_prediksi,
            "catatan": "Prediksi suhu = sensor kargo pada +15/+30/+60 menit dari bacaan terakhir (model v3)."}


def peta(c) -> dict[str, Any]:
    truk = daftar_truk(c)
    depo = c.cursor(row_factory=dict_row).execute("SELECT id, name AS nama, city AS kota, lat, lon FROM depots").fetchall()
    for d in depo:                                    # warna depo = status terburuk truk aktif di depo itu
        st = [t["status"] for t in truk if t["depot"]["id"] == d["id"] and t["trip"] is not None]
        d["status"] = min(st, key=lambda s: BURUK.get(s, 99)) if st else None
        d["n_truk_aktif"] = len(st)
    titik = []
    for t in truk:
        b = t["bacaan_terakhir"] or {}
        titik.append({"truck_id": t["truck_id"], "label": t["label"], "status": t["status"],
                      "online": (t["perangkat"] or {}).get("online"), "lat": b.get("lat"), "lon": b.get("lon"),
                      "ts": b.get("ts"), "depot_id": t["depot"]["id"]})
    return {"depo": depo, "truk": titik}


def sensor(c) -> dict[str, Any]:
    rows = c.cursor(row_factory=dict_row).execute(
        "SELECT dv.*, s.sensor_health, s.perlu_diperbarui, t.label FROM devices dv JOIN trucks t ON t.id = dv.truck_id "
        "LEFT JOIN truck_state s ON s.truck_id = dv.truck_id ORDER BY dv.id").fetchall()
    perangkat, temuan = [], []
    for r in rows:
        pdb = r.pop("perlu_diperbarui") or []
        perangkat.append({**r, "n_perlu_diperbarui": len(pdb)})
        temuan += [{"device_id": r["id"], "truck_id": r["truck_id"], **x} for x in pdb]
    grade: dict[str, int] = {}
    for p in perangkat:
        g = (p["sensor_health"] or {}).get("grade") or "Belum dinilai"
        grade[g] = grade.get(g, 0) + 1
    return {"perangkat": perangkat, "perlu_diperbarui": temuan, "per_grade": grade,
            "metode": "sensor_health rules_v0 (bobot [DESAIN]); lihat GET /api/v1/models"}


def kerugian(c, now: datetime, jam: int = 24 * 7) -> dict[str, Any]:
    rows = c.cursor(row_factory=dict_row).execute(
        "SELECT i.*, s.last_prediction->>'risk_index' AS risk_now FROM incidents i "
        "LEFT JOIN truck_state s ON s.truck_id = i.truck_id AND s.trip_id = i.trip_id "
        "WHERE i.jenis = 'kondisi' AND i.detected_at >= %s ORDER BY i.detected_at DESC",
        (now - timedelta(hours=jam),)).fetchall()
    baris = []
    for r in rows:
        risk = float(r["risk_now"]) if r["risk_now"] is not None else None
        baris.append({"incident_id": r["id"], "truck_id": r["truck_id"], "phase": r["phase"],
                      "detected_at": r["detected_at"], "breach_at": r["breach_at"], **loss.per_insiden(r, risk)})
    return {"dari": now - timedelta(hours=jam), "sampai": now, "ringkasan": loss.ringkas(baris), "insiden": baris}
