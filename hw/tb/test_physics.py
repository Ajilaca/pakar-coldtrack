"""fisika: semua keluaran per menit identik bit per bit dengan hw/golden/physics.MesinFisika.

Data: 5 skenario demo + trip train/val pilihan (berbagai mode dan muatan, termasuk beku), diputar
menit demi menit seperti di truk.
"""

import os
import sys
from collections import Counter
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
from hw.golden import physics as fx

PER_MODE = int(os.environ.get("TRIP_PER_MODE", "2"))


def data_uji():
    import pandas as pd

    from hw.golden.check_physics import sumber

    df = pd.read_parquet(ROOT / "data/processed/v4_seed1000_700trips.parquet")
    mode = df.groupby("trip_id")["failure_mode"].agg(lambda s: ([m for m in s.unique() if m != "A0"] + ["A0"])[0])
    jatah = {m: PER_MODE for m in mode.unique()}
    for jenis, nama, ts, amb, door, mov, prod in sumber():
        if jenis == "trip":
            if jatah[mode[nama]] == 0:
                continue
            jatah[mode[nama]] -= 1
            nama = f"trip {nama} ({mode[nama]})"
        yield nama, ts, amb, door, mov, prod


def s(v, bits):
    v = int(v)
    return v - (1 << bits) if v >> (bits - 1) else v


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    for sig in ("rst_n", "trip_reset", "sampel", "ts_raw", "t_amb", "pintu", "bergerak", "cfg_t_lo", "cfg_t_hi",
                "cfg_t_set", "cfg_batas_waspada", "cfg_k", "cfg_ek"):
        getattr(dut, sig).value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)


@cocotb.test()
async def trip_dan_skenario(dut):
    await reset(dut)
    total = 0
    cakupan = Counter()
    for nama, ts, amb, door, mov, prod in data_uji():
        cfg = fx.konfigurasi(prod["t_lo"], prod["t_hi"], prod["t_set"], prod["c"], prod["mass_kg"])
        for k in ("t_lo", "t_hi", "t_set", "batas_waspada"):
            getattr(dut, f"cfg_{k}").value = cfg[k] & 0xFFFF
        dut.cfg_k.value = cfg["k"]
        dut.cfg_ek.value = cfg["ek"]
        dut.trip_reset.value = 1
        await FallingEdge(dut.clk)
        dut.trip_reset.value = 0
        g = fx.MesinFisika(cfg)
        for t in range(len(ts)):
            a, b = fx.q(ts[t]), fx.q(amb[t])
            o = g.langkah(a, b, bool(door[t]), bool(mov[t]))
            dut.ts_raw.value = a & 0xFFFF
            dut.t_amb.value = b & 0xFFFF
            dut.pintu.value = int(door[t])
            dut.bergerak.value = int(mov[t])
            dut.sampel.value = 1
            await FallingEdge(dut.clk)
            dut.sampel.value = 0
            for _ in range(200):
                if dut.done.value:
                    break
                await FallingEdge(dut.clk)
            else:
                raise AssertionError(f"{nama} menit {t}: done tidak muncul")
            rtl = {"status": int(dut.status.value), "alasan": int(dut.alasan.value),
                   "ttb": int(dut.ttb.value) if dut.ttb_valid.value else None, "sensor": int(dut.sensor.value),
                   "tc": s(dut.tc.value, 40), "ts10": s(dut.ts10.value, 40), "seri": bool(dut.seri.value)}
            gold = {k: o[k] for k in rtl}
            assert rtl == gold, f"{nama} menit {t}: RTL {rtl} != golden {gold}"
            cakupan[f"status{rtl['status']}/alasan{rtl['alasan']}"] += 1
            cakupan[f"sensor{rtl['sensor']}"] += 1
            cakupan["ttb_tampil"] += rtl["ttb"] is not None
            cakupan["seri"] += rtl["seri"]
            total += 1
        dut._log.info(f"{nama}: {len(ts)} menit identik")
    dut._log.info(f"total {total} menit identik dengan golden; cakupan {dict(sorted(cakupan.items()))}")


def test_physics():
    from runner import jalankan

    jalankan("physics", ["physics.sv"], "test_physics")
