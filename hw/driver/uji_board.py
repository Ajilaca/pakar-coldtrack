"""Uji penerimaan board: skenario yang sama dijalankan di chip dan di model golden berdampingan.

Setiap menit rekaman, rantai, paket, MAC, 7 skor, status, dan diagnosis harus identik bit per bit. Bitstream di
board harus memuat model yang sama dengan golden (model #8, b9_xgb_chip_v5_context_synthetic_duty).

  python -m hw.driver.uji_board --hanya-id --chip axi            # ID chip dan bit STATUS saja (butuh root)
  sudo python -m hw.driver.uji_board --chip axi                  # skenario penuh, chip vs golden
  python -m hw.driver.uji_board --chip golden                    # uji skrip ini tanpa board
"""

import argparse
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hw.driver.fpga_only import buat_chip, muat_skenario, profil, sampel_dari_baris

KUNCI_UJI = bytes(range(0x40, 0x60))
BIT_STATUS = ["busy", "hasil_valid", "mac_valid", "kunci_terkunci", "siap", "lengkap", "diag_valid", "model_sah",
              "mode_flash", "ramalan_terpasang"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--chip", choices=["golden", "axi", "spi"], default="axi")
    ap.add_argument("--skenario", type=Path, default=ROOT / "hw/driver/skenario/pintu_terbuka.csv")
    ap.add_argument("--hanya-id", action="store_true", help="hanya periksa ID chip dan tampilkan bit STATUS")
    a = ap.parse_args()

    chip = buat_chip(a.chip)                       # ChipAxi/ChipSpi sudah memeriksa ID 0x43540001
    if a.hanya_id:
        if a.chip == "golden":
            sys.exit("--hanya-id butuh chip sungguhan (axi atau spi)")
        from hw.golden import regmap as rm

        st = chip.baca(rm.STATUS)
        print(f"ID chip benar. STATUS = {st:#06x}")
        for i, n in enumerate(BIT_STATUS):
            print(f"  bit{i} {n:18s} {st >> i & 1}")
        return 0

    meta, baris = muat_skenario(a.skenario)
    prod = profil(meta.get("profil", "vaksin_2_8C"), float(meta["massa"]) if "massa" in meta else None)
    jam = float(meta.get("jam_mulai", 9.0))
    gold = buat_chip("golden")
    chip.mulai_trip(prod, KUNCI_UJI)
    gold.mulai_trip(prod, KUNCI_UJI)
    awal = datetime.now(UTC).replace(second=0, microsecond=0)
    for r in baris:
        s = sampel_dari_baris(r, awal + timedelta(minutes=r["menit"]), jam)
        hc, hg = chip.proses(s), gold.proses(s)
        if hc != hg:
            ac, ag = asdict(hc), asdict(hg)
            beda = {k: (ac[k], ag[k]) for k in ac if ac[k] != ag[k]}
            print(f"BEDA di menit {r['menit']}: {sorted(beda)}")
            for k, (x, y) in list(beda.items())[:3]:
                print(f"  {k}: chip={x!r}\n  {' ' * len(k)}  golden={y!r}")
            return 1
    print(f"LULUS: {len(baris)} menit identik antara chip ({a.chip}) dan golden ({a.skenario.stem})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
