"""Hasil chip edge (hw/, AMD Kria KV260) di jalur cloud: dihitung sekali di truk, cloud memverifikasi dan memakai.

Truk ber-chip menambahkan objek `edge` ke tiap bacaan (docs/device_contract.md):
  rek     rekaman 23 byte yang disegel chip (hex)          format hw/golden/seal.py
  rantai  hash rantai setelah rekaman ini (hex, 32 byte)    h_i = SHA256(h_i-1 || rek), h_-1 = nol saat seq 0
  paket   paket hasil 16 byte (hex)                          hw/golden/regmap.paket_hasil
  mac     HMAC-SHA256(kunci perangkat, rantai || paket)
  skor    7 skor kelas Q8.16 (opsional, di luar MAC; dicek terhadap kelas dan skor teratas di paket)
Menit yang bacaan suhunya gagal tetap disegel chip; objek `edge`-nya dikirim di `rekaman_tanpa_bacaan` supaya
rantai menit berikutnya tetap bisa diverifikasi (rekaman itu harus bertanda sensor suhu tidak valid).

Verifikasi (kolom edge_results.verifikasi): MAC harus sah, isi rekaman harus sama dengan bacaan yang
disimpan, dan rantai harus bersambung dengan rekaman seq-1 bila rekaman itu sudah diterima.
Kunci perangkat dari env EDGE_KEYS="DEV-001=<64 hex>,DEV-002=..." (dev; produksi memakai penyimpanan rahasia).
"""

import hashlib
import hmac
import logging
import math
import os
import struct
from datetime import UTC, datetime
from typing import Any

from app.fleet.window import Jendela
from app.inference import (
    RISK_BAND,
    SENSOR_RISK_BAND,
    TTB_MAX,
    V3_API_LABEL,
    _guard_label,
    cargo_params,
)
from app.schemas import TelemetryReading

logger = logging.getLogger("coldtrack.edge")

FORMAT_REKAMAN = ">IIhHhHHBHBB"
SAH = ("OK", "OK_RANTAI_BARU")
PROVIDER = "edge_kv260"
# urutan kelas model chip = ml.preprocess.build_windows.FAILURE_CLASSES (label B8/B10)
KELAS_CHIP = ["A0", "A1", "A3", "A7", "A8", "degradasi_bertahap", "masalah_sensor"]
NAMA_STATUS = {0: "AMAN", 1: "WASPADA", 2: "KRITIS"}
NOL = bytes(32)


def kunci_perangkat(env: str | None = None) -> dict[str, bytes]:
    out = {}
    for item in (env if env is not None else os.environ.get("EDGE_KEYS", "")).split(","):
        if "=" in item:
            dev, h = item.split("=", 1)
            out[dev.strip()] = bytes.fromhex(h.strip())
    return out


def baca_rekaman(rek: bytes) -> dict[str, Any]:
    seq, ts, temp, rh, amb, solar, speed, flags, duty, harsh, batt = struct.unpack(FORMAT_REKAMAN, rek)
    return {"seq": seq, "ts": ts, "temp": temp, "rh": rh, "amb": amb, "solar": solar, "speed": speed,
            "pintu": bool(flags & 1), "reefer": bool(flags & 2), "temp_ok": bool(flags & 8), "duty": duty,
            "harsh": harsh, "batt": batt}


def baca_paket(paket: bytes) -> dict[str, Any]:
    v = int.from_bytes(paket, "big")
    b_fis, b_diag = (v >> 72) & 0xFF, (v >> 56) & 0xFF
    tc = (v >> 16) & 0xFFFFFFFF
    tc = tc - (1 << 32) if tc >> 31 else tc
    skor = v & 0xFFFF
    return {"seq": v >> 96, "menit": (v >> 80) & 0xFFFF, "status": b_fis & 3, "alasan": (b_fis >> 2) & 7,
            "sensor": (b_fis >> 5) & 3, "ttb_valid": bool(b_fis >> 7), "ttb": (v >> 64) & 0x3F,
            "diag_valid": bool(b_diag & 8), "kelas": b_diag & 7, "tc_c": tc / 25600,      # (0,01 C x 2^16) >> 8
            "skor_atas": skor - (1 << 16) if skor >> 15 else skor}


