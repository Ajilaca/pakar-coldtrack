"""Paritas golden model fixed-point (hw/golden/physics.py) terhadap backend/app/core/engine.py (float).

Data: 5 skenario demo + trip train/val dataset v4 (split test tidak dipakai). Celah suhu (NaN) diisi
nilai terakhir lebih dulu, seperti jalur armada (fleet.ffill_maks_menit), untuk kedua mesin.
  A  engine.py menerima suhu float asli, golden menerima satuan 0,01 C (kondisi nyata)
  B  keduanya menerima suhu yang sama yang sudah dikuantisasi 0,01 C (selisih murni aritmetika)

  python -m hw.golden.check_physics            -> hw/results/parity_physics.json
"""

import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.core import engine
from app.inference import cargo_params

from eval.common import CARGO_TO_PROFILE
from hw.golden import physics as fx

KODE = [("Kondisi normal", 0), ("Suhu muatan di luar", 1), ("Muatan diperkirakan", 2), ("Suhu mendekati", 3),
        ("Pintu terbuka", 4), ("Sensor rusak", 5), ("Sensor mencurigakan", 6)]


def kode_alasan(teks):
    return next(k for p, k in KODE if teks.startswith(p))


def bandingkan(ts, amb, door, moving, prod):
    """ts, amb float (tanpa NaN). Kembalikan dict array per menit untuk float dan fixed."""
    tel = pd.DataFrame({"T_sensor": ts, "T_amb": amb, "door_open": door.astype(float),
                        "moving": moving.astype(float)})
    e = engine.run(tel, prod, prod["mass_kg"])
    cfg = fx.konfigurasi(prod["t_lo"], prod["t_hi"], prod["t_set"], prod["c"], prod["mass_kg"])
    m = fx.MesinFisika(cfg)
    g = [m.langkah(fx.q(a), fx.q(b), bool(d), bool(v)) for a, b, d, v in zip(ts, amb, door, moving)]
    ttb_f = [None if (pd.isna(x) or x > fx.TTB_TAMPIL) else math.ceil(round(x, 9)) for x in e.ttb_show]
    return {
        "status_f": e.status.to_numpy(), "status_g": np.array([o["status"] for o in g]),
        "alasan_f": np.array([kode_alasan(r) for r in e.reason]), "alasan_g": np.array([o["alasan"] for o in g]),
        "sensor_f": e.sensor_status.to_numpy(), "sensor_g": np.array([o["sensor"] for o in g]),
        "ttb_f": ttb_f, "ttb_g": [o["ttb"] for o in g],
        "seri": np.array([o["seri"] for o in g]),
        "tc_err": np.abs(e.T_cargo_est.to_numpy() - np.array([o["tc"] for o in g]) / (fx.Q << fx.SH)),
    }


def ringkas(hasil):
    sf = np.concatenate([h["status_f"] for h in hasil])
    sg = np.concatenate([h["status_g"] for h in hasil])
    tf = [x for h in hasil for x in h["ttb_f"]]
    tg = [x for h in hasil for x in h["ttb_g"]]
    ttb_sama = sum(a == b for a, b in zip(tf, tg))
    ttb_dekat = sum((a is None and b is None) or (a is not None and b is not None and abs(a - b) <= 1)
                    for a, b in zip(tf, tg))
    beda = Counter(f"{fx_}->{g_}" for fx_, g_ in zip(sf, sg) if fx_ != g_)
    seri = np.concatenate([h["seri"] for h in hasil])
    return {
        "menit": len(sf),
        "status_sama": float((sf == sg).mean()),
        "status_beda": dict(beda),
        "status_fixed_lebih_rendah": int((sg < sf).sum()),
        "status_beda_di_menit_seri": int(((sf != sg) & seri).sum()),
        "status_beda_bukan_seri": int(((sf != sg) & ~seri).sum()),
        "menit_seri": int(seri.sum()),
        "kritis_float_tapi_aman_fixed": int(((sf == 2) & (sg == 0)).sum()),
        "alasan_sama": float((np.concatenate([h["alasan_f"] for h in hasil])
                              == np.concatenate([h["alasan_g"] for h in hasil])).mean()),
        "sensor_sama": float((np.concatenate([h["sensor_f"] for h in hasil])
                              == np.concatenate([h["sensor_g"] for h in hasil])).mean()),
        "ttb_tampil_sama": ttb_sama / len(tf),
        "ttb_tampil_selisih_maks_1": ttb_dekat / len(tf),
        "tc_galat_maks_c": float(max(h["tc_err"].max() for h in hasil)),
    }


def sumber():
    for p in sorted((ROOT / "backend/data/scenarios").glob("*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        r = pd.DataFrame(s["readings"])
        yield "skenario", p.stem, r.temp_c.to_numpy(float), r.ambient_c.to_numpy(float), \
            r.door_open.to_numpy(bool), (r.speed_kmh >= 1.0).to_numpy(), cargo_params(s["cargo_profile"], None)
    df = pd.read_parquet(ROOT / "data/processed/v4_seed1000_700trips.parquet")
    for tid, g in df[df.split.isin(["train", "val"])].groupby("trip_id"):
        g = g.sort_values("minute")
        ts = g.temp_c.ffill().bfill().to_numpy(float)
        yield "trip", int(tid), ts, g.ambient_c.to_numpy(float), (g.door_open >= 0.5).to_numpy(), \
            (g.speed_kmh >= 1.0).to_numpy(), cargo_params(CARGO_TO_PROFILE[g.cargo_type.iloc[0]], None)


def main():
    t0 = time.perf_counter()
    A, B, contoh = [], [], []
    for jenis, nama, ts, amb, door, mov, prod in sumber():
        A.append(bandingkan(ts, amb, door, mov, prod))
        tq, aq = np.round(ts * fx.Q) / fx.Q, np.round(amb * fx.Q) / fx.Q
        B.append(bandingkan(tq, aq, door, mov, prod))
        if jenis == "skenario":
            contoh.append({"skenario": nama, "status_akhir_float": int(A[-1]["status_f"][-1]),
                           "status_akhir_fixed": int(A[-1]["status_g"][-1]),
                           "status_sama": float((A[-1]["status_f"] == A[-1]["status_g"]).mean())})
    hasil = {"A_float_asli_vs_fixed": ringkas(A), "B_input_sama_terkuantisasi": ringkas(B), "skenario": contoh,
             "jumlah_trip": len(A) - len(contoh), "detik": time.perf_counter() - t0}
    out = ROOT / "hw/results/parity_physics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(hasil, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(hasil, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
