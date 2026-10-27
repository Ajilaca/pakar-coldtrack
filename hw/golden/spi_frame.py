"""Frame SPI chip ASIC (hw/rtl/spi_axil_bridge.sv), SPI mode 0, MSB dulu, satu transaksi per frame CS rendah.

  tulis: 6 byte MOSI = {1, 000, alamat 12 bit} + data 32 bit big-endian
  baca : 7 byte MOSI = {0, 000, alamat 12 bit} + 1 byte dummy + 4 byte bebas; data ada di 4 byte terakhir MISO
Register map sama dengan AXI4-Lite KV260 (hw/golden/regmap.py). SCK paling cepat clk chip / 8.
"""

TULIS = 0x8000


def frame_tulis(alamat: int, nilai: int) -> bytes:
    return (TULIS | (alamat & 0xFFF)).to_bytes(2, "big") + (nilai & 0xFFFFFFFF).to_bytes(4, "big")


def frame_baca(alamat: int) -> bytes:
    return (alamat & 0xFFF).to_bytes(2, "big") + bytes(5)


def data_baca(miso: bytes) -> int:
    return int.from_bytes(miso[3:7], "big")
