"""Antarmuka chip ColdTrack untuk driver ARM: satu sampel per menit masuk, hasil + segel keluar.

Tiga implementasi dengan antarmuka sama (`mulai_trip`, `proses`):
  ChipAxi     KV260 sungguhan: register AXI4-Lite coldtrack_axil di 0xA000_0000 lewat /dev/mem (butuh root).
              Urutan akses sama dengan hw/tb/test_coldtrack_top.py. Belum diuji di board.
  ChipSpi     Chip ASIC (hw/rtl/coldtrack_spi.sv) lewat SPI dari Linux (`spidev`), register map sama.
              Belum ada chipnya; frame diuji di testbench cocotb.
  ChipGolden  Model golden Python (hw/golden/) yang identik bit per bit dengan RTL di testbench cocotb;
              dipakai untuk demo tanpa board.

Satuan sampel mengikuti rekaman segel (hw/golden/seal.py): suhu, kelembapan, kecepatan 0,01; radiasi 1/16 W/m2;
siklus kerja 1/10000. `proses` mengembalikan rekaman 23 byte, rantai, paket hasil 16 byte, MAC, dan 7 skor kelas.
"""

import mmap
import os
import struct
import time
from dataclasses import dataclass

import numpy as np

from hw.golden import physics as fx
from hw.golden import regmap as rm
from hw.golden import seal as sg
from hw.golden import spi_frame as sf
from hw.golden import trees as ph

NOL = bytes(32)
BASIS_AXI = 0xA000_0000
BATERAI_MV = 2900


@dataclass
class Sampel:
    seq: int
    ts: int                 # detik UNIX
    temp: int | None        # 0,01 C; None = bacaan suhu gagal
    rh: int
    amb: int
    solar: int
    speed: int
    door: bool
    reefer: bool
    duty: int
    harsh: int
    hour: int
    battery_mv: int = BATERAI_MV


@dataclass
class HasilMenit:
    rek: bytes
    rantai: bytes
    paket: bytes
    mac: bytes
    skor: list[int]
    status: int
    diag_valid: bool
    kelas: int


def rekaman(s: Sampel) -> bytes:
    ok = s.temp is not None
    flags = rm.flags(s.door, s.reefer, s.duty > 0, ok)
    baterai = min(255, max(0, round((s.battery_mv - 2000) / 10)))
    return struct.pack(sg.FORMAT_REKAMAN, s.seq, s.ts, s.temp if ok else 0, s.rh, s.amb, s.solar, s.speed, flags,
                       s.duty, s.harsh, baterai)


class ChipGolden:
    def __init__(self, model_json, pakai_duty: bool = True):
        self.model = ph.muat_model(model_json, pakai_duty)
        self.pakai_duty = pakai_duty

    def mulai_trip(self, prod: dict, kunci: bytes) -> None:
        self.cfg = fx.konfigurasi(prod["t_lo"], prod["t_hi"], prod["t_set"], prod["c"], prod["mass_kg"])
        self.fis = fx.MesinFisika(self.cfg)
        self.kunci, self.h = kunci, NOL
        self.q = {k: [] for k in ("temp", "amb", "solar", "rh", "door", "reefer", "speed", "harsh", "hour", "duty", "nan")}

    def proses(self, s: Sampel) -> HasilMenit:
        ok = s.temp is not None
        for k, v in (("temp", s.temp if ok else 0), ("amb", s.amb), ("solar", s.solar), ("rh", s.rh), ("door", int(s.door)),
                     ("reefer", int(s.reefer)), ("speed", s.speed), ("harsh", s.harsh), ("hour", s.hour),
                     ("duty", s.duty), ("nan", not ok)):
            self.q[k].append(v)
        t = len(self.q["temp"]) - 1
        o = self.fis.langkah(s.temp if ok else -32768, s.amb, s.door, s.speed >= 100)
        rek = rekaman(s)
        self.h = sg.segel(self.h, rek)
        diag_valid, kelas, skor = False, 0, [0] * 7
        if t >= 59:
            a = t - 59
            nan = np.array(self.q["nan"])
            if not nan[max(0, a - 1) if a > 0 else 0:t + 1].any():
                q = ph.ffill_temp({k: np.array(v) for k, v in self.q.items() if k != "nan"} | {"nan": nan})
                f = ph.fitur_bulat(q, t, self.pakai_duty)
                skor = ph.skor_bulat(self.model, f)
                kelas, diag_valid = ph.kelas_bulat(self.model, f), True
        paket = rm.paket_hasil(s.seq, t, o, diag_valid, kelas, skor[kelas] if diag_valid else 0)
        return HasilMenit(rek, self.h, paket, sg.mac(self.kunci, self.h, paket), skor, o["status"], diag_valid, kelas)


