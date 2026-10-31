"""Tes versi ASIC (hw/asic/xgboost/rtl): skenario dan model golden sama dengan tes FPGA di hw/tb, DUT dari sumber ASIC.

Jalankan dari folder ini:  ../../../../.venv/bin/python -m pytest -q test_asic.py
Setiap tes memakai modul tes cocotb dari hw/tb, jadi kriteria lulusnya identik dengan versi FPGA: semua keluaran
sama bit per bit dengan golden. Register tanpa reset diisi nilai acak (lihat runner_asic.py).
Bedanya model_flash: versi ASIC memverifikasi tag HMAC di flash (image bertag, parameter HASH_MODEL = kunci uji);
test_model_flash_asic.py menguji penolakan dan penggantian model.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner_asic import HW, jalankan  # noqa: E402

RAM = ["asic/xgboost/sim/RAM256.v", "asic/xgboost/sim/sky130_fd_sc_hd__dfrtp_4.v", "asic/xgboost/rtl/ring_sram.sv"]
FITUR = RAM + ["rtl/floor_div.sv", "asic/xgboost/rtl/features.sv"]
FISIKA = ["asic/xgboost/rtl/serial_mul.sv", "asic/xgboost/rtl/physics.sv"]
INTI = (["rtl/sha256_core.sv", "rtl/seal.sv"] + FISIKA + FITUR
        + ["rtl/tree_engine.sv", "rtl/sha256_stream.sv", "rtl/qspi_reader.sv", "rtl/tree_stream.sv",
           "asic/xgboost/rtl/model_flash.sv", "rtl/coldtrack_top.sv"])
BATAS = {"BATAS_DONE_FISIKA": "3000", "BATAS_DONE_FITUR": "6000"}
KUNCI = bytes(range(0xA0, 0xC0))           # kunci uji, bukan kunci produksi


def test_features_asic():
    jalankan("features", FITUR, "test_features", extra_env=BATAS)


def test_physics_asic():
    jalankan("physics", FISIKA, "test_physics", extra_env=BATAS)


def _flash(nama="xgb_v5_context_duty"):
    """Image bertag kunci uji sebagai hex untuk spi_flash_model."""
    from hw.asic.xgboost.golden import flash_tag as ft
    from hw.golden import flash_image as fi

    folder = HW / "model" / nama
    berkas = HW / "build" / "flash" / f"asic_{nama}.hex"
    fi.tulis_hex(ft.image_bertag(folder, KUNCI), berkas)
    return berkas


def test_model_flash_asic():
    sys.path.insert(0, str(HW.parent))
    jalankan("model_flash_tb", ["rtl/sha256_core.sv", "rtl/sha256_stream.sv", "rtl/qspi_reader.sv",
                                "rtl/tree_stream.sv", "asic/xgboost/rtl/model_flash.sv", "tb/spi_flash_model.sv",
                                "tb/model_flash_tb.sv"],
             "test_model_flash_asic",
             parameters={"BERKAS_A": f'"{_flash()}"', "BERKAS_B": f'"{_flash("xgb_v5_context")}"',
                         "HASH_MODEL": f"256'h{KUNCI.hex()}"})


def test_coldtrack_top_flash_asic():
    sys.path.insert(0, str(HW.parent))
    jalankan("coldtrack_top_flash_tb", INTI + ["tb/spi_flash_model.sv", "tb/coldtrack_top_flash_tb.sv"],
             "test_coldtrack_top", parameters={"BERKAS_A": f'"{_flash()}"', "HASH_MODEL": f"256'h{KUNCI.hex()}"},
             extra_env={"CT_FLASH": "1", **BATAS})


def test_coldtrack_asic():
    """Top layout ASIC lewat SPI: sinkroniser reset + coldtrack_spi + physics/features/model_flash versi ASIC."""
    sys.path.insert(0, str(HW.parent))
    jalankan("coldtrack_asic_tb", INTI + ["rtl/spi_axil_bridge.sv", "rtl/coldtrack_spi.sv", "asic/xgboost/rtl/rst_sync.sv",
                                          "asic/xgboost/rtl/coldtrack_asic.sv", "tb/spi_flash_model.sv",
                                          "asic/xgboost/tb/coldtrack_asic_tb.sv"],
             "test_coldtrack_top", parameters={"BERKAS_A": f'"{_flash()}"', "HASH_MODEL": f"256'h{KUNCI.hex()}"},
             extra_env={"CT_SPI": "1", **BATAS})
