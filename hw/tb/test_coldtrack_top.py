"""coldtrack_top lewat AXI4-Lite, seperti driver ARM KV260: setiap menit hasil fisika, diagnosis, rantai segel,
dan HMAC paket hasil harus identik dengan model golden (fisika, pohon, segel, regmap).
"""

import os
import sys
from pathlib import Path

import cocotb
import pandas as pd
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge, RisingEdge

HW = Path(__file__).resolve().parent.parent
ROOT = HW.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
from hw.golden import physics as fx
from hw.golden import trees as ph
from hw.golden import regmap as rm
from hw.golden import seal as sg

B9 = "b9_xgb_chip_v5_context_synthetic_duty"
MENIT = int(os.environ.get("MENIT_TOP", "140"))
KUNCI = bytes(range(0x40, 0x60))


class Axil:
    """Master AXI4-Lite: handshake dinilai dari nilai sinyal tepat sebelum tepi naik (RisingEdge)."""

    def __init__(self, dut):
        self.d = dut

    async def tulis(self, addr, data):
        d = self.d
        d.s_axil_awaddr.value = addr
        d.s_axil_wdata.value = data & 0xFFFFFFFF
        d.s_axil_wstrb.value = 0xF
        d.s_axil_awvalid.value = 1
        d.s_axil_wvalid.value = 1
        d.s_axil_bready.value = 1
        aw = w = False
        for _ in range(50):
            await RisingEdge(d.clk)
            if not aw and d.s_axil_awready.value:
                aw = True
                d.s_axil_awvalid.value = 0
            if not w and d.s_axil_wready.value:
                w = True
                d.s_axil_wvalid.value = 0
            if aw and w:
                break
        for _ in range(50):
            await RisingEdge(d.clk)
            if d.s_axil_bvalid.value:
                d.s_axil_bready.value = 0
                return
        raise AssertionError(f"tulis {addr:#x} tidak dijawab")

    async def baca(self, addr):
        d = self.d
        d.s_axil_araddr.value = addr
        d.s_axil_arvalid.value = 1
        d.s_axil_rready.value = 1
        for _ in range(50):
            await RisingEdge(d.clk)
            if d.s_axil_arready.value:
                d.s_axil_arvalid.value = 0
            if d.s_axil_rvalid.value:
                v = int(d.s_axil_rdata.value)
                d.s_axil_arvalid.value = 0
                d.s_axil_rready.value = 0
                return v
        raise AssertionError(f"baca {addr:#x} tidak dijawab")


def s(v, bits):
    return v - (1 << bits) if v >> (bits - 1) else v


def trip(mode_pilih):
    from app.inference import cargo_params

    from eval.common import CARGO_TO_PROFILE
    from hw.golden.check_trees import duty_trip

    df = pd.read_parquet(ROOT / "data/processed/v4_seed1000_700trips.parquet")
    val = df[df.split == "val"]
    mode = val.groupby("trip_id")["failure_mode"].agg(lambda x: ([m for m in x.unique() if m != "A0"] + ["A0"])[0])
    tid = int(mode[mode == mode_pilih].index[0])
    g = val[val.trip_id == tid].sort_values("minute").reset_index(drop=True)
    prod = cargo_params(CARGO_TO_PROFILE[g.cargo_type.iloc[0]], None)
    return tid, g, ph.ffill_temp(ph.kuantisasi_trip(g, duty_trip(g, tid))), prod


