"""Jam bersama sistem armada.

Produksi: jam dinding UTC. Dev dengan simulator truk virtual: jam simulasi yang dipercepat
SIM_SPEED kali, berjangkar pada SIM_ANCHOR (ISO-8601 UTC) yang SAMA untuk semua layanan
(simulator, worker inferensi, API), supaya deteksi "tidak ada data" dan cap waktu bacaan konsisten:

    sim_now = SIM_ANCHOR + (wall_now - SIM_ANCHOR) * SIM_SPEED

Tanpa SIM_SPEED (atau SIM_SPEED=1) jam = jam dinding.
"""

import os
from datetime import UTC, datetime


def speed() -> float:
    return float(os.environ.get("SIM_SPEED", "1") or 1)


def _anchor() -> datetime:
    return datetime.fromisoformat(os.environ.get("SIM_ANCHOR", "2026-10-11T00:00:00+00:00"))


def now() -> datetime:
    wall = datetime.now(UTC)
    s = speed()
    if s == 1:
        return wall
    a = _anchor()
    return a + (wall - a) * s


def wall_seconds_for(sim_seconds: float) -> float:
    """Berapa detik jam dinding untuk sekian detik jam simulasi (untuk jeda simulator/worker)."""
    return sim_seconds / speed()
