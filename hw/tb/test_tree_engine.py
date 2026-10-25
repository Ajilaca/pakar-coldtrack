"""tree_engine: skor 7 kelas dan argmax harus identik bit per bit dengan hw/golden/pohon.py.

Fitur diambil dari jendela val acak (fitur bilangan bulat golden). Model #8 dimuat dari berkas .mem
saat elaborasi; model #7 kemudian ditulis host lewat port simpul_/pohon_/base_ (ganti model tanpa sintesis).
"""

import os
import sys
from pathlib import Path

import cocotb
import numpy as np
import pandas as pd
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge

HW = Path(__file__).resolve().parent.parent
ROOT = HW.parent
sys.path.insert(0, str(ROOT))
from hw.golden import pohon as ph

B8, B9 = "b8_xgb_chip_v5_konteks", "b9_xgb_chip_v5_konteks_duty_sintetis"
SW, N_JENDELA = 32, int(os.environ.get("N_JENDELA", "120"))


def kasus(duty, n, seed):
    """n jendela val acak -> (fitur int, skor golden, kelas golden)."""
    from bench import b8_lib as b8
    from hw.golden.uji_pohon import duty_trip

    d = b8.muat("val")
    df = pd.read_parquet(ROOT / "data/processed/v4_seed1000_700trips.parquet")
    m = ph.muat_model(ROOT / f"bench/results/lokal-cpu/B10/{B9 if duty else B8}.json", duty)
    out = []
    for i in np.random.default_rng(seed).choice(len(d["trip"]), n, replace=False):
        tid, t = int(d["trip"][i]), int(d["menit"][i])
        g = df[df.trip_id == tid].sort_values("minute").reset_index(drop=True)
        q = ph.ffill_temp(ph.kuantisasi_trip(g, duty_trip(g, tid) if duty else None))
        f = ph.fitur_bulat(q, t, duty)
        out.append((f, ph.skor_bulat(m, f), ph.kelas_bulat(m, f)))
    return out


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    for s in ("rst_n", "fitur_we", "fitur_addr", "fitur_data", "simpul_we", "simpul_addr", "simpul_data",
              "pohon_we", "pohon_addr", "pohon_data", "base_we", "base_addr", "base_data", "start"):
        getattr(dut, s).value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)


async def tulis(dut, we, addr, data, pasangan):
    getattr(dut, we).value = 1
    for a, v in pasangan:
        getattr(dut, addr).value = a
        getattr(dut, data).value = v
        await FallingEdge(dut.clk)
    getattr(dut, we).value = 0


async def jalankan(dut, f):
    await tulis(dut, "fitur_we", "fitur_addr", "fitur_data", list(enumerate(f)))
    dut.start.value = 1
    await FallingEdge(dut.clk)
    dut.start.value = 0
    for siklus in range(20000):
        await FallingEdge(dut.clk)
        if dut.done.value:
            break
    else:
        raise AssertionError("done tidak muncul")
    raw = int(dut.skor.value)
    skor = [((raw >> (k * SW)) & ((1 << SW) - 1)) for k in range(7)]
    return [s - (1 << SW) if s >> (SW - 1) else s for s in skor], int(dut.kelas.value), siklus


async def cek(dut, data, nama):
    siklus_maks = 0
    for n, (f, skor_g, kelas_g) in enumerate(data):
        skor, kelas, siklus = await jalankan(dut, f)
        assert skor == skor_g, f"{nama} jendela {n}: skor {skor} != golden {skor_g}"
        assert kelas == kelas_g, f"{nama} jendela {n}: kelas {kelas} != {kelas_g}"
        siklus_maks = max(siklus_maks, siklus)
    dut._log.info(f"{nama}: {len(data)} jendela identik, maks {siklus_maks} siklus per inferensi")


@cocotb.test()
async def model_b9_dari_berkas_lalu_b8_dari_host(dut):
    await reset(dut)
    await cek(dut, kasus(True, N_JENDELA, 11), "b9 (berkas .mem)")

    folder = HW / "model" / B8
    simpul = [int(x, 16) for x in (folder / "simpul.mem").read_text().split()]
    pohon = [int(x, 16) for x in (folder / "pohon.mem").read_text().split()]
    base = [int(x, 16) for x in (folder / "base.mem").read_text().split()]
    await tulis(dut, "simpul_we", "simpul_addr", "simpul_data", list(enumerate(simpul)))
    await tulis(dut, "pohon_we", "pohon_addr", "pohon_data", list(enumerate(pohon)))
    await tulis(dut, "base_we", "base_addr", "base_data", list(enumerate(base)))
    await cek(dut, kasus(False, N_JENDELA, 12), "b8 (dimuat host)")


def test_tree_engine():
    from runner import jalankan

    folder = HW / "model" / B9
    jalankan("tree_engine", ["tree_engine.sv"], "test_tree_engine",
             parameters={"BERKAS_SIMPUL": f'"{folder / "simpul.mem"}"', "BERKAS_POHON": f'"{folder / "pohon.mem"}"',
                         "BERKAS_BASE": f'"{folder / "base.mem"}"'})
