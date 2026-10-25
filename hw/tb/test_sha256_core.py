"""sha256_core: vektor NIST FIPS 180-4 + pesan acak multi-blok, dibandingkan dengan hashlib."""

import hashlib
import random
import struct

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge, RisingEdge


def pad(msg: bytes) -> bytes:
    n = len(msg) * 8
    msg += b"\x80" + b"\x00" * ((55 - len(msg)) % 64)
    return msg + struct.pack(">Q", n)


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value = 0
    dut.start.value = 0
    dut.use_iv.value = 0
    dut.h_in.value = 0
    dut.block.value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def hash_rtl(dut, msg: bytes) -> bytes:
    """Masukan diberikan dan keluaran dibaca di tepi turun (nilai register sudah stabil)."""
    data = pad(msg)
    h = 0
    for i in range(0, len(data), 64):
        await FallingEdge(dut.clk)
        dut.block.value = int.from_bytes(data[i:i + 64], "big")
        dut.use_iv.value = int(i == 0)
        dut.h_in.value = h
        dut.start.value = 1
        await FallingEdge(dut.clk)
        dut.start.value = 0
        siklus = 0          # dihitung dari tepi naik yang mengambil start
        while True:
            if dut.done.value:
                break
            await FallingEdge(dut.clk)
            siklus += 1
            if dut.done.value:
                break
            assert siklus < 100, "done tidak muncul"
        assert siklus == 65, f"latensi {siklus} siklus, harapan 65"
        h = int(dut.h_out.value)
    return h.to_bytes(32, "big")


@cocotb.test()
async def nist_vektor(dut):
    await reset(dut)
    for msg in (b"abc", b"", b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"):
        assert (await hash_rtl(dut, msg)) == hashlib.sha256(msg).digest(), msg


@cocotb.test()
async def acak_multi_blok(dut):
    await reset(dut)
    rnd = random.Random(2026)
    for n in [0, 1, 55, 56, 63, 64, 65, 119, 120, 200, 1000] + [rnd.randrange(0, 300) for _ in range(20)]:
        msg = rnd.randbytes(n)
        assert (await hash_rtl(dut, msg)) == hashlib.sha256(msg).digest(), f"panjang {n}"


def test_sha256_core():
    from runner import jalankan

    jalankan("sha256_core", ["sha256_core.sv"], "test_sha256_core")