def cocok_dengan_bacaan(r: dict[str, Any], rd: TelemetryReading) -> bool:
    """Isi rekaman yang disegel harus sama dengan bacaan yang disimpan (satuan rekaman, dibulatkan)."""
    sama = [r["ts"] == int(rd.ts.timestamp()), r["rh"] == round(rd.humidity * 100), r["amb"] == round(rd.ambient_c * 100),
            r["speed"] == round(rd.speed_kmh * 100), r["pintu"] == rd.door_open, r["reefer"] == rd.reefer_on,
            r["harsh"] == rd.harsh_events]
    if r["temp_ok"]:
        sama.append(r["temp"] == round(rd.temp_c * 100))
    if rd.solar_radiation is not None:
        sama.append(r["solar"] == round(rd.solar_radiation * 16))
    return all(sama)


def periksa(kunci: bytes | None, rek: bytes, rantai: bytes, paket: bytes, mac: bytes, prev: bytes | None,
            rd: TelemetryReading | None) -> str:
    """prev = rantai rekaman seq-1 (NOL untuk seq 0), None bila belum diterima. rd None = rekaman tanpa bacaan."""
    if kunci is None:
        return "TANPA_KUNCI"
    if not hmac.compare_digest(hmac.new(kunci, rantai + paket, hashlib.sha256).digest(), mac):
        return "MAC_SALAH"
    r = baca_rekaman(rek)
    sesuai = not r["temp_ok"] if rd is None else cocok_dengan_bacaan(r, rd)
    if baca_paket(paket)["seq"] != r["seq"] or not sesuai:
        return "REKAMAN_BEDA"
    if prev is None:
        return "OK_RANTAI_BARU"
    return "OK" if hashlib.sha256(prev + rek).digest() == rantai else "RANTAI_PUTUS"


