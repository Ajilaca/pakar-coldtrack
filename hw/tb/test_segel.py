"""segel: rantai hash dan HMAC dibandingkan dengan hw/golden/segel.py (hashlib/hmac), plus kunci terkunci
dan deteksi manipulasi di sisi verifikasi."""

import random
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from golden import segel as g


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    for s in ("rst_n", "kunci_tulis", "kunci_data", "kunci_kunci", "rantai_reset", "segel_start",
              "rekaman", "mac_start", "hasil"):
        getattr(dut, s).value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)


async def pulsa(dut, nama):
    getattr(dut, nama).value = 1
    await FallingEdge(dut.clk)
    getattr(dut, nama).value = 0


async def tunggu_done(dut, batas=400):
    for _ in range(batas):
        await FallingEdge(dut.clk)
        if dut.done.value:
            return
    raise AssertionError("done tidak muncul")


async def tulis_kunci(dut, kunci: bytes):
    dut.kunci_data.value = int.from_bytes(kunci, "big")
    await pulsa(dut, "kunci_tulis")


async def segel_rtl(dut, rek: bytes):
    dut.rekaman.value = int.from_bytes(rek, "big")
    await pulsa(dut, "segel_start")
    await tunggu_done(dut)
    return int(dut.rantai.value).to_bytes(32, "big")


async def mac_rtl(dut, hasil: bytes):
    dut.hasil.value = int.from_bytes(hasil, "big")
    await pulsa(dut, "mac_start")
    await tunggu_done(dut)
    return int(dut.mac.value).to_bytes(32, "big")


def rekaman_acak(rnd, seq):
    return g.rekaman(seq, 1_792_900_000 + 60 * seq, rnd.uniform(-25, 10), rnd.uniform(40, 95),
                     rnd.uniform(24, 34), rnd.uniform(0, 700), rnd.uniform(0, 90), rnd.random() < .1,
                     rnd.random() < .95, rnd.random() < .5, True, rnd.random(), rnd.randrange(3),
                     rnd.randrange(2400, 3100))


@cocotb.test()
async def rantai_dan_mac(dut):
    await reset(dut)
    rnd = random.Random(7)
    kunci = rnd.randbytes(32)
    await tulis_kunci(dut, kunci)
    await pulsa(dut, "kunci_kunci")
    log = []
    h = bytes(32)
    for seq in range(30):
        rek = rekaman_acak(rnd, seq)
        log.append(rek)
        h = g.segel(h, rek)
        assert (await segel_rtl(dut, rek)) == h, f"rantai seq {seq}"
        if seq % 10 == 9:
            hasil = rnd.randbytes(16)
            m = await mac_rtl(dut, hasil)
            assert m == g.mac(kunci, h, hasil), f"mac seq {seq}"
            assert g.verifikasi(kunci, log, h, hasil, m)
            rusak = list(log)
            rusak[3] = rusak[3][:9] + bytes([rusak[3][9] ^ 1]) + rusak[3][10:]   # ubah 1 bit suhu
            assert not g.verifikasi(kunci, rusak, h, hasil, m)
            assert not g.verifikasi(kunci, log[:-1], h, hasil, m)                 # buang ekor
            assert not g.verifikasi(kunci, log[:2] + log[3:], h, hasil, m)        # hapus di tengah


@cocotb.test()
async def kunci_terkunci(dut):
    await reset(dut)
    k1, k2 = bytes(range(32)), bytes(range(100, 132))
    await tulis_kunci(dut, k1)
    await pulsa(dut, "kunci_kunci")
    await tulis_kunci(dut, k2)                       # harus diabaikan
    assert dut.kunci_terkunci.value == 1
    hasil = bytes(16)
    assert (await mac_rtl(dut, hasil)) == g.mac(k1, bytes(32), hasil)


@cocotb.test()
async def reset_rantai(dut):
    await reset(dut)
    rek = g.rekaman(1, 0, 4.0, 70, 30, 0, 50, 0, 1, 1, 1, .4, 0, 2900)
    await segel_rtl(dut, rek)
    await pulsa(dut, "rantai_reset")
    assert int(dut.rantai.value) == 0
    assert (await segel_rtl(dut, rek)) == g.segel(bytes(32), rek)


def test_segel():
    from runner import jalankan

    jalankan("segel", ["sha256_core.sv", "segel.sv"], "test_segel")
