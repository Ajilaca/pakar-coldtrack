"""Jendela inferensi per truk dari baris telemetry (CONTEXT_FLEET_SCALEUP.md Fase 3).

- Grid 1 menit: ts dibulatkan ke bawah ke menit, duplikat dalam satu menit -> bacaan terakhir.
- Celah <= ffill_maks_menit diisi bacaan terakhir; celah lebih panjang TIDAK diisi sebagian
  (menit-menit itu tetap kosong dan dibuang, sama seperti /analyze memperlakukan bacaan yang hilang).
- Keadaan data:
    TIDAK_ADA_DATA  tidak ada bacaan dalam offline_setelah_menit terakhir (menurut app/clock), atau trip belum
                    punya bacaan. Truk seperti ini TIDAK PERNAH ditampilkan AMAN.
    MENUNGGU_DATA   kurang dari 60 menit bacaan sejak awal trip (model butuh jendela 60 menit).
    OK              jendela siap; `data_lengkap` False bila 60 menit terakhir masih berlubang setelah pengisian.
- Zona waktu: ts disimpan UTC (docs/device_contract.md), tetapi fitur hour_of_day model dilatih dengan JAM LOKAL
  (ml/coldtrack_sim.py, skenario demo WIB). Bacaan jendela dikonversi ke `zona_waktu` (config fleet.zona_waktu,
  bawaan Asia/Jakarta) sebelum masuk model; tanpa ini fitur jam bergeser 7 jam.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from app.schemas import TelemetryReading

WINDOW = 60
KOLOM = ["temp_c", "humidity", "ambient_c", "door_open", "reefer_on", "speed_kmh", "harsh_events",
         "solar_radiation", "lat", "lon"]


@dataclass
class Jendela:
    keadaan: str                                   # TIDAK_ADA_DATA | MENUNGGU_DATA | OK
    readings: list[TelemetryReading] = field(default_factory=list)
    last_ts: datetime | None = None                # bacaan ASLI terakhir (bukan hasil pengisian)
    data_lengkap: bool = True
    menit_diisi: int = 0                           # menit hasil pengisian di 60 menit terakhir
    menit_hilang: int = 0                          # menit kosong (tak diisi) di rentang 60 menit terakhir
    n_menit: int = 0

    def catatan(self) -> str | None:
        if self.keadaan == "TIDAK_ADA_DATA":
            return "Tidak ada bacaan dari perangkat. Status tidak dapat dinilai; periksa logger/sinyal."
        if self.keadaan == "MENUNGGU_DATA":
            return f"Baru {self.n_menit} dari {WINDOW} menit data sejak awal trip; model belum dijalankan."
        if not self.data_lengkap:
            return (f"{self.menit_hilang} menit data hilang dalam 60 menit terakhir (celah > pengisian maksimum); "
                    "diagnosis kurang andal. Status tetap dari mesin fisika.")
        if self.menit_diisi:
            return f"{self.menit_diisi} menit diisi bacaan sebelumnya (celah pendek)."
        return None


def _isi_celah_pendek(df: pd.DataFrame, maks: int) -> tuple[pd.DataFrame, np.ndarray]:
    """ffill hanya untuk rangkaian menit kosong sepanjang <= maks. Kembalikan (df, mask menit hasil isi)."""
    kosong = df["temp_c"].isna().to_numpy()
    isi = np.zeros(len(df), dtype=bool)
    i = 0
    while i < len(kosong):
        if kosong[i]:
            j = i
            while j < len(kosong) and kosong[j]:
                j += 1
            if j - i <= maks and i > 0 and j < len(kosong):   # celah di tengah (bukan di ujung) dan pendek
                isi[i:j] = True
            i = j
        else:
            i += 1
    filled = df.ffill()
    df = df.copy()
    df.loc[isi] = filled.loc[isi]
    return df, isi


def bangun_jendela(rows: pd.DataFrame, now: datetime, ffill_maks_menit: int = 5,
                   offline_setelah_menit: int = 10, zona_waktu: str = "Asia/Jakarta") -> Jendela:
    """rows: kolom ts (UTC) + KOLOM, bacaan trip aktif (sudah dibatasi history_cap_min oleh pemanggil)."""
    if rows.empty:
        return Jendela("TIDAK_ADA_DATA")
    df = rows.copy()
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.floor("min")
    df = df.sort_values("ts").drop_duplicates("ts", keep="last").set_index("ts")
    last_ts = df.index[-1].to_pydatetime()
    if now - last_ts > timedelta(minutes=offline_setelah_menit):
        return Jendela("TIDAK_ADA_DATA", last_ts=last_ts)

    grid = pd.date_range(df.index[0], df.index[-1], freq="min")
    df = df.reindex(grid)[KOLOM]
    df, isi = _isi_celah_pendek(df, ffill_maks_menit)
    ada = df["temp_c"].notna().to_numpy()
    akhir = slice(max(0, len(df) - WINDOW), len(df))
    menit_diisi, menit_hilang = int(isi[akhir].sum()), int((~ada[akhir]).sum())
    df = df[ada]
    n = len(df)
    if n < WINDOW:
        return Jendela("MENUNGGU_DATA", last_ts=last_ts, n_menit=n)

    df.index = df.index.tz_convert(zona_waktu)
    recs = df.reset_index(names="ts").to_dict("records")
    readings = []
    for r in recs:
        r = {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in r.items()}
        r["door_open"], r["reefer_on"] = bool(r["door_open"]), bool(r["reefer_on"])
        r["harsh_events"] = int(r["harsh_events"] or 0)
        r["ts"] = r["ts"].to_pydatetime()
        readings.append(TelemetryReading.model_validate(r))
    # 60 bacaan terakhir harus 60 menit berurutan; selain itu ada celah yang tidak diisi
    lengkap = (readings[-1].ts - readings[-WINDOW].ts) == timedelta(minutes=WINDOW - 1)
    return Jendela("OK", readings=readings, last_ts=last_ts, data_lengkap=lengkap,
                   menit_diisi=menit_diisi, menit_hilang=menit_hilang, n_menit=n)
