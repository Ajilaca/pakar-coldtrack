"""Model acuan segel (hw/rtl/segel.sv): format rekaman 23 byte, rantai hash, dan HMAC paket hasil.

Rekaman (big-endian, 23 byte), satuan sama dengan masukan mesin fisika dan fitur model
(hw/golden/fisika.py, hw/golden/pohon.py), jadi yang disegel tepat yang dipakai chip:
  seq u32 | ts u32 (detik UNIX) | temp_c s16 (0,01 C) | humidity u16 (0,01 %) | ambient_c s16 (0,01 C) |
  solar u16 (1/16 W/m2) | speed u16 (0,01 km/jam) | flags u8 | duty u16 (1/10000) | harsh u8 |
  battery u8 (10 mV di atas 2,00 V)
flags: bit0 pintu terbuka, bit1 reefer menyala, bit2 kopling kompresor, bit3 sensor suhu valid.
Hasil (16 byte) diisi blok status; isinya bebas bagi segel.
"""

import hashlib
import hmac
import struct

FORMAT_REKAMAN = ">IIhHhHHBHBB"
assert struct.calcsize(FORMAT_REKAMAN) == 23


def c100(x):
    return round(x * 100)


def rekaman(seq, ts, temp_c, humidity, ambient_c, solar, speed_kmh, pintu, reefer, kopling,
            sensor_valid, duty, harsh, battery_mv):
    flags = int(pintu) | int(reefer) << 1 | int(kopling) << 2 | int(sensor_valid) << 3
    baterai = min(255, max(0, round((battery_mv - 2000) / 10)))
    return struct.pack(FORMAT_REKAMAN, seq, ts, c100(temp_c), c100(humidity), c100(ambient_c), round(solar * 16),
                       c100(speed_kmh), flags, round(duty * 10000), int(harsh), baterai)


def segel(h_prev: bytes, rek: bytes) -> bytes:
    assert len(h_prev) == 32 and len(rek) == 23
    return hashlib.sha256(h_prev + rek).digest()


def rantai(rekaman_list, h0=bytes(32)):
    h = h0
    for r in rekaman_list:
        h = segel(h, r)
    return h


def mac(kunci: bytes, h_rantai: bytes, hasil: bytes) -> bytes:
    assert len(kunci) == 32 and len(h_rantai) == 32 and len(hasil) == 16
    return hmac.new(kunci, h_rantai + hasil, hashlib.sha256).digest()


def verifikasi(kunci, rekaman_list, h_terkirim, hasil, mac_terkirim, h0=bytes(32)):
    """Sisi server: hitung ulang rantai dari rekaman yang diterima lalu cocokkan rantai dan MAC."""
    h = rantai(rekaman_list, h0)
    return h == h_terkirim and hmac.compare_digest(mac(kunci, h, hasil), mac_terkirim)
