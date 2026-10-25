"""floor_div: floor(n/d) bertanda dibandingkan dengan // Python, termasuk kasus tepi."""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge

NW, DW = 72, 34


async def bagi(dut, n, d):
    dut.n.value = n & ((1 << NW) - 1)
    dut.d.value = d
    dut.start.value = 1
    await FallingEdge(dut.clk)
    dut.start.value = 0
    for _ in range(NW + 5):
        await FallingEdge(dut.clk)
        if dut.done.value:
            v = int(dut.q.value)
            return v - (1 << NW) if v >> (NW - 1) else v
    raise AssertionError("done tidak muncul")


@cocotb.test()
async def acak_dan_tepi(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value = 0
    dut.start.value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)
    rnd = random.Random(3)
    kasus = [(0, 1), (7, 2), (-7, 2), (-8, 2), (-1, 3), (1, 3), ((1 << 70), 3), (-(1 << 70), 7), (5, (1 << DW) - 1)]
    kasus += [(rnd.randrange(-(1 << 68), 1 << 68), rnd.randrange(1, 1 << 33)) for _ in range(300)]
    kasus += [(rnd.randrange(-(1 << 55), 1 << 55), rnd.randrange(1, 14401)) for _ in range(300)]
    for n, d in kasus:
        assert (await bagi(dut, n, d)) == n // d, (n, d)


def test_floor_div():
    from runner import jalankan

    jalankan("floor_div", ["floor_div.sv"], "test_floor_div")
