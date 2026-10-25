"""Pembungkus cocotb_tools.runner: satu pemanggilan per modul uji.

Simulator bawaan Verilator dari OSS CAD Suite (~/FPGA/tools/oss-cad-suite); ganti dengan
SIM=icarus. Hasil build di hw/build/<toplevel>_<sim>/ (tidak dikomit).
"""

import os
from pathlib import Path

HW = Path(__file__).resolve().parent.parent
RTL = HW / "rtl"
OSS = Path(os.environ.get("OSS_CAD_SUITE", Path.home() / "FPGA" / "tools" / "oss-cad-suite"))


def jalankan(toplevel, sources, test_module, parameters=None, sim=None, waves=False):
    from cocotb_tools.runner import get_runner

    sim = sim or os.environ.get("SIM", "verilator")
    if (OSS / "bin").exists() and str(OSS / "bin") not in os.environ["PATH"]:
        os.environ["PATH"] = f"{OSS / 'bin'}{os.pathsep}{os.environ['PATH']}"
    build = HW / "build" / f"{toplevel}_{sim}"
    args = ["-Wno-fatal", "--timing"] if sim == "verilator" else []
    runner = get_runner(sim)
    runner.build(sources=[RTL / s for s in sources], hdl_toplevel=toplevel, build_dir=build,
                 parameters=parameters or {}, build_args=args, timescale=("1ns", "1ps"),
                 waves=waves, always=True)
    runner.test(hdl_toplevel=toplevel, test_module=test_module, build_dir=build,
                test_dir=Path(__file__).resolve().parent, waves=waves)
