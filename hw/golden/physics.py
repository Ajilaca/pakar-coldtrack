"""Model acuan fixed-point mesin fisika (port bilangan bulat dari backend/app/core/engine.py).

Dijalankan menit demi menit seperti RTL: setiap pemanggilan `langkah` hanya memakai data sampai
menit itu. Semua aritmetika bilangan bulat; RTL harus identik bit per bit dengan modul ini.

Format:
  suhu masukan, ambang      satuan 0,01 C (int); kelipatan 0,1 C data simulator jadi eksak
  Tc (observer), ts10, cab  satuan 0,01 C x 2^16 (int)
  k, e^-k                   Q0.40 (dihitung host sekali per trip)
  faktor P_T = e^-kT        Q0.40 (diperbarui satu perkalian per langkah pencarian T)

TTB dicari T = 0..60: T pertama yang memenuhi "sudah/akan melewati batas dalam T menit". Hasilnya
ceil(TTB float) bila <= 60; ambang status (<= 30, <= 60) dan aturan pintu (<= 30) tepat tanpa ln.
Perbandingan yang memakai rata-rata 10 menit dilakukan pada JUMLAH (S10 > ambang x n), eksak; ts10
(x 2^16) hanya dipakai di dalam perkalian dengan faktor P_T.
Bagian engine.py yang tidak di-port: door_budget._close_now (simulasi "bila pintu ditutup"), tidak
memengaruhi status.
"""

import math
from collections import deque

FRAK = 40
SATU = 1 << FRAK
Q = 100                      # satuan 0,01 C
SH = 16                      # 0,01 C -> 0,01 C x 2^16

SENSOR_MAX, SENSOR_MIN = 60 * Q, -40 * Q
LOMPAT = 5 * Q
FLAT_PASTI, FLAT_CURIGA = 60, 15
KONTEKS_AMB = 3 * Q          # kenaikan T_amb 30 mnt
FLAT_HARAP = round(0.3 * 30 * Q)  # (ts[s]-ts[s-30]) * flat >= 0,3*30 C
SLOPE5 = round(0.15 * 5 * Q)      # ts[i]-ts[i-5] > 0,75 C
DRIFT_D20 = round(0.005 * 20 * Q)  # ts10[i]-ts10[i-20] >= 0,1 C = 10 satuan, eksak
TTB_KRITIS, TTB_WASPADA, TTB_TAMPIL, PINTU_WASPADA = 30, 60, 60, 30
REC10 = [0] + [round((1 << 24) / n) for n in range(1, 11)]   # Q0.24

AMAN, WASPADA, KRITIS = 0, 1, 2
ALASAN = {0: "normal", 1: "di_luar_batas", 2: "ttb", 3: "mendekati_batas", 4: "pintu", 5: "sensor_rusak",
          6: "sensor_curiga"}


def konfigurasi(t_lo, t_hi, t_set, c_kj, mass_kg, h_conv=8.0, rho_bulk=500.0):
    """Nilai yang ditulis host (ARM KV260 / ESP32) ke register sekali per trip."""
    ua = h_conv * 6.0 * (mass_kg / rho_bulk) ** (2 / 3)
    k = min(ua / (mass_kg * c_kj * 1000.0) * 60.0, 1.0)
    margin = min(1.0, 0.25 * (t_hi - t_lo))
    return {"t_lo": round(t_lo * Q), "t_hi": round(t_hi * Q), "t_set": round(t_set * Q),
            "batas_waspada": round((t_hi - margin) * Q), "k": round(k * SATU),
            "ek": round(math.exp(-k) * SATU), "k_float": k}


def q(x):
    return round(x * Q)


