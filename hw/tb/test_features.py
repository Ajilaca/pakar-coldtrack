"""fitur: 82 fitur per menit identik dengan hw/golden/trees.fitur_bulat, flag siap/lengkap sesuai golden.

Trip val diputar menit demi menit (berbagai mode, termasuk A6 dengan bacaan hilang) sampai lewat menit
240 agar jendela konteks 240 menit benar-benar bergeser.
"""

import os
import sys
from pathlib import Path

import cocotb
import pandas as pd
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hw.golden import trees as ph

FW = 48
MENIT = int(os.environ.get("MENIT_FITUR", "300"))
BATAS_DONE = int(os.environ.get("BATAS_DONE_FITUR", "5000"))   # versi ASIC (kuadrat serial) butuh lebih lama
MODE = ["A0", "A1", "A6", "A8", "A2", "A7"]


def trip_uji():
    from hw.golden.check_trees import duty_trip

    df = pd.read_parquet(ROOT / "data/processed/v4_seed1000_700trips.parquet")
    val = df[df.split == "val"]
    mode = val.groupby("trip_id")["failure_mode"].agg(lambda s: ([m for m in s.unique() if m != "A0"] + ["A0"])[0])
    for md in MODE:
        tid = int(mode[mode == md].index[0])
        g = val[val.trip_id == tid].sort_values("minute").reset_index(drop=True)
        q = ph.ffill_temp(ph.kuantisasi_trip(g, duty_trip(g, tid)))
        yield md, tid, q


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    for s in ("rst_n", "trip_reset", "sampel", "temp_ok", "temp", "amb", "solar", "rh", "speed", "duty", "door",
              "reefer", "harsh", "hour"):
        getattr(dut, s).value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)


def s(v, bits):
    v = int(v)
    return v - (1 << bits) if v >> (bits - 1) else v


@cocotb.test()
async def trip_val(dut):
    await reset(dut)
    total = 0
    for md, tid, q in trip_uji():
        dut.trip_reset.value = 1
        await FallingEdge(dut.clk)
        dut.trip_reset.value = 0
        n = min(MENIT, len(q["temp"]))
        for t in range(n):
            dut.temp_ok.value = int(not q["nan"][t])
            dut.temp.value = int(q["temp"][t]) & 0xFFFF
            dut.amb.value = int(q["amb"][t]) & 0xFFFF
            dut.solar.value = int(q["solar"][t])
            dut.rh.value = int(q["rh"][t])
            dut.speed.value = int(q["speed"][t])
            dut.duty.value = int(q["duty"][t])
            dut.door.value = int(q["door"][t])
            dut.reefer.value = int(q["reefer"][t])
            dut.harsh.value = int(q["harsh"][t])
            dut.hour.value = int(q["hour"][t])
            dut.sampel.value = 1
            await FallingEdge(dut.clk)
            dut.sampel.value = 0
            f = {}
            for _ in range(BATAS_DONE):
                if dut.fitur_we.value:
                    f[int(dut.fitur_addr.value)] = s(dut.fitur_data.value, FW)
                if dut.done.value:
                    break
                await FallingEdge(dut.clk)
            else:
                raise AssertionError(f"trip {tid} menit {t}: done tidak muncul")
            assert int(dut.menit.value) == t
            assert bool(dut.siap.value) == (t >= 59), f"siap menit {t}"
            if t < 59:
                assert not f
                continue
            a = t - 59
            lengkap_g = not q["nan"][max(0, a - 1) if a > 0 else 0:t + 1].any()
            assert bool(dut.lengkap.value) == lengkap_g, f"trip {tid} menit {t}: lengkap"
            assert sorted(f) == list(range(82))
            if lengkap_g:
                g = ph.fitur_bulat(q, t, True)
                beda = [i for i in range(82) if f[i] != g[i]]
                assert not beda, f"trip {tid} ({md}) menit {t}: fitur {beda[:5]} RTL {[f[i] for i in beda[:5]]} golden {[g[i] for i in beda[:5]]}"
                total += 1
        dut._log.info(f"trip {tid} ({md}): {n} menit identik dengan golden")
    dut._log.info(f"total {total} jendela lengkap identik")


def test_features():
    from runner import jalankan

    jalankan("features", ["floor_div.sv", "features.sv"], "test_features")
