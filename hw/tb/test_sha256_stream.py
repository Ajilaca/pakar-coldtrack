"""sha256_stream: digest harus sama dengan hashlib untuk panjang di sekitar batas padding dan panjang acak,
dengan jeda acak antar byte (seperti pembaca flash yang berhenti saat siap=0)."""

import hashlib
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge

PANJANG = [0, 1, 3, 54, 55, 56, 57, 63, 64, 65, 119, 120, 127, 128, 129, 200, 1000]


async def hash_rtl(dut, pesan, rng):
    dut.mulai.value = 1
    await FallingEdge(dut.clk)
    dut.mulai.value = 0
    for b in pesan:
        while not dut.siap.value:
            await FallingEdge(dut.clk)
        dut.byte_valid.value = 1
        dut.byte_data.value = b
        await FallingEdge(dut.clk)
        dut.byte_valid.value = 0
        for _ in range(rng.randrange(4)):
            await FallingEdge(dut.clk)
    dut.akhiri.value = 1
    await FallingEdge(dut.clk)
    dut.akhiri.value = 0
    for _ in range(2000):
        await FallingEdge(dut.clk)
        if dut.done.value:
            return int(dut.digest.value).to_bytes(32, "big")
    raise AssertionError(f"done tidak muncul untuk {len(pesan)} byte")


@cocotb.test()
async def sama_dengan_hashlib(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    for s in ("rst_n", "mulai", "byte_valid", "byte_data", "akhiri"):
        getattr(dut, s).value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)
    rng = random.Random(7)
    for n in PANJANG + [rng.randrange(2000) for _ in range(8)]:
        pesan = bytes(rng.randrange(256) for _ in range(n))
        assert await hash_rtl(dut, pesan, rng) == hashlib.sha256(pesan).digest(), f"{n} byte"
    dut._log.info(f"{len(PANJANG) + 8} pesan identik dengan hashlib")


def test_sha256_stream():
    from runner import jalankan

    jalankan("sha256_stream", ["sha256_core.sv", "sha256_stream.sv"], "test_sha256_stream")
