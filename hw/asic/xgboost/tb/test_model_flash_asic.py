"""model_flash versi ASIC (hw/asic/xgboost/rtl/model_flash.sv): model di flash diverifikasi dengan tag HMAC, bukan hash tetap.

Testbench hw/tb/model_flash_tb.sv; parameter HASH_MODEL berisi kunci uji. Flash A = model b9 bertag, flash B = model
b8 bertag dengan kunci yang sama.
1. Model b9: skor dan kelas identik bit per bit dengan hw/golden/trees.py, sah.
2. Satu byte image dibalik -> tidak sah; dikembalikan -> sah lagi.
3. Satu byte tag dibalik -> tidak sah; dikembalikan -> sah lagi.
4. Ganti model: b8 bertag kunci yang sama -> sah, skor identik dengan golden b8 (model baru tanpa chip baru).
5. Tag dibuat dengan kunci lain -> tidak sah.
6. Header dirusak (jumlah simpul melebihi batas) -> baca dihentikan lebih awal, tidak sah, done tetap muncul.
"""

import os
import sys
from pathlib import Path

import cocotb
from cocotb.triggers import FallingEdge

HW = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(HW.parent))
sys.path.insert(0, str(HW / "tb"))
from hw.asic.xgboost.golden import flash_tag as ft  # noqa: E402
from test_model_flash import flash_tulis, jalankan, reset  # noqa: E402

N_JENDELA = int(os.environ.get("N_JENDELA_FLASH", "12"))
SAH = 0xA5
DUTY, LAIN = HW / "model" / "xgb_v5_context_duty", HW / "model" / "xgb_v5_context"
KUNCI = bytes(range(0xA0, 0xC0))           # kunci uji, bukan kunci produksi (sama dengan test_asic.py)
B8, B9 = "b8_xgb_chip_v5_context", "b9_xgb_chip_v5_context_synthetic_duty"


def kasus(duty, n, seed):
    """n pasangan (trip val, menit >= 59) acak -> (fitur int, skor golden, kelas golden).

    Sama dengan hw/tb/test_tree_engine.kasus, tetapi jendela diambil langsung dari parquet tanpa bench/b8_lib
    (yang membutuhkan torch).
    """
    import numpy as np
    import pandas as pd

    from hw.golden import trees as ph
    from hw.golden.check_trees import duty_trip

    df = pd.read_parquet(HW.parent / "data/processed/v4_seed1000_700trips.parquet")
    val = df[df.split == "val"]
    m = ph.muat_model(HW.parent / f"bench/results/local-cpu/B10/{B9 if duty else B8}.json", duty)
    rng = np.random.default_rng(seed)
    out = []
    for tid in rng.permutation(sorted(val.trip_id.unique())):
        g = val[val.trip_id == tid].sort_values("minute").reset_index(drop=True)
        if len(g) <= 60:
            continue
        t = int(rng.integers(59, len(g)))
        q = ph.ffill_temp(ph.kuantisasi_trip(g, duty_trip(g, int(tid)) if duty else None))
        f = ph.fitur_bulat(q, t, duty)
        out.append((f, ph.skor_bulat(m, f), ph.kelas_bulat(m, f)))
        if len(out) == n:
            break
    return out


@cocotb.test()
async def flash_hmac_ganti_model(dut):
    await reset(dut)
    isi = ft.image_bertag(DUTY, KUNCI)
    n_img = len(isi) - 32

    # 1. model b9
    data = kasus(True, N_JENDELA, 21)
    siklus_maks = 0
    for n, (f, skor_g, kelas_g) in enumerate(data):
        skor, kelas, pola, siklus = await jalankan(dut, f)
        assert pola == SAH, f"jendela {n}: model bertag kunci benar harus sah (pola {pola:#x})"
        assert skor == skor_g and kelas == kelas_g, f"jendela {n}: skor {skor} != golden {skor_g}"
        siklus_maks = max(siklus_maks, siklus)
    dut._log.info(f"b9: {len(data)} jendela identik dengan golden, {siklus_maks} siklus per inferensi")
    f, skor_g, _ = data[0]

    # 2. satu byte image, 3. satu byte tag
    for a, nama in ((n_img // 2, "image"), (n_img + 31, "tag")):
        await flash_tulis(dut, a, isi[a] ^ 0x01)
        *_, pola, _ = await jalankan(dut, f)
        assert pola != SAH, f"{nama} yang diubah harus ditolak"
        await flash_tulis(dut, a, isi[a])
        skor, _, pola, _ = await jalankan(dut, f)
        assert pola == SAH and skor == skor_g, f"setelah {nama} dikembalikan harus sah lagi"

    # 4. ganti model: b8 bertag kunci yang sama
    dut.pakai_b.value = 1
    for n, (f8, skor8, kelas8) in enumerate(kasus(False, max(2, N_JENDELA // 3), 22)):
        skor, kelas, pola, _ = await jalankan(dut, f8)
        assert pola == SAH, f"b8 jendela {n}: model baru bertag kunci benar harus sah"
        assert skor == skor8 and kelas == kelas8, f"b8 jendela {n}: skor {skor} != golden {skor8}"
    dut.pakai_b.value = 0
    dut._log.info("model b8 bertag kunci yang sama diterima dan identik dengan golden b8")

    # 5. tag dari kunci lain
    palsu = ft.tag(bytes(32 * [0x5A]), isi[:n_img])
    for i in range(32):
        await flash_tulis(dut, n_img + i, palsu[i])
    *_, pola, _ = await jalankan(dut, f)
    assert pola != SAH, "tag dari kunci lain harus ditolak"
    for i in range(32):
        await flash_tulis(dut, n_img + i, isi[n_img + i])

    # 6. header: n_simpul (byte 4..5) dibuat 0xFFFF > MAX_SIMPUL
    for i in (4, 5):
        await flash_tulis(dut, i, 0xFF)
    *_, pola, siklus = await jalankan(dut, f)
    assert pola != SAH, "header buruk harus ditolak"
    assert siklus < 1000, f"header buruk harus berhenti lebih awal ({siklus} siklus)"
    for i in (4, 5):
        await flash_tulis(dut, i, isi[i])
    skor, _, pola, _ = await jalankan(dut, f)
    assert pola == SAH and skor == skor_g
    await FallingEdge(dut.clk)
    dut._log.info("byte image, byte tag, kunci lain, dan header buruk ditolak; model asli dan model baru diterima")
