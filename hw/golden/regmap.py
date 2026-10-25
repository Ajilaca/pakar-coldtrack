"""Peta register AXI4-Lite hw/rtl/coldtrack_top.sv dan paket hasil yang di-HMAC (dipakai driver dan server).

Semua register 32 bit, alamat byte. Nilai bertanda 16 bit ditulis sebagai bilangan 32 bit (bit atas diabaikan).
"""

ID = 0x000              # RO 0x43540001
CTRL = 0x004            # WO pulsa: bit0 trip_reset, bit1 sampel_go, bit2 mac_go, bit3 kunci_kunci, bit4 kunci_tulis,
                        #           bit5 simpul_we, bit6 pohon_we, bit7 base_we
STATUS = 0x008          # RO: bit0 busy, bit1 hasil_valid, bit2 mac_valid, bit3 kunci_terkunci, bit4 siap, bit5 lengkap,
                        #     bit6 diag_valid
CFG = {"t_lo": 0x010, "t_hi": 0x014, "t_set": 0x018, "batas_waspada": 0x01C,
       "k_lo": 0x020, "k_hi": 0x024, "ek_lo": 0x028, "ek_hi": 0x02C}
SAMPEL = {"seq": 0x040, "ts": 0x044, "temp": 0x048, "rh": 0x04C, "amb": 0x050, "solar": 0x054, "speed": 0x058,
          "flags": 0x05C, "duty": 0x060, "harsh": 0x064, "batt": 0x068, "hour": 0x06C}
R_FISIKA = 0x080        # [1:0] status [4:2] alasan [6:5] sensor [7] ttb_valid [13:8] ttb [16] seri
R_TC_LO, R_TC_HI = 0x084, 0x088
R_DIAG = 0x08C          # [2:0] kelas [3] diag_valid
R_MENIT = 0x090
R_TS10_LO, R_TS10_HI = 0x094, 0x098
R_SKOR = 0x0A0          # 7 kata, kelas k di R_SKOR + 4k
R_RANTAI = 0x0C0        # 8 kata, kata 0 = bit 255..224
R_MAC = 0x0E0
KUNCI = 0x100           # 8 kata WO, lalu CTRL.kunci_tulis
M_SIMPUL_ADDR, M_SIMPUL_D0, M_SIMPUL_D1, M_SIMPUL_D2 = 0x180, 0x184, 0x188, 0x18C
M_POHON_ADDR, M_POHON_DATA, M_BASE_ADDR, M_BASE_DATA = 0x190, 0x194, 0x198, 0x19C

C_TRIP_RESET, C_SAMPEL, C_MAC, C_KUNCI_KUNCI, C_KUNCI_TULIS = 1, 2, 4, 8, 16
C_SIMPUL_WE, C_POHON_WE, C_BASE_WE = 32, 64, 128


def flags(pintu, reefer, kopling, temp_ok):
    return int(pintu) | int(reefer) << 1 | int(kopling) << 2 | int(temp_ok) << 3


def paket_hasil(seq, menit, fis, diag_valid, kelas, skor_kelas):
    """16 byte yang di-HMAC bersama rantai: hasil fisika (dict hw/golden/fisika) + diagnosis."""
    b_fis = int(fis["ttb"] is not None) << 7 | fis["sensor"] << 5 | fis["alasan"] << 2 | fis["status"]
    v = (seq & 0xFFFFFFFF) << 96 | (menit & 0xFFFF) << 80 | b_fis << 72 | ((fis["ttb_mentah"] or 0) & 0x3F) << 64
    v |= (int(diag_valid) << 3 | kelas) << 56 | ((fis["tc"] >> 8) & 0xFFFFFFFF) << 16 | ((skor_kelas >> 8) & 0xFFFF)
    return v.to_bytes(16, "big")
