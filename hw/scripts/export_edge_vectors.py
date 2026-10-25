"""Vektor uji hasil edge untuk backend (backend/tests/fixtures/edge_vectors.json).

Menjalankan chip golden (hw/driver/chip.py, identik bit per bit dengan RTL) atas 140 menit pertama trip seed
satu truk armada (trip A1), lalu menyimpan payload bacaan + objek `edge` persis seperti yang dikirim driver.

  python -m hw.scripts.export_edge_vectors
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from hw.driver.chip import ChipGolden
from hw.driver.edge_driver import MODEL, bacaan, sampel, trip_truk

TRUK, N = "E 8659 FR", 140              # trip A1 (pintu terbuka) mulai menit 69
KUNCI = bytes(range(0x40, 0x60))
T0 = pd.Timestamp("2030-02-01T06:00:00Z")
OUT = ROOT / "backend/tests/fixtures/edge_vectors.json"


def main():
    from app.inference import cargo_params

    trip, device, _, q = trip_truk(TRUK)
    chip = ChipGolden(MODEL)
    chip.mulai_trip(cargo_params(trip["cargo_profile"], trip["mass_kg"]), KUNCI)
    rows = []
    for t in range(N):
        ts = T0 + pd.Timedelta(minutes=t)
        h = chip.proses(sampel(q, t, ts))
        b = bacaan(q, t, ts)
        if b is None:
            continue
        b["edge"] = {"rek": h.rek.hex(), "rantai": h.rantai.hex(), "paket": h.paket.hex(), "mac": h.mac.hex(),
                     "skor": h.skor}
        rows.append({"bacaan": b, "harapan": {"status": h.status, "diag_valid": h.diag_valid, "kelas": h.kelas}})
    OUT.write_text(json.dumps({"truck_id": TRUK, "device_id": device["id"], "kunci": KUNCI.hex(),
                               "cargo_profile": trip["cargo_profile"], "mass_kg": trip["mass_kg"],
                               "sumber_trip_v4": trip["sumber_trip_v4"], "menit": rows}, indent=1) + "\n")
    print(OUT, len(rows), "menit")


if __name__ == "__main__":
    main()
