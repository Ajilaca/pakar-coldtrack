"""Karakterisasi SPI coldtrack_spi: kecepatan SCK x fase terhadap clk chip, hitung transaksi yang salah.

SCK tidak dipakai sebagai clock; chip mencupliknya dengan clk (sinkroniser 2 FF), jadi batasnya bergantung pada
rasio SCK/clk dan posisi tepi SCK relatif terhadap clk. Tiap konfigurasi: chip direset, konfigurasi fisika ditulis
pada kecepatan aman, lalu RONDE ronde diukur pada kecepatan uji:
  trip_reset, 11 register sampel acak, sampel_go, tunggu hasil_valid, baca 8 kata rantai (cek SHA-256 golden),
  baca ID dan alamat kosong (0xDEADBEEF).
Periode yang bukan kelipatan clk membuat fase bergeser di sepanjang frame; offset menggeser titik awalnya.
Simulasi tanpa delay fisik dan metastabilitas: hasilnya batas logika, bukan batas silikon.
Wajib: nol kesalahan pada SCK <= clk/8. Hasil: hw/results/spi_sweep.json.
"""

import json
import random
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge, RisingEdge, Timer

HW = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HW.parent))
from hw.golden import physics as fx
from hw.golden import regmap as rm
from hw.golden import seal as sg
from hw.golden import spi_frame as sf

CLK_NS = 10
SETENGAH_NS = [40, 37, 35, 33, 30, 27, 25, 23, 20, 17, 15, 12.5, 10]
OFFSET_NS = [0, 2.5, 5, 7.5]
RONDE = 8
AMAN_NS = 40
KOLOM = ("seq", "ts", "temp", "rh", "amb", "solar", "speed", "flags", "duty", "harsh", "batt")
LEBAR = {"seq": 32, "ts": 32, "temp": 16, "rh": 16, "amb": 16, "solar": 16, "speed": 16, "flags": 4, "duty": 16,
         "harsh": 8, "batt": 8}


class Master:
    def __init__(self, dut):
        self.d, self.t, self.offset = dut, AMAN_NS, 0.0

    async def frame(self, mosi):
        d, t = self.d, self.t
        await RisingEdge(d.clk)
        if self.offset:
            await Timer(self.offset, unit="ns")
        d.spi_cs_n.value = 0
        await Timer(t, unit="ns")
        miso = 0
        for byte in mosi:
            for i in range(7, -1, -1):
                d.spi_mosi.value = (byte >> i) & 1
                await Timer(t, unit="ns")
                miso = miso << 1 | int(d.spi_miso.value)
                d.spi_sck.value = 1
                await Timer(t, unit="ns")
                d.spi_sck.value = 0
        await Timer(t, unit="ns")
        d.spi_cs_n.value = 1
        await Timer(max(2 * t, 4 * CLK_NS), unit="ns")
        return miso.to_bytes(len(mosi), "big")

    async def tulis(self, a, v):
        await self.frame(sf.frame_tulis(a, v))

    async def baca(self, a):
        return sf.data_baca(await self.frame(sf.frame_baca(a)))


def _rek(n):
    """Rekaman 23 byte seperti coldtrack_top (format hw/golden/seal.py)."""
    b = n["seq"].to_bytes(4, "big") + n["ts"].to_bytes(4, "big")
    for k in ("temp", "rh", "amb", "solar", "speed"):
        b += n[k].to_bytes(2, "big")
    return b + n["flags"].to_bytes(1, "big") + n["duty"].to_bytes(2, "big") + bytes([n["harsh"], n["batt"]])


