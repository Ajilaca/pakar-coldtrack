"""model_flash: bobot pohon dari flash QSPI eksternal, diperiksa SHA-256 tiap inferensi.

1. Skor dan kelas identik bit per bit dengan hw/golden/trees.py (model b9 dari flash, hash cocok -> sah).
2. Satu byte simpul dibalik di flash -> tidak sah; dikembalikan -> sah lagi.
3. Image model lain yang strukturnya benar (b8) dipasang -> tidak sah, karena hash beda.
4. Header dirusak (jumlah simpul melebihi batas) -> baca dihentikan lebih awal, tidak sah, done tetap muncul.
"""

import os
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge, RisingEdge, with_timeout

HW = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HW.parent))
from hw.golden import flash_image as fi

SW, N_JENDELA = 32, int(os.environ.get("N_JENDELA_FLASH", "20"))
SAH = 0xA5
DUTY, LAIN = HW / "model" / "xgb_v5_context_duty", HW / "model" / "xgb_v5_context"


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    for s in ("rst_n", "fitur_we", "fitur_addr", "fitur_data", "start", "pakai_b", "tulis", "tulis_addr",
              "tulis_data"):
        getattr(dut, s).value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)


async def flash_tulis(dut, addr, nilai):
    dut.tulis.value = 1
    dut.tulis_addr.value = addr
    dut.tulis_data.value = nilai
    await FallingEdge(dut.clk)
    dut.tulis.value = 0


async def jalankan(dut, f):
    dut.fitur_we.value = 1
    for a, v in enumerate(f):
        dut.fitur_addr.value = a
        dut.fitur_data.value = v
        await FallingEdge(dut.clk)
    dut.fitur_we.value = 0
    dut.start.value = 1
    await FallingEdge(dut.clk)
    dut.start.value = 0
    t0 = cocotb.utils.get_sim_time("ns")
    await with_timeout(RisingEdge(dut.done), 20, "ms")
    await FallingEdge(dut.clk)
    siklus = int((cocotb.utils.get_sim_time("ns") - t0) / 10)
    assert not dut.perintah_salah.value, "perintah ke flash salah"
    assert dut.cs_n.value == 1, "CS harus naik setelah selesai"
    raw = int(dut.skor.value)
    skor = [((raw >> (k * SW)) & ((1 << SW) - 1)) for k in range(7)]
    skor = [s - (1 << SW) if s >> (SW - 1) else s for s in skor]
    return skor, int(dut.kelas.value), int(dut.pola_sah.value), siklus


@cocotb.test()
async def flash_sah_manipulasi_tukar(dut):
    from test_tree_engine import kasus

    await reset(dut)
    img = fi.image(DUTY)
    data = kasus(True, N_JENDELA, 21)

    siklus_maks = 0
    for n, (f, skor_g, kelas_g) in enumerate(data):
        skor, kelas, pola, siklus = await jalankan(dut, f)
        assert pola == SAH, f"jendela {n}: model asli harus sah (pola {pola:#x})"
        assert skor == skor_g and kelas == kelas_g, f"jendela {n}: skor {skor} != golden {skor_g}"
        siklus_maks = max(siklus_maks, siklus)
    dut._log.info(f"{len(data)} jendela identik dengan golden, {siklus_maks} siklus per inferensi "
                  f"({len(img)} byte image)")

    f, skor_g, _ = data[0]
    # 2. satu bit ambang di tengah image dibalik
    a = len(img) // 2
    await flash_tulis(dut, a, img[a] ^ 0x01)
    *_, pola, _ = await jalankan(dut, f)
    assert pola != SAH, "image yang diubah harus ditolak"
    await flash_tulis(dut, a, img[a])
    skor, _, pola, _ = await jalankan(dut, f)
    assert pola == SAH and skor == skor_g, "setelah dikembalikan harus sah lagi"

    # 3. model lain yang strukturnya benar
    dut.pakai_b.value = 1
    *_, pola, _ = await jalankan(dut, f)
    assert pola != SAH, "model dengan hash lain harus ditolak"
    dut.pakai_b.value = 0

    # 4. header: n_simpul (byte 4..5) dibuat 0xFFFF > MAX_SIMPUL
    for i in (4, 5):
        await flash_tulis(dut, i, 0xFF)
    *_, pola, siklus = await jalankan(dut, f)
    assert pola != SAH, "header buruk harus ditolak"
    assert siklus < 1000, f"header buruk harus berhenti lebih awal ({siklus} siklus)"
    for i in (4, 5):
        await flash_tulis(dut, i, img[i])
    *_, pola, _ = await jalankan(dut, f)
    assert pola == SAH
    dut._log.info("manipulasi byte, tukar model, dan header buruk ditolak; image asli diterima lagi")


def test_model_flash():
    from runner import jalankan

    build = HW / "build" / "flash"
    berkas = {}
    for nama, folder in (("a", DUTY), ("b", LAIN)):
        berkas[nama] = build / f"{folder.name}.hex"
        fi.tulis_hex(fi.image(folder), berkas[nama])
    h = fi.sha256(fi.image(DUTY))
    jalankan("model_flash_tb", ["sha256_core.sv", "sha256_stream.sv", "qspi_reader.sv", "tree_stream.sv",
                                "model_flash.sv", "tb/spi_flash_model.sv", "tb/model_flash_tb.sv"],
             "test_model_flash",
             parameters={"BERKAS_A": f'"{berkas["a"]}"', "BERKAS_B": f'"{berkas["b"]}"', "HASH_MODEL": f"256'h{h}"})