class MesinFisika:
    def __init__(self, cfg):
        self.c = cfg
        self.i = 0
        n = 100
        self.raw = deque(maxlen=n)
        self.bad = deque(maxlen=n)
        self.clean = deque(maxlen=n)
        self.amb = deque(maxlen=n)
        self.door = deque(maxlen=n)
        self.mov = deque(maxlen=n)
        self.ts10 = deque(maxlen=21)
        self.flat = 0
        self.prev = None
        self.last_ok = None
        self.last_clean = cfg["t_set"]
        self.tc = None
        self.clean_prev = None

    @staticmethod
    def _ambil(buf, lag):
        return buf[-1 - lag]

    def _sensor(self, ts, bad, i):
        st = 2 if bad else 0
        if bad:
            self.flat, self.prev = 0, None
            return st
        self.flat = self.flat + 1 if (self.prev is not None and ts == self.prev) else 0
        self.prev = ts
        if self.last_ok is not None and abs(ts - self.last_ok) > LOMPAT and i > 0:
            w = min(i, 10)
            sah = any(self._ambil(self.door, j) for j in range(w + 1)) or \
                any(self._ambil(self.mov, j) != self.mov[-1] for j in range(w + 1))
            if not sah:
                st = max(st, 1)
        self.last_ok = ts
        if self.flat >= FLAT_PASTI:
            st = 2
        elif self.flat >= FLAT_CURIGA:
            f = self.flat
            ctx = any(self._ambil(self.door, j) for j in range(min(f, i) + 1)) or \
                (self.amb[-1] - self._ambil(self.amb, min(30, i))) >= KONTEKS_AMB
            s = i - f
            if not ctx and s >= 30 and not any(self._ambil(self.bad, f + j) for j in range(31)):
                ctx = (self._ambil(self.raw, f) - self._ambil(self.raw, f + 30)) * f >= FLAT_HARAP
            if ctx:
                st = max(st, 1)
        return st

    def langkah(self, ts_raw, t_amb, pintu, bergerak):
        """ts_raw, t_amb: int satuan 0,01 C; pintu, bergerak: bool. Kembalikan dict keluaran menit ini."""
        c, i = self.c, self.i
        bad = ts_raw > SENSOR_MAX or ts_raw < SENSOR_MIN
        self.raw.append(ts_raw)
        self.bad.append(bad)
        self.amb.append(t_amb)
        self.door.append(bool(pintu))
        self.mov.append(bool(bergerak))
        sst = self._sensor(ts_raw, bad, i)

        clean = self.last_clean if bad else ts_raw
        self.last_clean = clean
        self.clean.append(clean)

        # observer muatan: Tc[0] = ts[0]; Tc[i] = Tc[i-1] + k (ts[i-1] - Tc[i-1])
        if self.tc is None:
            self.tc = clean << SH
        else:
            self.tc += (c["k"] * ((self.clean_prev << SH) - self.tc)) >> FRAK
        self.clean_prev = clean
        tc = self.tc

        seri = False      # ada perbandingan yang tepat di ambang (float engine.py bisa memutus beda)
        n10 = min(i + 1, 10)
        s10 = sum(self._ambil(self.clean, j) for j in range(n10))
        ts10 = (s10 * REC10[n10]) >> 8                                  # x 2^24/n >> 8 = rata-rata x 2^16
        self.ts10.append((s10, n10))

        thi, tlo = c["t_hi"] << SH, c["t_lo"] << SH
        hi8 = c["t_hi"]
        naik5 = i >= 5 and (clean - self._ambil(self.clean, 5)) > SLOPE5
        naik5_seri = i >= 5 and (clean - self._ambil(self.clean, 5)) == SLOPE5
        panas = pintu or (not bergerak and naik5)
        amb24 = t_amb << SH
        ts10_di_atas_hi = s10 > hi8 * n10                               # ts10 > t_hi, eksak
        if panas and t_amb * n10 > s10:
            cab, cab_di_atas_hi = amb24, t_amb > hi8
        else:
            cab, cab_di_atas_hi = ts10, ts10_di_atas_hi
        sudah = tc >= thi
        bisa = (not sudah) and cab_di_atas_hi

        # hanyut: (ts10[i] - ts10[i-20]) / 20 >= 0,005 lewat jumlah, tanpa pembagian
        if i >= 20:
            sj, nj = self._ambil(self.ts10, 20)
            d20_num = nj * s10 - n10 * sj                               # = n10*nj*(ts10[i]-ts10[i-20])
            naik20 = d20_num >= DRIFT_D20 * n10 * nj
            seri = seri or d20_num == DRIFT_D20 * n10 * nj
        else:
            nj, d20_num, naik20 = 1, 0, False
        pintu30 = any(self._ambil(self.door, j) for j in range(min(i, 29) + 1))
        hanyut = naik20 and not pintu30 and s10 < hi8 * n10

        ttb = None
        p = SATU
        p30 = None
        for t in range(TTB_TAMPIL + 1):
            if t > 0:
                p = (p * c["ek"]) >> FRAK
            if t == PINTU_WASPADA:
                p30 = p
            # hanyut <= T: 20 (t_hi - ts10) <= T (ts10[i]-ts10[i-20]), dikali n10*nj -> bilangan bulat
            fisik = sudah or (bisa and ((cab - thi) << FRAK) >= p * (cab - tc))
            kiri, kanan = 20 * nj * (hi8 * n10 - s10), t * d20_num
            if ttb is None and (fisik or (hanyut and kiri <= kanan)):
                ttb = t
                seri = seri or (not fisik and kiri == kanan and t in (TTB_KRITIS, TTB_WASPADA))
        if pintu:
            if tc >= thi:
                pintu_bahaya = True
            elif amb24 <= thi:
                pintu_bahaya = False
            else:
                pintu_bahaya = ((amb24 - thi) << FRAK) >= p30 * (amb24 - tc)
        else:
            pintu_bahaya = False

        s, alasan = AMAN, 0

        def naik(level, kode):
            nonlocal s, alasan
            if level > s:
                s, alasan = level, kode

        if tc >= thi or tc < tlo:
            naik(KRITIS, 1)
        if ttb is not None and ttb <= TTB_KRITIS:
            naik(KRITIS, 2)
        if ttb is not None and ttb <= TTB_WASPADA:
            naik(WASPADA, 2)
        seri = seri or s10 == c["batas_waspada"] * n10 or s10 == hi8 * n10 or naik5_seri
        if tc > (c["batas_waspada"] << SH) or s10 > c["batas_waspada"] * n10:
            naik(WASPADA, 3)
        if pintu_bahaya:
            naik(WASPADA, 4)
        if sst == 2:
            s, alasan = WASPADA, 5
        elif sst == 1:
            naik(WASPADA, 6)

        self.i += 1
        return {"status": s, "alasan": alasan, "ttb": ttb if (ttb is not None and sst < 2) else None,
                "ttb_mentah": ttb, "sensor": sst, "tc": tc, "ts10": ts10, "seri": seri}
