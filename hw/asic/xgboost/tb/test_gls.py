"""Gate-level simulation (GLS) netlist final layout coldtrack_asic: skenario ujung-ke-ujung yang sama dengan RTL.

Jalankan dari folder ini:  ../../../../.venv/bin/python -m pytest -q -s test_gls.py
DUT = layout/runs/<GLS_RUN>/final/nl/coldtrack_asic.nl.v (bawaan RUN_AK) + model Verilog sel sky130_fd_sc_hd dari PDK
(FUNCTIONAL, tanpa delay) + model perilaku RAM256 (sim/RAM256.v). Modul tes cocotb = hw/tb/test_coldtrack_top.py mode
CT_SPI, sama dengan test_asic.py::test_coldtrack_asic, jadi kriteria lulusnya identik: fisika, rantai segel, skor dan
kelas diagnosis, HMAC, serta penolakan image flash rusak sama bit per bit dengan golden.

Kunci HMAC model sudah tertanam di gerbang netlist, jadi image flash ditandai dengan kunci layout (~/.coldtrack/
kunci_model.hex, atau $CT_KUNCI_MODEL), bukan kunci uji test_asic.py.

Sebelum dikompilasi, sel fisik tanpa fungsi logika (decap, fill, tap, dioda antena) dibuang dari netlist; sel lain,
termasuk buffer dan sel hold hasil ECO, tetap utuh. Verilator dibangun tanpa --public-flat-rw (hanya port testbench
yang dibuka ke cocotb) supaya netlist ratusan ribu sel tetap cepat.

test_gls_sdf: netlist yang sama dengan delay pasca-layout (final/sdf/<GLS_CORNER>, IOPATH sel + INTERCONNECT) di Icarus
(model sel timing sky130, bukan FUNCTIONAL), clock GLS_CLK_NS = 100 ns (CLOCK_PERIOD layout) dan SCK = clk/8. Skenario
pendek (sdf_singkat, MENIT_SDF menit): ID, frame terputus diabaikan, kunci sesi, lalu per menit fisika, rantai segel,
dan HMAC paket identik dengan golden. RAM256 di sini netlist gerbang makro (delay di dalam makro ikut dianotasi). Icarus
tidak menjalankan TIMINGCHECK SDF (setup/hold), jadi pemeriksaan itu tetap dari STA signoff.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.simtime import get_sim_time
from cocotb.triggers import ClockCycles, FallingEdge, Timer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner_asic import HW, OSS  # noqa: E402

XGB = HW / "asic" / "xgboost"
RUN = os.environ.get("GLS_RUN", "RUN_AK")
CLK_NS = int(os.environ.get("GLS_CLK_NS", "100"))
MENIT_SDF = int(os.environ.get("MENIT_SDF", "3"))
FISIK = re.compile(r"^\s*sky130_fd_sc_hd__(decap|fill|tapvpwrvgnd|diode)_\w+\s+[^;]*;\n", re.M)
TANPA_PORT = re.compile(r"^\s*sky130_fd_sc_hd__(decap|fill|tapvpwrvgnd)_\w+\s+[^;]*;\n", re.M)


def _pdk_verilog():
    pdk = Path(os.environ.get("PDK_ROOT", Path.home() / ".ciel")) / "ciel" / "sky130" / "versions"
    return sorted(pdk.glob("*/sky130A/libs.ref/sky130_fd_sc_hd/verilog"))[0]


def _aman(nama):
    """Nama escaped (mis. u_chip.u_ct.u_ram0, A0BUF[5].__cell__) -> identifier biasa, sama untuk netlist dan SDF."""
    return nama.replace(".", "__").replace("[", "_").replace("]", "_")


def _saring(src, dst, pola, ganti_escape=False):
    """src tanpa sel yang cocok dengan pola -> dst (dibuat ulang bila src lebih baru).

    ganti_escape: identifier escaped diganti dengan _aman(); parser SDF Icarus tidak mengenali titik ber-escape di
    path hierarki (u_chip\\.u_ct...) sehingga anotasinya gagal.
    """
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        dst.parent.mkdir(parents=True, exist_ok=True)
        teks, n = pola.subn("", src.read_text())
        if ganti_escape:
            teks = re.sub(r"\\(\S+)", lambda m: _aman(m.group(1)), teks)
        dst.write_text(teks)
        print(f"{src.name}: {n} sel fisik dibuang -> {dst}")
    return dst


INTERCONNECT = re.compile(r"\(INTERCONNECT (\S+) \S+ \(([\d.]+):[\d.]+:[\d.]+\)(?: \(([\d.]+):[\d.]+:[\d.]+\))?\)")
IOPATH = re.compile(r"(\(IOPATH (?:\S+|\([^()]*\)) (\S+) )((?:\([^()]*\)\s*)+)\)")
TRIPEL = re.compile(r"\(([\d.]+):([\d.]+):([\d.]+)\)")


def _lipat_interconnect(teks):
    """INTERCONNECT dibuang, delay kabel terbesar dari tiap pin keluaran ditambahkan ke IOPATH sel penggeraknya.

    Icarus mencari tiap nama instance secara linear di scope top (~230 ribu instance), jadi 555 ribu INTERCONNECT
    menambah ~1 jam anotasi per corner. Delay kabel kecil dibanding delay sel (RUN_AK tt: median 0,001 ns,
    p99 0,029 ns, maks 0,326 ns), jadi dilipat ke penggerak: tiap beban menerima delay kabel terpanjang pada net itu.
    """
    tambah = {}
    for src, r, f in INTERCONNECT.findall(teks):
        lama = tambah.get(src, (0.0, 0.0))
        tambah[src] = (max(lama[0], float(r)), max(lama[1], float(f or r)))
    teks = INTERCONNECT.sub("", teks)
    # blok CELL top-level hanya berisi INTERCONNECT; (ABSOLUTE ) kosong ditolak parser Icarus (anotasi berhenti)
    teks = re.sub(r' \(CELL\n  \(CELLTYPE "coldtrack_asic"\)\n.*?\n \)\n', "", teks, count=1, flags=re.S)
    keluar, inst = [], None
    for baris in teks.splitlines(keepends=True):
        if baris.lstrip().startswith("(INSTANCE"):
            inst = baris.split("(INSTANCE", 1)[1].strip().rstrip(")").strip()
        elif "(IOPATH" in baris and inst:
            baris = IOPATH.sub(lambda m: _tambah_delay(m, tambah.get(f"{inst}.{m.group(2)}", (0.0, 0.0))), baris)
        keluar.append(baris)
    return "".join(keluar)


def _tambah_delay(m, d):
    """IOPATH (rise) (fall): rise + d[0], fall + d[1]; satu nilai saja -> + maks; nilai kosong () dibiarkan."""
    nilai = re.findall(r"\([^()]*\)", m.group(3))
    per = list(d) if len(nilai) >= 2 else [max(d)]
    baru = []
    for k, v in enumerate(nilai):
        t = TRIPEL.fullmatch(v)
        dk = per[k] if k < len(per) else max(d)
        baru.append("({:.3f}:{:.3f}:{:.3f})".format(*(float(x) + dk for x in t.groups())) if t else v)
    return m.group(1) + " ".join(baru) + ")"


def sdf_gls(corner):
    """SDF final untuk Icarus -> hw/build/gls/<RUN>_<corner>.sdf: nama escaped diganti seperti netlist_gls(sdf=True),
    dan INTERCONNECT dilipat ke IOPATH (_lipat_interconnect) kecuali GLS_SDF_INTERCONNECT=1."""
    penuh = os.environ.get("GLS_SDF_INTERCONNECT") == "1"
    src = XGB / "layout" / "runs" / RUN / "final" / "sdf" / corner / f"coldtrack_asic__{corner}.sdf"
    dst = HW / "build" / "gls" / f"{RUN}_{corner}{'' if penuh else '_lipat'}.sdf"
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        dst.parent.mkdir(parents=True, exist_ok=True)
        teks = src.read_text().replace("\\.", "__").replace("\\[", "_").replace("\\]", "_")
        # header (VOLTAGE 1.800::1.800) tanpa nilai typ -> "Chosen value not defined" di Icarus
        teks = re.sub(r"\((VOLTAGE|PROCESS|TEMPERATURE) (\"?)(-?[\d.]+)::(-?[\d.]+)\2\)", r"(\1 \2\3:\3:\4\2)", teks,
                      count=3)
        dst.write_text(teks if penuh else _lipat_interconnect(teks))
    return dst


def netlist_gls(sdf=False):
    """Sumber DUT di hw/build/gls/.

    Fungsional: netlist final tanpa decap/fill/tap/dioda + model perilaku RAM256. SDF: SDF final dibuat STA dengan
    netlist gerbang makro (STA_MACRO_PRIORITIZE_NL), jadi memuat delay sel dan kabel di dalam RAM256; netlist gerbang
    RAM256 (ram256/nl) ikut dipakai dan dioda dipertahankan karena kabel ke pin dioda juga dianotasi.
    """
    top = XGB / "layout" / "runs" / RUN / "final" / "nl" / "coldtrack_asic.nl.v"
    gls = HW / "build" / "gls"
    if not sdf:
        return [XGB / "sim" / "RAM256.v", _saring(top, gls / f"{RUN}.nl.v", FISIK)]
    return [_saring(XGB / "ram256" / "nl" / "RAM256.nl.v", gls / "RAM256.sdf.nl.v", TANPA_PORT, True),
            _saring(top, gls / f"{RUN}.sdf.nl.v", TANPA_PORT, True)]


def _flash_model_icarus():
    """hw/tb/spi_flash_model.sv tanpa variabel automatic di blok always (belum didukung Icarus); perilaku sama."""
    src = HW / "tb" / "spi_flash_model.sv"
    dst = HW / "build" / "gls" / "spi_flash_model_icarus.sv"
    teks, n = re.subn(r"automatic (int|logic \[7:0\]) (\w) = ", r"\2 = ", src.read_text())
    assert n == 3, "struktur spi_flash_model.sv berubah, sesuaikan _flash_model_icarus"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(teks.replace("    logic [31:0] naik;", "    int j, a;\n    logic [7:0] v;\n    logic [31:0] naik;", 1))
    return dst


def _flash(nama="xgb_v5_context_duty"):
    """Image bertag kunci layout sebagai hex untuk spi_flash_model."""
    sys.path.insert(0, str(HW.parent))
    from hw.asic.xgboost.golden import flash_tag as ft
    from hw.golden import flash_image as fi

    kunci = ft.baca_kunci(Path(os.environ.get("CT_KUNCI_MODEL", ft.KUNCI_BAWAAN)))
    berkas = HW / "build" / "flash" / f"gls_{nama}.hex"
    fi.tulis_hex(ft.image_bertag(HW / "model" / nama, kunci), berkas)
    return berkas


def _bangun_verilator(build, toplevel, sources, parameters):
    import cocotb_tools.config as cc

    exe = build / toplevel
    if exe.exists() and all(Path(s).stat().st_mtime < exe.stat().st_mtime for s in sources):
        return
    vlt = build / "publik.vlt"
    build.mkdir(parents=True, exist_ok=True)
    vlt.write_text(f'`verilator_config\npublic_flat_rw -module "{toplevel}" -var "*"\n')
    env = dict(os.environ, PATH=f"{OSS / 'bin'}{os.pathsep}{os.environ['PATH']}")
    cmd = (["verilator", "-cc", "--exe", "-Mdir", str(build), "--top-module", toplevel, "--vpi", "--prefix", "Vtop",
            "-o", toplevel, "-LDFLAGS",
            f"-Wl,-rpath,{cc.libs_dir} -L{cc.libs_dir} -lcocotbvpi_verilator",
            "-Wno-fatal", "-Wno-lint", "-Wno-style", "-Wno-BLKANDNBLK", "--timing",
            "--x-initial", "unique", "--x-assign", "unique", "--threads", os.environ.get("GLS_THREADS", "8"),
            "--timescale", "1ns/1ps", "-DFUNCTIONAL", "-DUNIT_DELAY=", "-DGLS"]
           + [f"-G{k}={v}" for k, v in parameters.items()]
           + [str(vlt), str(cc.share_dir / "lib" / "verilator" / "verilator.cpp")] + [str(s) for s in sources])
    subprocess.run(cmd, check=True, env=env)
    subprocess.run(["make", "-j", os.environ.get("GLS_JOBS", "8"), "-C", str(build), "-f", "Vtop.mk", "VM_TRACE=0"],
                   check=True, env=env)


def test_gls_fungsional():
    from cocotb_tools.runner import get_runner

    lib = _pdk_verilog()
    toplevel = "coldtrack_asic_tb"
    build = HW / "build" / f"gls_{RUN}_verilator"
    sources = [lib / "primitives.v", lib / "sky130_fd_sc_hd.v", *netlist_gls(),
               HW / "tb" / "spi_flash_model.sv", XGB / "tb" / "coldtrack_asic_tb.sv"]
    _bangun_verilator(build, toplevel, sources, {"BERKAS_A": f'"{_flash()}"'})
    runner = get_runner("verilator")
    runner.test(hdl_toplevel=toplevel, hdl_toplevel_lang="verilog", test_module="test_coldtrack_top", build_dir=build,
                test_dir=HW / "tb", plusargs=["+verilator+rand+reset+2", "+verilator+seed+1"],
                extra_env={"CT_SPI": "1", "BATAS_DONE_FISIKA": "3000", "BATAS_DONE_FITUR": "6000"})


def test_gls_sdf():
    from cocotb_tools.runner import get_runner

    corner = os.environ.get("GLS_CORNER", "nom_tt_025C_1v80")
    sdf = sdf_gls(corner)
    lib = _pdk_verilog()
    toplevel = "coldtrack_asic_tb"
    build = HW / "build" / f"gls_{RUN}_{corner}_icarus"
    if str(OSS / "bin") not in os.environ["PATH"]:
        os.environ["PATH"] = f"{OSS / 'bin'}{os.pathsep}{os.environ['PATH']}"
    runner = get_runner("icarus")
    runner.build(sources=[lib / "primitives.v", lib / "sky130_fd_sc_hd.v", *netlist_gls(sdf=True),
                          _flash_model_icarus(), XGB / "tb" / "coldtrack_asic_tb.sv"],
                 hdl_toplevel=toplevel, build_dir=build, build_args=["-gspecify", "-ginterconnect"],
                 defines={"UNIT_DELAY": "", "GLS": 1, "GLS_SDF": f'"{sdf}"'},
                 parameters={"BERKAS_A": f'"{_flash()}"'}, timescale=("1ns", "1ps"), always=True)
    runner.test(hdl_toplevel=toplevel, test_module="test_gls", testcase="sdf_singkat", build_dir=build,
                test_dir=Path(__file__).resolve().parent, extra_env={"CT_SPI": "1"})


@cocotb.test(skip=os.environ.get("CT_SPI") != "1")
async def sdf_singkat(dut):
    """Skenario pendek lewat SPI untuk GLS bertiming; pemeriksaan sama dengan test_coldtrack_top.ujung_ke_ujung."""
    import test_coldtrack_top as tc
    from hw.golden import physics as fx
    from hw.golden import regmap as rm
    from hw.golden import seal as sg
    from hw.golden import spi_frame as sf

    tc.SETENGAH_SPI_NS = 4 * CLK_NS
    cocotb.start_soon(Clock(dut.clk, CLK_NS, unit="ns").start())
    for sig in ("rst_n", "spi_sck", "spi_mosi", "tulis"):
        getattr(dut, sig).value = 0
    dut.spi_cs_n.value = 1
    await ClockCycles(dut.clk, 3)
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 3)
    bus = tc.Spi(dut)
    assert await bus.baca(rm.ID) == 0x43540001
    await bus.frame(sf.frame_tulis(rm.CTRL, rm.C_SAMPEL), potong_bit=47)
    await Timer(100 * CLK_NS, unit="ns")
    st = await bus.baca(rm.STATUS)
    assert st & 3 == 0 and st >> 8 & 1, f"STATUS {st:#x}: frame terputus harus diabaikan, bit mode flash 1"

    for i in range(8):
        await bus.tulis(rm.KUNCI + 4 * i, int.from_bytes(tc.KUNCI[4 * i:4 * i + 4], "big"))
    await bus.tulis(rm.CTRL, rm.C_KUNCI_TULIS)
    await bus.tulis(rm.CTRL, rm.C_KUNCI_KUNCI)
    assert (await bus.baca(rm.STATUS)) & 8, "kunci harus terkunci"

    tid, g, q, prod = tc.trip("A1")
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
    for t in range(MENIT_SDF):
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
            if (st := await bus.baca(rm.STATUS)) & 2:
                break
            await Timer(500 * CLK_NS, unit="ns")
        else:
            raise AssertionError(f"menit {t}: hasil_valid tidak muncul")

        o = gf.langkah(temp if ok else -32768, int(q["amb"][t]), bool(q["door"][t]), int(q["speed"][t]) >= 100)
        rekaman.append(t.to_bytes(4, "big") + nilai["ts"].to_bytes(4, "big") + (temp & 0xFFFF).to_bytes(2, "big")
                       + int(q["rh"][t]).to_bytes(2, "big") + (int(q["amb"][t]) & 0xFFFF).to_bytes(2, "big")
                       + int(q["solar"][t]).to_bytes(2, "big") + int(q["speed"][t]).to_bytes(2, "big")
                       + nilai["flags"].to_bytes(1, "big") + int(q["duty"][t]).to_bytes(2, "big")
                       + int(q["harsh"][t]).to_bytes(1, "big") + (90).to_bytes(1, "big"))
        rf = await bus.baca(rm.R_FISIKA)
        tcap = tc.s((await bus.baca(rm.R_TC_HI)) << 32 | await bus.baca(rm.R_TC_LO), 64)
        rtl = {"status": rf & 3, "alasan": (rf >> 2) & 7, "sensor": (rf >> 5) & 3,
               "ttb": (rf >> 8) & 63 if rf >> 7 & 1 else None, "seri": bool(rf >> 16 & 1), "tc": tcap}
        assert rtl == {k: o[k] for k in rtl}, f"menit {t}: fisika {rtl} != {o}"
        assert await bus.baca(rm.R_MENIT) == t
        rantai = b"".join([(await bus.baca(rm.R_RANTAI + 4 * i)).to_bytes(4, "big") for i in range(8)])
        assert rantai == sg.rantai(rekaman), f"menit {t}: rantai segel beda"
        assert await bus.baca(rm.R_DIAG) == 0

        await bus.tulis(rm.CTRL, rm.C_MAC)
        while not (await bus.baca(rm.STATUS)) & 4:
            pass
        mac = b"".join([(await bus.baca(rm.R_MAC + 4 * i)).to_bytes(4, "big") for i in range(8)])
        assert mac == sg.mac(tc.KUNCI, rantai, rm.paket_hasil(t, t, o, False, 0, 0)), f"menit {t}: HMAC beda"
        dut._log.info(f"menit {t}: fisika, rantai segel, HMAC identik (t = {get_sim_time('us'):.0f} us)")
    dut._log.info(f"trip {tid} (A1): {MENIT_SDF} menit identik dengan golden pada netlist + SDF")
