"""Pembuat skenario data per menit untuk uji FPGA tanpa sensor (jalan di laptop, hasilnya CSV untuk fpga_only.py).

Suhu kabin memakai model termal sederhana [SIM], bukan data nyata: kebocoran dinding, pintu terbuka, dan pendinginan
reefer menuju titik setel. Sinyal kompresor (duty) memakai bench/experiments/b9/b9_lib.sinyal_trip, fungsi yang sama
dengan data latih model chip. Radiasi matahari mengikuti jam lokal mulai (--jam-mulai); jalankan skenario pada jam
yang dekat dengan jam sebenarnya supaya radiasi cocok dengan fitur jam yang dibaca chip dari jam dinding.

Skenario: normal, pintu_terbuka, reefer_mati, prapendinginan_buruk, sensor_macet.

  python -m hw.driver.skenario --semua
  python -m hw.driver.skenario --nama reefer_mati --menit 240 --profil vaksin_2_8C --jam-mulai 9
"""

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hw.driver.fpga_only import KOLOM, profil

KELUAR = ROOT / "hw/driver/skenario"
NAMA = ["normal", "pintu_terbuka", "reefer_mati", "prapendinginan_buruk", "sensor_macet"]
CARGO_B9 = {"vaksin_2_8C": "vaksin_2_8C", "daging_beku_-18C": "daging_beku", "buah_segar_2_4C": "sayur_buah",
            "ikan_segar_0_5C": "ikan_segar", "produk_susu_2_4C": "produk_susu"}
K_BOCOR, K_PINTU, K_REEFER = 0.005, 0.03, 0.2     # [SIM] pecahan selisih suhu per menit
DERAU_SENSOR_C = 0.05                             # sama dengan derau sensor simulator
# Di data latih kecepatan hanya 0 atau 60 km/j (99,5 % baris 60, termasuk saat pintu terbuka). Kecepatan lain, mis.
# 50 km/j, membuat diagnosis model selalu A7 (diuji di trip A0 asli), jadi skenario memakai 60 km/j konstan.
KECEPATAN = 6000
TITIK_EMBUN_C = 22.0                              # kelembapan mengikuti suhu luar pada titik embun tetap


def jam_ke_luar(jam: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    amb = 27 + 4 * np.sin(np.pi * (jam - 9) / 12)
    solar = np.maximum(0, 700 * np.sin(np.pi * (jam - 6) / 12))
    b, c = 17.62, 243.12
    rh = np.clip(100 * np.exp(b * TITIK_EMBUN_C / (c + TITIK_EMBUN_C) - b * amb / (c + amb)), 5, 100)
    return amb, solar, rh


def bangun(nama: str, n: int, nama_profil: str, jam_mulai: float, seed: int) -> list[dict]:
    import pandas as pd

    from bench.experiments.b9 import b9_lib

    p = profil(nama_profil, None)
    rng = np.random.default_rng(seed)
    jam = (jam_mulai + np.arange(n) / 60) % 24
    amb, solar, rh = jam_ke_luar(jam)
    onset = 70
    pintu = np.zeros(n, bool)
    reefer = np.ones(n, bool)
    sensor_beku_dari = None
    suhu0 = p["t_set"] + 0.5
    if nama == "pintu_terbuka":
        pintu[onset:onset + 20] = True
    elif nama == "reefer_mati":
        reefer[onset:] = False
    elif nama == "prapendinginan_buruk":
        suhu0 = p["t_hi"] + 3.0
    elif nama == "sensor_macet":
        pintu[60:72] = True
        sensor_beku_dari = 75

    t = np.empty(n)
    t[0] = suhu0
    for i in range(1, n):
        dt = K_BOCOR * (amb[i] - t[i - 1]) + (K_PINTU * (amb[i] - t[i - 1]) if pintu[i] else 0.0)
        if reefer[i]:
            dt += K_REEFER * (p["t_set"] - t[i - 1])
        t[i] = t[i - 1] + dt
    temp = t + rng.normal(0, DERAU_SENSOR_C, n)
    if sensor_beku_dari is not None:
        temp[sensor_beku_dari:] = temp[sensor_beku_dari]

    g = pd.DataFrame({"ambient_c": amb, "temp_true_c": t, "solar_radiation": solar, "door_open": pintu.astype(float),
                      "cargo_type": CARGO_B9.get(nama_profil, "vaksin_2_8C")})
    mode = "A3" if nama == "reefer_mati" else "A0"
    duty, _ = b9_lib.sinyal_trip(g, mode, onset if mode == "A3" else 0, rng)
    return [{"menit": i, "temp": round(temp[i] * 100), "temp_ok": 1, "rh": round(rh[i] * 100),
             "amb": round(amb[i] * 100), "solar": round(solar[i] * 16), "speed": KECEPATAN,
             "door": int(pintu[i]), "reefer": int(reefer[i]), "duty": round(float(duty[i]) * 10000), "harsh": 0}
            for i in range(n)]


def tulis(path: Path, baris: list[dict], meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("# " + " ".join(f"{k}={v}" for k, v in meta.items()) + "\n")
        f.write(",".join(KOLOM) + "\n")
        f.writelines(",".join(str(r[k]) for k in KOLOM) + "\n" for r in baris)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--nama", choices=NAMA)
    ap.add_argument("--semua", action="store_true")
    ap.add_argument("--menit", type=int, default=180)
    ap.add_argument("--profil", default="vaksin_2_8C")
    ap.add_argument("--jam-mulai", type=float, default=9.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--keluar", type=Path, default=KELUAR)
    a = ap.parse_args()
    if not (a.nama or a.semua):
        ap.error("pilih --nama atau --semua")
    for nama in NAMA if a.semua else [a.nama]:
        baris = bangun(nama, a.menit, a.profil, a.jam_mulai, a.seed)
        meta = {"nama": nama, "profil": a.profil, "jam_mulai": a.jam_mulai, "seed": a.seed, "sumber": "SIM"}
        tulis(a.keluar / f"{nama}.csv", baris, meta)
        suhu = [r["temp"] / 100 for r in baris]
        print(f"{nama:22s} {len(baris)} menit, suhu {min(suhu):.1f}..{max(suhu):.1f} C -> {a.keluar / (nama + '.csv')}")


if __name__ == "__main__":
    main()
