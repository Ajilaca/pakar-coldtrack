"""Pelari 'FPGA saja': skenario data dari skrip Python -> chip (hitung dan segel) -> MQTT ke cloud + log lokal.

Tanpa sensor. Data per menit dibaca dari CSV buatan `hw/driver/skenario.py`. Dependensi ringan untuk KV260:
numpy, paho-mqtt, pyyaml (`edge_driver.py` butuh pandas, parquet, dan paket backend). Chip dipilih lewat --chip:
axi (KV260, butuh root dan bitstream termuat), spi (chip ASIC), golden (emulasi bit-exact, tanpa board).

  python -m hw.driver.fpga_only --skenario hw/driver/skenario/pintu_terbuka.csv --chip golden --tanpa-mqtt
  sudo python -m hw.driver.fpga_only --skenario hw/driver/skenario/pintu_terbuka.csv --chip axi --kunci <64 hex>

Cap waktu bacaan = menit sekarang + 60 detik per sampel. Dengan --jeda < 60 dan MQTT aktif, cap waktu melaju lebih
cepat dari jam dinding, dan cloud dengan SIM_SPEED=1 bisa menganggapnya data masa depan.
Env: MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD, API_URL (opsional, untuk mendaftarkan trip).
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hw.driver.chip import ChipAxi, ChipGolden, ChipSpi, Sampel
from hw.golden import seal as sg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("coldtrack.fpga_only")

MODEL = ROOT / "bench/results/local-cpu/B10/b9_xgb_chip_v5_context_synthetic_duty.json"
KOLOM = ("menit", "temp", "temp_ok", "rh", "amb", "solar", "speed", "door", "reefer", "duty", "harsh")
WIB = timedelta(hours=7)


def profil(nama: str, massa: float | None) -> dict:
    """Parameter fisika chip dari backend/config.yaml; aturan sama dengan app.inference.cargo_params."""
    import yaml

    cfg = yaml.safe_load((ROOT / "backend" / "config.yaml").read_text(encoding="utf-8"))["cargo_profiles"]
    p = cfg.get(nama, cfg["vaksin_2_8C"])
    lo, hi = float(p["min_temp_c"]), float(p["max_temp_c"])
    return {"t_lo": lo, "t_hi": hi, "t_set": float(p.get("t_set_c", lo + 0.4 * (hi - lo))),
            "c": float(p["c_kj_kgc"]), "mass_kg": float(massa or p.get("mass_kg_default", 1000.0))}


def muat_skenario(path: Path) -> tuple[dict, list[dict]]:
    """CSV skenario -> (metadata dari baris '# kunci=nilai', daftar baris bilangan bulat satuan rekaman)."""
    meta, baris = {}, []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            if ln.startswith("#"):
                for kv in ln[1:].split():
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        meta[k] = v
            elif ln.strip():
                baris.append(ln)
    rd = csv.DictReader(baris)
    if tuple(rd.fieldnames or ()) != KOLOM:
        raise SystemExit(f"{path}: kolom harus {KOLOM}, ditemukan {rd.fieldnames}")
    return meta, [{k: int(v) for k, v in r.items()} for r in rd]


def sampel_dari_baris(r: dict, ts: datetime, jam_mulai: float | None = None) -> Sampel:
    """jam_mulai: jam lokal skenario pada menit 0, supaya fitur jam cocok dengan radiasi dan suhu luar skenario.
    None = jam dinding WIB dari ts (untuk sensor sungguhan)."""
    jam_lokal = (ts + WIB).hour if jam_mulai is None else int((jam_mulai + r["menit"] / 60) % 24)
    return Sampel(seq=r["menit"], ts=int(ts.timestamp()), temp=r["temp"] if r["temp_ok"] else None, rh=r["rh"],
                  amb=r["amb"], solar=r["solar"], speed=r["speed"], door=bool(r["door"]), reefer=bool(r["reefer"]),
                  duty=r["duty"], harsh=r["harsh"], hour=jam_lokal)


def bacaan(s: Sampel, ts: datetime) -> dict | None:
    """Bacaan kontrak MQTT dari nilai yang sama persis dengan yang masuk chip."""
    if s.temp is None:
        return None
    return {"ts": ts.isoformat().replace("+00:00", "Z"), "temp_c": s.temp / 100, "humidity": s.rh / 100,
            "ambient_c": s.amb / 100, "door_open": s.door, "reefer_on": s.reefer, "speed_kmh": s.speed / 100,
            "harsh_events": s.harsh, "solar_radiation": s.solar / 16}


def buat_chip(nama: str):
    return {"golden": lambda: ChipGolden(MODEL), "axi": ChipAxi, "spi": ChipSpi}[nama]()


def api(base: str, metode: str, path: str, body: dict) -> dict:
    req = urllib.request.Request(base.rstrip("/") + path, data=json.dumps(body).encode(), method=metode,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skenario", required=True, type=Path)
    ap.add_argument("--chip", choices=["golden", "axi", "spi"], default="golden")
    ap.add_argument("--kunci", default=os.environ.get("EDGE_KEY", ""), help="kunci HMAC perangkat, 64 hex")
    ap.add_argument("--truck", default="B 3036 WN", help="nomor polisi truk yang sudah terdaftar di cloud")
    ap.add_argument("--device", default="DEV-001", help="harus sama dengan nama di EDGE_KEYS cloud")
    ap.add_argument("--profil", help="timpa profil kargo dari metadata CSV")
    ap.add_argument("--massa", type=float, help="massa muatan kg (bawaan profil)")
    ap.add_argument("--depot", default="JKT")
    ap.add_argument("--jeda", type=float, default=60.0, help="detik antar sampel (bawaan 60)")
    ap.add_argument("--log", type=Path, help="log JSONL bacaan tersegel (bawaan hw/driver/log/)")
    ap.add_argument("--jam-dinding", action="store_true",
                    help="fitur jam dari jam dinding WIB, bukan dari jam_mulai skenario")
    ap.add_argument("--tanpa-mqtt", action="store_true", help="hanya chip dan log lokal, tidak kirim ke cloud")
    a = ap.parse_args()

    kunci = bytes.fromhex(a.kunci) if a.kunci else b""
    if len(kunci) != 32:
        sys.exit("--kunci harus 32 byte (64 hex), sama dengan EDGE_KEYS di worker-ingest")
    meta, baris = muat_skenario(a.skenario)
    nama_profil = a.profil or meta.get("profil", "vaksin_2_8C")
    prod = profil(nama_profil, a.massa or (float(meta["massa"]) if "massa" in meta else None))
    jam_skenario = None if a.jam_dinding else float(meta.get("jam_mulai", 9.0))
    key = a.truck.replace(" ", "").upper()
    awal = datetime.now(UTC).replace(second=0, microsecond=0)
    log = a.log or ROOT / "hw/driver/log" / f"{key}_{awal:%Y%m%dT%H%MZ}.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)

    chip = buat_chip(a.chip)
    cl = None
    if not a.tanpa_mqtt:
        import paho.mqtt.client as mqtt

        cl = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"fpga-{key}")
        cl.username_pw_set(os.environ.get("MQTT_USER", "simulator"), os.environ.get("MQTT_PASSWORD", ""))
        status = {"schema": "coldtrack.status.v1", "device_id": a.device, "firmware": "fpga-only-0.1",
                  "gateway_version": "0.1", "battery_v": 2.9}
        cl.will_set(f"coldtrack/v1/{key}/status", json.dumps({**status, "online": False}), qos=1, retain=True)
        cl.connect(os.environ.get("MQTT_HOST", "localhost"), int(os.environ.get("MQTT_PORT", "1883")))
        cl.loop_start()
        cl.publish(f"coldtrack/v1/{key}/status", json.dumps({**status, "online": True, "ts": awal.isoformat()}),
                   qos=1, retain=True)

    trip_id = None
    if os.environ.get("API_URL") and not a.tanpa_mqtt:
        trip_id = api(os.environ["API_URL"], "POST", "/api/v1/trips",
                      {"truck_id": a.truck, "cargo_profile": nama_profil, "mass_kg": prod["mass_kg"],
                       "depot_id": a.depot, "started_at": awal.isoformat()})["trip_id"]

    logger.info("%s: skenario %s (%d menit), profil %s, chip %s, log %s", a.truck, meta.get("nama", a.skenario.stem),
                len(baris), nama_profil, a.chip, log)
    chip.mulai_trip(prod, kunci)
    rekaman_semua, hasil = [], None
    with open(log, "w", encoding="utf-8") as lf:
        for r in baris:
            t0 = time.monotonic()
            ts = awal + timedelta(minutes=r["menit"])
            s = sampel_dari_baris(r, ts, jam_skenario)
            hasil = chip.proses(s)
            rekaman_semua.append(hasil.rek)
            e = {"rek": hasil.rek.hex(), "rantai": hasil.rantai.hex(), "paket": hasil.paket.hex(),
                 "mac": hasil.mac.hex(), "skor": hasil.skor}
            b = bacaan(s, ts)
            payload = {"schema": "coldtrack.telemetry.v1", "device_id": a.device, "seq": r["menit"] + 1, "readings": []}
            if b is not None:
                payload["readings"] = [{**b, "edge": e}]
            else:                                 # bacaan suhu gagal: rekaman tetap disegel, rantai tidak terputus
                payload["rekaman_tanpa_bacaan"] = [e]
            lf.write(json.dumps({"hasil": {"status": hasil.status, "diag_valid": hasil.diag_valid,
                                           "kelas": hasil.kelas}, "payload": payload}) + "\n")
            lf.flush()
            if cl is not None:
                cl.publish(f"coldtrack/v1/{key}/telemetry", json.dumps(payload), qos=1)
            if r["menit"] % 10 == 0:
                logger.info("menit %d: temp %s, status %d, diagnosis %s", r["menit"],
                            f"{s.temp / 100:.2f}" if s.temp is not None else "gagal", hasil.status,
                            hasil.kelas if hasil.diag_valid else "-")
            time.sleep(max(0.0, a.jeda - (time.monotonic() - t0)))

    ok = sg.verifikasi(kunci, rekaman_semua, hasil.rantai, hasil.paket, hasil.mac)
    logger.info("rantai segel dan MAC menit terakhir %s", "SAH" if ok else "TIDAK SAH")
    if cl is not None:
        cl.loop_stop()
        cl.disconnect()
    if trip_id:
        api(os.environ["API_URL"], "PATCH", f"/api/v1/trips/{trip_id}", {"ended_at": datetime.now(UTC).isoformat()})
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