def urai(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Objek `edge` dari payload -> byte. None bila tidak ada atau formatnya salah."""
    e = raw.get("edge")
    if not isinstance(e, dict):
        return None
    try:
        out = {k: bytes.fromhex(e[k]) for k in ("rek", "rantai", "paket", "mac")}
    except (KeyError, TypeError, ValueError):
        return None
    if (len(out["rek"]), len(out["rantai"]), len(out["paket"]), len(out["mac"])) != (23, 32, 16, 32):
        return None
    skor = e.get("skor")
    out["skor"] = [int(s) for s in skor] if isinstance(skor, list) and len(skor) == len(KELAS_CHIP) else None
    return out


INSERT = ("INSERT INTO edge_results (truck_id, ts, device_id, seq_rek, rek, rantai, paket, mac, skor, verifikasi) "
          "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (truck_id, ts) DO NOTHING")


def simpan(conn, truck_id: str, device_id: str | None, raw: list[dict[str, Any]], ok: list[TelemetryReading],
           kunci: dict[str, bytes] | None = None, tanpa_bacaan: list[dict[str, Any]] | None = None) -> dict[str, int]:
    """Verifikasi dan simpan objek `edge` dari bacaan yang lolos validasi dan dari `rekaman_tanpa_bacaan`.
    Kembalikan hitungan per hasil verifikasi."""
    from psycopg.types.json import Jsonb

    kunci = kunci_perangkat() if kunci is None else kunci
    per_ts = {r.ts: r for r in ok}
    item = []
    for b in raw:
        e = urai(b)
        if e is None:
            continue
        try:
            ts = TelemetryReading.model_validate({k: v for k, v in b.items() if k != "edge"}).ts
        except ValueError:
            continue
        if ts in per_ts:
            item.append((baca_rekaman(e["rek"])["seq"], ts, e))
    for b in tanpa_bacaan or []:
        e = urai(b if isinstance(b, dict) and "edge" in b else {"edge": b})
        if e is not None:
            r = baca_rekaman(e["rek"])
            item.append((r["seq"], datetime.fromtimestamp(r["ts"], UTC), e))
    hitung: dict[str, int] = {}
    if not item:
        return hitung
    rantai_batch = {}
    with conn.cursor() as cur:
        for seq, ts, e in sorted(item, key=lambda x: (x[0], x[1])):
            if seq == 0:
                prev = NOL
            elif seq - 1 in rantai_batch:
                prev = rantai_batch[seq - 1]
            else:
                row = cur.execute("SELECT rantai FROM edge_results WHERE truck_id = %s AND seq_rek = %s AND ts < %s "
                                  "ORDER BY ts DESC LIMIT 1", (truck_id, seq - 1, ts)).fetchone()
                prev = bytes(row[0]) if row else None
            v = periksa(kunci.get(device_id or ""), e["rek"], e["rantai"], e["paket"], e["mac"], prev, per_ts.get(ts))
            if v in SAH:
                rantai_batch[seq] = e["rantai"]
            cur.execute(INSERT, (truck_id, ts, device_id, seq, e["rek"], e["rantai"], e["paket"], e["mac"],
                                 Jsonb(e["skor"]) if e["skor"] else None, v))
            hitung[v] = hitung.get(v, 0) + 1
            if v not in SAH:
                logger.warning("%s %s: hasil edge %s", truck_id, ts.isoformat(), v)
    conn.commit()
    return hitung


def muat_terakhir(cur, truck_id: str, ts: datetime) -> dict[str, Any] | None:
    """Hasil edge sah untuk menit `ts` (bacaan terakhir jendela), atau None."""
    row = cur.execute("SELECT paket, skor, verifikasi, rantai FROM edge_results WHERE truck_id = %s AND ts = %s "
                      "AND verifikasi = ANY(%s)", (truck_id, ts, list(SAH))).fetchone()
    if row is None:
        return None
    if isinstance(row, dict):
        return {**row, "paket": bytes(row["paket"]), "rantai": bytes(row["rantai"])}
    return {"paket": bytes(row[0]), "skor": row[1], "verifikasi": row[2], "rantai": bytes(row[3])}


ALASAN_TEKS = {0: "Kondisi normal.", 1: "Suhu muatan di luar batas aman.",
               3: "Suhu mendekati atau melewati batas atas.", 4: "Pintu terbuka. Tutup pintu.",
               5: "Sensor rusak. Verifikasi manual diperlukan; sisa waktu tidak ditampilkan.",
               6: "Sensor mencurigakan. Verifikasi manual."}


def _peluang(skor: list[int] | None, p: dict[str, Any]) -> dict[str, float] | None:
    """Softmax skor Q8.16; dipakai hanya bila konsisten dengan kelas dan skor teratas yang di-MAC."""
    if not skor:
        return None
    top = max(range(len(skor)), key=lambda i: (skor[i], -i))
    if top != p["kelas"] or ((skor[top] >> 8) & 0xFFFF) != (p["skor_atas"] & 0xFFFF):
        return None
    z = [s / 65536 for s in skor]
    m = max(z)
    e = [math.exp(x - m) for x in z]
    return {V3_API_LABEL[k]: round(v / sum(e), 4) for k, v in zip(KELAS_CHIP, e, strict=True)}


def kondisi(hasil: dict[str, Any], cargo_profile: str, mass_kg: float | None, jendela: Jendela) -> dict[str, Any]:
    """Keluaran provider kondisi (bentuk sama dengan app/models/condition.py) dari paket chip yang sah."""
    p = baca_paket(hasil["paket"])
    status = NAMA_STATUS.get(p["status"], "WASPADA")
    ttb = float(p["ttb"]) if p["ttb_valid"] else None
    alasan = (f"Muatan diperkirakan melewati batas dalam {p['ttb']} menit." if p["alasan"] == 2
              else ALASAN_TEKS.get(p["alasan"], "Kondisi normal."))
    lo, hi = SENSOR_RISK_BAND if p["sensor"] >= 1 else RISK_BAND[status]
    risiko = round(min(max(1.0 - min(ttb if ttb is not None else TTB_MAX, TTB_MAX) / TTB_MAX, lo), hi), 2)
    data_lengkap = jendela.data_lengkap and p["diag_valid"]
    fm = None
    if p["diag_valid"]:
        prob = _peluang(hasil.get("skor"), p)
        label = V3_API_LABEL[KELAS_CHIP[p["kelas"]]]
        conf = prob[label] if prob else 1.0
        pintu = bool(jendela.readings and jendela.readings[-1].door_open)
        fm = {**_guard_label(label, conf, p["sensor"], status, pintu), "probabilities": prob}
        if not prob:
            fm["confidence"] = None
    out = {"status": status, "reason": alasan, "risk_index": risiko, "time_to_breach_min": ttb,
           "ttb_model_min": None, "sensor_status": p["sensor"], "forecast": None, "failure_mode": fm,
           "data_lengkap": data_lengkap, "catatan_data": jendela.catatan(),
           "t_cargo_est": round(p["tc_c"], 3), "t_hi": cargo_params(cargo_profile, mass_kg)["t_hi"],
           "model_version": "rtl-xgb_v5_context_duty", "provider": PROVIDER, "series": None,
           "edge": {"verifikasi": hasil["verifikasi"], "menit": p["menit"], "seq": p["seq"],
                    "rantai": hasil["rantai"].hex()}}
    if not data_lengkap and status == "AMAN":
        out["status"] = "DATA_TIDAK_LENGKAP"
    return out