async def ronde(m, rng):
    """True bila seluruh ronde benar; jumlah frame dan frame baca ID/kosong yang salah."""
    n = {k: rng.randrange(1 << LEBAR[k]) for k in KOLOM}
    await m.tulis(rm.CTRL, rm.C_TRIP_RESET)
    for k in KOLOM:
        await m.tulis(rm.SAMPEL[k], n[k])
    await m.tulis(rm.CTRL, rm.C_SAMPEL)
    frame, ok = 13, False
    for _ in range(40):
        frame += 1
        if (await m.baca(rm.STATUS)) & 2:
            ok = True
            break
    rantai = b""
    for i in range(8):
        rantai += (await m.baca(rm.R_RANTAI + 4 * i)).to_bytes(4, "big")
    frame += 8
    benar = ok and rantai == sg.rantai([_rek(n)])
    salah_id = int(await m.baca(rm.ID) != 0x43540001) + int(await m.baca(0x800) != 0xDEADBEEF)
    return benar and not salah_id, frame + 2, salah_id


async def siapkan(dut, m):
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)
    m.t, m.offset = AMAN_NS, 0.0
    cfg = fx.konfigurasi(2.0, 8.0, 5.0, 3.6, 1000.0)
    for k in ("t_lo", "t_hi", "t_set", "batas_waspada"):
        await m.tulis(rm.CFG[k], cfg[k])
    for k in ("k", "ek"):
        await m.tulis(rm.CFG[f"{k}_lo"], cfg[k] & 0xFFFFFFFF)
        await m.tulis(rm.CFG[f"{k}_hi"], cfg[k] >> 32)
    assert await m.baca(rm.ID) == 0x43540001


@cocotb.test()
async def sapuan_sck_fase(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_NS, unit="ns").start())
    for s in ("spi_sck", "spi_mosi", "qspi_io_i"):
        if hasattr(dut, s):
            getattr(dut, s).value = 0
    dut.spi_cs_n.value = 1
    m = Master(dut)
    rng = random.Random(3)
    hasil = []
    for t in SETENGAH_NS:
        for off in OFFSET_NS:
            await siapkan(dut, m)
            m.t, m.offset = t, off
            gagal = frame = salah_id = 0
            for _ in range(RONDE):
                b, f, s_id = await ronde(m, rng)
                gagal += not b
                frame += f
                salah_id += s_id
            hasil.append({"setengah_ns": t, "offset_ns": off, "rasio_clk": 2 * t / CLK_NS,
                          "sck_mhz": round(1000 / (2 * t), 2), "ronde": RONDE, "ronde_gagal": gagal,
                          "frame": frame, "baca_id_kosong_salah": salah_id})
        r = [h for h in hasil if h["setengah_ns"] == t]
        dut._log.info(f"SCK = clk/{2 * t / CLK_NS:g} ({1000 / (2 * t):.1f} MHz): ronde gagal per offset "
                      f"{[h['ronde_gagal'] for h in r]} dari {RONDE}")

    out = HW / "results" / "spi_sweep.json"
    out.write_text(json.dumps({"clk_mhz": 1000 / CLK_NS, "ronde_per_konfigurasi": RONDE,
                               "isi_ronde": "trip_reset, 11 sampel, sampel_go, tunggu hasil_valid, 8 kata rantai, "
                                            "ID, alamat kosong", "hasil": hasil}, indent=1) + "\n")
    aman = [h for h in hasil if h["rasio_clk"] >= 8]
    assert all(h["ronde_gagal"] == 0 for h in aman), "ada kesalahan pada SCK <= clk/8"
    batas = None
    for r in sorted({h["rasio_clk"] for h in hasil}, reverse=True):     # dari paling lambat
        if any(h["ronde_gagal"] for h in hasil if h["rasio_clk"] == r):
            break
        batas = r
    dut._log.info(f"tanpa kesalahan di semua offset sampai SCK = clk/{batas:g}")


def test_spi_sweep():
    from runner import jalankan

    jalankan("coldtrack_spi", ["sha256_core.sv", "seal.sv", "physics.sv", "floor_div.sv", "features.sv",
                               "tree_engine.sv", "sha256_stream.sv", "qspi_reader.sv", "tree_stream.sv",
                               "model_flash.sv", "coldtrack_top.sv", "spi_axil_bridge.sv", "coldtrack_spi.sv"],
             "test_spi_sweep", parameters={"MODEL_FLASH": 0})