class _ChipRegister:
    """Urutan akses register per trip dan per menit; subkelas menyediakan tulis/baca."""

    batas = 0.5

    def tulis(self, alamat: int, nilai: int) -> None:
        raise NotImplementedError

    def baca(self, alamat: int) -> int:
        raise NotImplementedError

    def _cek_id(self, saran: str) -> None:
        if (i := self.baca(rm.ID)) != 0x43540001:
            raise RuntimeError(f"ID chip salah: {i:#x} ({saran})")

    def _tunggu(self, bit: int) -> None:
        akhir = time.monotonic() + self.batas
        while not self.baca(rm.STATUS) & bit:
            if time.monotonic() > akhir:
                raise TimeoutError(f"STATUS bit {bit:#x} tidak muncul")

    def _kata(self, alamat: int, n: int = 8) -> bytes:
        return b"".join(self.baca(alamat + 4 * i).to_bytes(4, "big") for i in range(n))

    def mulai_trip(self, prod: dict, kunci: bytes) -> None:
        cfg = fx.konfigurasi(prod["t_lo"], prod["t_hi"], prod["t_set"], prod["c"], prod["mass_kg"])
        if not self.baca(rm.STATUS) & 8:                       # kunci belum terkunci: tulis lalu kunci (sekali)
            for i in range(8):
                self.tulis(rm.KUNCI + 4 * i, int.from_bytes(kunci[4 * i:4 * i + 4], "big"))
            self.tulis(rm.CTRL, rm.C_KUNCI_TULIS)
            self.tulis(rm.CTRL, rm.C_KUNCI_KUNCI)
        for k in ("t_lo", "t_hi", "t_set", "batas_waspada"):
            self.tulis(rm.CFG[k], cfg[k])
        for k, v in (("k", cfg["k"]), ("ek", cfg["ek"])):
            self.tulis(rm.CFG[f"{k}_lo"], v & 0xFFFFFFFF)
            self.tulis(rm.CFG[f"{k}_hi"], v >> 32)
        self.tulis(rm.CTRL, rm.C_TRIP_RESET)

    def proses(self, s: Sampel) -> HasilMenit:
        ok = s.temp is not None
        nilai = {"seq": s.seq, "ts": s.ts, "temp": s.temp if ok else 0, "rh": s.rh, "amb": s.amb, "solar": s.solar,
                 "speed": s.speed, "duty": s.duty, "harsh": s.harsh,
                 "batt": min(255, max(0, round((s.battery_mv - 2000) / 10))), "hour": s.hour,
                 "flags": rm.flags(s.door, s.reefer, s.duty > 0, ok)}
        for k, v in nilai.items():
            self.tulis(rm.SAMPEL[k], v)
        self.tulis(rm.CTRL, rm.C_SAMPEL)
        self._tunggu(2)
        rf, diag, menit = self.baca(rm.R_FISIKA), self.baca(rm.R_DIAG), self.baca(rm.R_MENIT)
        tc = self.baca(rm.R_TC_HI) << 32 | self.baca(rm.R_TC_LO)
        tc = tc - (1 << 64) if tc >> 63 else tc
        skor = [self.baca(rm.R_SKOR + 4 * k) for k in range(7)]
        skor = [v - (1 << 32) if v >> 31 else v for v in skor]
        diag_valid, kelas = bool(diag & 8), diag & 7
        ttb_ada = bool(rf >> 7 & 1)
        fis = {"status": rf & 3, "alasan": (rf >> 2) & 7, "sensor": (rf >> 5) & 3, "tc": tc,
               "ttb": (rf >> 8) & 63 if ttb_ada else None, "ttb_mentah": (rf >> 8) & 63}
        paket = rm.paket_hasil(s.seq, menit, fis, diag_valid, kelas, skor[kelas] if diag_valid else 0)
        self.tulis(rm.CTRL, rm.C_MAC)
        self._tunggu(4)
        return HasilMenit(rekaman(s), self._kata(rm.R_RANTAI), paket, self._kata(rm.R_MAC), skor, fis["status"],
                          diag_valid, kelas)


class ChipAxi(_ChipRegister):
    """Register coldtrack_axil lewat /dev/mem. Model sudah tertanam di bitstream (nodes/trees/base.mem)."""

    def __init__(self, basis: int = BASIS_AXI, batas_tunggu_s: float = 0.5):
        self.fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
        self.mm = mmap.mmap(self.fd, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=basis)
        self.batas = batas_tunggu_s
        self._cek_id("bitstream ColdTrack belum dimuat?")

    def tulis(self, alamat: int, nilai: int) -> None:
        self.mm[alamat:alamat + 4] = struct.pack("<I", nilai & 0xFFFFFFFF)

    def baca(self, alamat: int) -> int:
        return struct.unpack("<I", self.mm[alamat:alamat + 4])[0]


class ChipSpi(_ChipRegister):
    """Chip ASIC lewat /dev/spidevB.C (paket `spidev`). SCK paling cepat clk chip / 8; model ada di flash QSPI chip,
    diagnosis hanya sah bila hash image cocok (STATUS bit 7)."""

    def __init__(self, bus: int = 0, cs: int = 0, hz: int = 4_000_000, batas_tunggu_s: float = 0.5):
        import spidev

        self.spi = spidev.SpiDev()
        self.spi.open(bus, cs)
        self.spi.mode = 0
        self.spi.max_speed_hz = hz
        self.batas = batas_tunggu_s
        self._cek_id("kabel SPI, clock chip, atau SCK terlalu cepat?")

    def tulis(self, alamat: int, nilai: int) -> None:
        self.spi.xfer2(list(sf.frame_tulis(alamat, nilai)))

    def baca(self, alamat: int) -> int:
        return sf.data_baca(bytes(self.spi.xfer2(list(sf.frame_baca(alamat)))))
