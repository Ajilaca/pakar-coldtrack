"""Inventaris memori coldtrack_top per mode (BRAM vs flash) lewat Yosys, tanpa pemetaan ke gate.

Memori yang tersisa setelah `memory -nomap` adalah yang di ASIC harus jadi makro SRAM, DFFRAM, atau ROM logika.
Ringan (tidak ada sintesis penuh), jadi aman dijalankan di laptop. Hasil JSON di hw/build/asic_mem_m<mode>.json.

  python -m hw.scripts.asic_mem               # kedua mode
  python -m hw.scripts.asic_mem --mode 1
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

HW = Path(__file__).resolve().parents[1]
OSS = Path(os.environ.get("OSS_CAD_SUITE", Path.home() / "FPGA" / "tools" / "oss-cad-suite"))
RTL = ["sha256_core", "seal", "physics", "floor_div", "features", "tree_engine", "sha256_stream", "qspi_reader",
       "tree_stream", "model_flash", "coldtrack_top"]
MODEL = "model/xgb_v5_context_duty"


def inventaris(mode):
    h = (HW / MODEL / "flash.sha256").read_text().strip()
    out = HW / "build" / f"asic_mem_m{mode}.json"
    out.parent.mkdir(exist_ok=True)
    berkas = " ".join(f"rtl/{r}.sv" for r in RTL)
    skrip = (f"read_verilog -sv {berkas}; chparam -set MODEL_FLASH {mode} -set HASH_MODEL 256'h{h} "
             f'-set BERKAS_SIMPUL "{MODEL}/nodes.mem" -set BERKAS_POHON "{MODEL}/trees.mem" '
             f'-set BERKAS_BASE "{MODEL}/base.mem" coldtrack_top; hierarchy -top coldtrack_top; proc; flatten; '
             f"opt -fast; memory -nomap; opt -fast; select t:$mem_v2; write_json -selected {out}")
    env = {**os.environ, "PATH": f"{OSS / 'bin'}{os.pathsep}{os.environ['PATH']}"}
    subprocess.run(["yosys", "-q", "-p", skrip], cwd=HW, env=env, check=True, stderr=subprocess.DEVNULL)
    mem = []
    for mod in json.loads(out.read_text())["modules"].values():
        for c in mod["cells"].values():
            p = c["parameters"]
            nama = p["MEMID"].replace("\\", "").replace("$flatten", "")
            rom = "proc_rom" in nama
            mem.append((nama, int(p["SIZE"], 2), int(p["WIDTH"], 2), rom))
    return mem


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", type=int, choices=(0, 1))
    a = ap.parse_args()
    for mode in [a.mode] if a.mode is not None else [0, 1]:
        print(f"MODEL_FLASH={mode}")
        tot = ram = 0
        for nama, kedalaman, lebar, rom in inventaris(mode):
            b = kedalaman * lebar
            tot += b
            ram += 0 if rom else b
            print(f"  {nama[-44:]:44s} {kedalaman:6d} x {lebar:3d} = {b:7d} bit{'  (ROM konstanta)' if rom else ''}")
        print(f"  total {tot / 8192:.1f} KiB, RAM tulis {ram / 8192:.1f} KiB\n")


if __name__ == "__main__":
    main()
