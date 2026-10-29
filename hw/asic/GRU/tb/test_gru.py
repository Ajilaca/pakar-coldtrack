"""Tes cocotb gru_engine: keluaran RTL harus identik bit dengan golden (hw/asic/GRU/golden/gru_golden.py).
Kasus (image, masukan, harapan) disiapkan runner_gru.py; berkas harapan lewat env GRU_EXP (atau ERR untuk header rusak)."""
import os

import cocotb
from cocotb.triggers import First, RisingEdge, Timer


@cocotb.test()
async def gru_cocok_golden(dut):
    exp = open(os.environ["GRU_EXP"]).read().split()
    batas_ns = int(os.environ.get("GRU_TIMEOUT_NS", "2000000000"))
    hasil = await First(RisingEdge(dut.done), Timer(batas_ns, "ns"))
    assert dut.done.value == 1, "timeout: done tidak muncul"
    siklus = int(dut.cyc.value) - int(dut.cyc_mulai.value)
    if exp == ["ERR"]:
        assert dut.err.value == 1, "header rusak harus memberi err = 1"
        dut._log.info(f"header rusak ditolak setelah {siklus} siklus")
        return
    assert dut.err.value == 0, "err = 1 untuk image sah"
    beda = []
    for i, e in enumerate(int(x) for x in exp):
        dut.out_idx.value = i
        await Timer(1, "ns")
        v = dut.out_data.value.to_signed()
        if v != e:
            beda.append((i, v, e))
    dut._log.info(f"{len(exp)} keluaran, {siklus} siklus, {os.path.basename(os.environ['GRU_EXP'])}")
    assert not beda, f"keluaran beda (idx, rtl, golden): {beda}"
    del hasil
