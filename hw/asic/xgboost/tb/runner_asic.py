"""Runner tes versi ASIC: modul tes cocotb diambil dari hw/tb (golden dan skenario sama dengan versi FPGA),
DUT dibangun dari sumber hw/asic. Bedanya dengan hw/tb/runner.py:

- folder build terpisah (hw/build/asic_<toplevel>_<sim>/), jadi build FPGA tidak tertimpa;
- Verilator mengisi register tanpa reset (dan memori) dengan nilai acak (--x-initial unique +
  +verilator+rand+reset+2), sehingga logika yang diam-diam bergantung pada nilai reset nol ikut gagal.
"""

import os
import sys
from pathlib import Path

HW = Path(__file__).resolve().parents[3]
TB = HW / "tb"
sys.path.insert(0, str(TB))
from runner import OSS  # noqa: E402  (path OSS CAD Suite yang sama dengan runner FPGA)


def jalankan(toplevel, sources, test_module, parameters=None, sim=None, waves=False, extra_env=None, seed=1):
    """sources: path relatif hw/ (mis. "rtl/floor_div.sv", "asic/xgboost/rtl/features.sv", "tb/x.sv")."""
    from cocotb_tools.runner import get_runner

    sim = sim or os.environ.get("SIM", "verilator")
    if (OSS / "bin").exists() and str(OSS / "bin") not in os.environ["PATH"]:
        os.environ["PATH"] = f"{OSS / 'bin'}{os.pathsep}{os.environ['PATH']}"
    build = HW / "build" / f"asic_{toplevel}_{sim}"
    args, plus = [], []
    if sim == "verilator":
        args = ["-Wno-fatal", "--timing", "--x-initial", "unique", "--x-assign", "unique"]
        plus = ["+verilator+rand+reset+2", f"+verilator+seed+{seed}"]
    runner = get_runner(sim)
    runner.build(sources=[HW / s for s in sources], hdl_toplevel=toplevel, build_dir=build,
                 parameters=parameters or {}, build_args=args, timescale=("1ns", "1ps"),
                 waves=waves, always=True)
    runner.test(hdl_toplevel=toplevel, test_module=test_module, build_dir=build, test_dir=TB,
                waves=waves, plusargs=plus, extra_env=extra_env or {})
