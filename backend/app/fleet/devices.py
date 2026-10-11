"""Panel "Perlu diperbarui": temuan per perangkat (hardware/software). Ambang di config.yaml fleet.perangkat [ASUMSI]."""

from datetime import date, datetime, timedelta
from typing import Any


def _versi(v: str | None) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in str(v).split("."))
    except ValueError:
        return ()


def perlu_diperbarui(device: dict[str, Any], sensor_health: dict[str, Any] | None, now: datetime,
                     cfg: dict[str, Any], last_ts: datetime | None = None) -> list[dict[str, Any]]:
    """device: baris tabel devices. Kembalikan daftar {jenis, kode, tingkat, pesan}."""
    out = []

    def tambah(jenis, kode, tingkat, pesan):
        out.append({"jenis": jenis, "kode": kode, "tingkat": tingkat, "pesan": pesan})

    fw, fw_baru = device.get("firmware"), cfg.get("firmware_terbaru")
    if fw and fw_baru and _versi(fw) < _versi(fw_baru):
        tambah("software", "firmware_usang", "waspada", f"Firmware {fw} -> {fw_baru}.")
    gw, gw_baru = device.get("gateway_version"), cfg.get("gateway_terbaru")
    if gw and gw_baru and _versi(gw) < _versi(gw_baru):
        tambah("software", "gateway_usang", "waspada", f"Gateway {gw} -> {gw_baru}.")

    kal = device.get("calibrated_at")
    if isinstance(kal, str):
        kal = date.fromisoformat(kal)
    maks = int(cfg.get("kalibrasi_maks_hari", 180))
    if kal is not None and (now.date() - kal).days > maks:
        tambah("hardware", "kalibrasi", "waspada",
               f"Kalibrasi terakhir {kal.isoformat()} ({(now.date() - kal).days} hari, batas {maks} hari).")

    b = device.get("battery_v")
    if b is not None and b < 2.4:
        tambah("hardware", "baterai", "kritis", f"Baterai {b:.2f} V (< 2,4 V). Ganti baterai.")
    elif b is not None and b < 2.6:
        tambah("hardware", "baterai", "waspada", f"Baterai {b:.2f} V (< 2,6 V).")

    skor = (sensor_health or {}).get("score")
    if skor is not None and skor < int(cfg.get("skor_sensor_min", 50)):
        tambah("hardware", "sensor", "kritis", f"Skor kesehatan sensor {skor} ({sensor_health.get('grade')}).")

    terakhir = last_ts or device.get("last_status_at")
    jam = float(cfg.get("offline_lama_jam", 24))
    if not device.get("online") and terakhir is not None and now - terakhir > timedelta(hours=jam):
        tambah("hardware", "offline_lama", "kritis", f"Perangkat offline sejak {terakhir:%Y-%m-%d %H:%M} UTC.")
    return out