@cocotb.test()
async def ujung_ke_ujung(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    for sig in ("rst_n", "s_axil_awvalid", "s_axil_wvalid", "s_axil_bready", "s_axil_arvalid", "s_axil_rready",
                "s_axil_awaddr", "s_axil_wdata", "s_axil_wstrb", "s_axil_araddr"):
        getattr(dut, sig).value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)
    bus = Axil(dut)
    assert await bus.baca(rm.ID) == 0x43540001

    for i in range(8):
        await bus.tulis(rm.KUNCI + 4 * i, int.from_bytes(KUNCI[4 * i:4 * i + 4], "big"))
    await bus.tulis(rm.CTRL, rm.C_KUNCI_TULIS)
    await bus.tulis(rm.CTRL, rm.C_KUNCI_KUNCI)
    assert (await bus.baca(rm.STATUS)) & 8, "kunci harus terkunci"

    model = ph.muat_model(ROOT / f"bench/results/local-cpu/B10/{B9}.json", True)
    for md in ("A1", "A0"):
        tid, g, q, prod = trip(md)
        cfg = fx.konfigurasi(prod["t_lo"], prod["t_hi"], prod["t_set"], prod["c"], prod["mass_kg"])
        for k in ("t_lo", "t_hi", "t_set", "batas_waspada"):
            await bus.tulis(rm.CFG[k], cfg[k])
        await bus.tulis(rm.CFG["k_lo"], cfg["k"] & 0xFFFFFFFF)
        await bus.tulis(rm.CFG["k_hi"], cfg["k"] >> 32)
        await bus.tulis(rm.CFG["ek_lo"], cfg["ek"] & 0xFFFFFFFF)
        await bus.tulis(rm.CFG["ek_hi"], cfg["ek"] >> 32)
        await bus.tulis(rm.CTRL, rm.C_TRIP_RESET)
        gf = fx.MesinFisika(cfg)
        rekaman = []
        n_diag = n_mac = 0
        for t in range(min(MENIT, len(g))):
            ok = not q["nan"][t]
            temp = int(q["temp"][t]) if ok else 0
            nilai = {"seq": t, "ts": 1_792_900_000 + 60 * t, "temp": temp, "rh": q["rh"][t], "amb": q["amb"][t],
                     "solar": q["solar"][t], "speed": q["speed"][t], "duty": q["duty"][t], "harsh": q["harsh"][t],
                     "batt": 90, "hour": q["hour"][t],
                     "flags": rm.flags(q["door"][t], q["reefer"][t], q["duty"][t] > 0, ok)}
            for k, v in nilai.items():
                await bus.tulis(rm.SAMPEL[k], int(v))
            await bus.tulis(rm.CTRL, rm.C_SAMPEL)
            for _ in range(10000):
                st = await bus.baca(rm.STATUS)
                if st & 2:
                    break
            else:
                raise AssertionError(f"menit {t}: hasil_valid tidak muncul")

            # golden
            o = gf.langkah(temp if ok else -32768, int(q["amb"][t]), bool(q["door"][t]), int(q["speed"][t]) >= 100)
            rek = (t.to_bytes(4, "big") + nilai["ts"].to_bytes(4, "big") + (temp & 0xFFFF).to_bytes(2, "big")
                   + int(q["rh"][t]).to_bytes(2, "big") + (int(q["amb"][t]) & 0xFFFF).to_bytes(2, "big")
                   + int(q["solar"][t]).to_bytes(2, "big") + int(q["speed"][t]).to_bytes(2, "big")
                   + nilai["flags"].to_bytes(1, "big") + int(q["duty"][t]).to_bytes(2, "big")
                   + int(q["harsh"][t]).to_bytes(1, "big") + (90).to_bytes(1, "big"))
            rekaman.append(rek)

            rf = await bus.baca(rm.R_FISIKA)
            tc = s((await bus.baca(rm.R_TC_HI)) << 32 | await bus.baca(rm.R_TC_LO), 64)
            rtl = {"status": rf & 3, "alasan": (rf >> 2) & 7, "sensor": (rf >> 5) & 3,
                   "ttb": (rf >> 8) & 63 if rf >> 7 & 1 else None, "seri": bool(rf >> 16 & 1), "tc": tc}
            assert rtl == {k: o[k] for k in rtl}, f"trip {tid} menit {t}: fisika {rtl} != {o}"
            assert await bus.baca(rm.R_MENIT) == t

            rantai = b"".join([(await bus.baca(rm.R_RANTAI + 4 * i)).to_bytes(4, "big") for i in range(8)])
            assert rantai == sg.rantai(rekaman), f"menit {t}: rantai segel beda"

            diag = await bus.baca(rm.R_DIAG)
            lengkap = bool(st & 32)
            kelas, skor = 0, 0
            if t >= 59:
                if lengkap:
                    f = ph.fitur_bulat(q, t, True)
                    skor_g = ph.skor_bulat(model, f)
                    kelas = ph.kelas_bulat(model, f)
                    skor_rtl = [s(await bus.baca(rm.R_SKOR + 4 * k), 32) for k in range(7)]
                    assert skor_rtl == skor_g and diag == (8 | kelas), f"menit {t}: diagnosis beda"
                    skor = skor_g[kelas]
                    n_diag += 1
            else:
                assert diag == 0
            if (t >= 59 and lengkap or t < 59) and t % 15 == 14:
                await bus.tulis(rm.CTRL, rm.C_MAC)
                while not (await bus.baca(rm.STATUS)) & 4:
                    pass
                mac = b"".join([(await bus.baca(rm.R_MAC + 4 * i)).to_bytes(4, "big") for i in range(8)])
                paket = rm.paket_hasil(t, t, o, t >= 59 and lengkap, kelas, skor)
                assert mac == sg.mac(KUNCI, rantai, paket), f"menit {t}: HMAC beda"
                assert sg.verifikasi(KUNCI, rekaman, rantai, paket, mac)
                n_mac += 1
        dut._log.info(f"trip {tid} ({md}): {min(MENIT, len(g))} menit identik; {n_diag} diagnosis, {n_mac} HMAC dicek")


def test_coldtrack_top():
    from runner import jalankan

    folder = HW / "model" / "xgb_v5_context_duty"
    jalankan("coldtrack_top", ["sha256_core.sv", "seal.sv", "physics.sv", "floor_div.sv", "features.sv",
                               "tree_engine.sv", "coldtrack_top.sv"], "test_coldtrack_top",
             parameters={"BERKAS_SIMPUL": f'"{folder / "nodes.mem"}"', "BERKAS_POHON": f'"{folder / "trees.mem"}"',
                         "BERKAS_BASE": f'"{folder / "base.mem"}"'})
