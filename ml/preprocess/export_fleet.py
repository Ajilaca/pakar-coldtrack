"""Fase 1 armada -- seed 24 truk virtual dari dataset v4 + depo, perangkat, dan rute SINTETIK.

Menjalankan: python -m ml.preprocess.export_fleet

- Trip diambil dari split VAL v4 (bukan latih: demo tidak boleh memamerkan data yang pernah dilihat
  model; bukan test: split test disisihkan untuk evaluasi). Stratifikasi ~60 % A0, lalu setiap mode
  anomali A1-A8 minimal satu trip.
- v4 tidak punya lat/lon, massa muatan, nilai muatan, atau data perangkat. Semuanya dibangkitkan di
  sini dan DITANDAI sintetik / [ASUMSI] (docs/fleet_assumptions.md). Rute = garis lurus antar hub
  dengan sedikit jitter, seperti ml/preprocess/export_demo_scenarios.py.

Keluaran (backend/data/fleet/): telemetry.parquet, trucks.json, devices.json, depots.json, trips.json
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "processed" / "v4_seed1000_700trips.parquet"
OUT = ROOT / "backend" / "data" / "fleet"
SEED = 2026
N_TRUK = 24
N_A0 = 14

# 6 hub di Jawa [ASUMSI: koordinat pusat kota, bukan alamat depo nyata]
DEPOTS = [
    {"id": "JKT", "name": "Depo Jakarta", "city": "Jakarta", "lat": -6.2088, "lon": 106.8456, "plat": "B"},
    {"id": "BDG", "name": "Depo Bandung", "city": "Bandung", "lat": -6.9175, "lon": 107.6191, "plat": "D"},
    {"id": "CRB", "name": "Depo Cirebon", "city": "Cirebon", "lat": -6.7320, "lon": 108.5523, "plat": "E"},
    {"id": "SMG", "name": "Depo Semarang", "city": "Semarang", "lat": -6.9667, "lon": 110.4167, "plat": "H"},
    {"id": "YGY", "name": "Depo Yogyakarta", "city": "Yogyakarta", "lat": -7.7956, "lon": 110.3695, "plat": "AB"},
    {"id": "SBY", "name": "Depo Surabaya", "city": "Surabaya", "lat": -7.2575, "lon": 112.7521, "plat": "L"},
]
# parquet cargo_type -> backend/config.yaml cargo_profiles (sama dengan eval/common.py)
CARGO_TO_PROFILE = {
    "vaksin_2_8C": "vaksin_2_8C",
    "daging_beku": "daging_beku_-18C",
    "sayur_buah": "buah_segar_2_4C",
    "ikan_segar": "ikan_segar_0_5C",
    "produk_susu": "produk_susu_2_4C",
}
FIRMWARE_TERBARU, GATEWAY_TERBARU = "1.5.0", "0.9.3"
KOLOM_BACAAN = ["temp_c", "humidity", "ambient_c", "door_open", "reefer_on", "speed_kmh", "harsh_events",
                "solar_radiation"]


def pilih_trip(df, rng):
    g = df.groupby("trip_id").agg(mode=("failure_mode", "last"), n=("minute", "size"))
    pilih = list(rng.choice(g.index[g["mode"] == "A0"], N_A0, replace=False))
    for m in ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"]:
        pilih.append(int(rng.choice(g.index[g["mode"] == m])))
    sisa = g.index[(g["mode"] != "A0") & ~g.index.isin(pilih)]
    pilih += list(rng.choice(sisa, N_TRUK - len(pilih), replace=False))
    return [int(t) for t in pilih]


def plat(rng, prefix, terpakai):
    while True:
        p = f"{prefix} {rng.integers(1000, 9999)} {''.join(rng.choice(list('ABCDEFGHJKLMNPRSTUVWXYZ'), 2))}"
        if p not in terpakai:
            terpakai.add(p)
            return p


def main():
    rng = np.random.default_rng(SEED)
    df = pd.read_parquet(DATA_PATH)
    df = df[df["split"] == "val"]
    trips_v4 = pilih_trip(df, rng)
    terpakai, trucks, devices, trips, parts = set(), [], [], [], []
    for k, tid in enumerate(trips_v4):
        g = df[df["trip_id"] == tid].sort_values("minute").reset_index(drop=True)
        asal = DEPOTS[k % len(DEPOTS)]
        tujuan = DEPOTS[(k + 1 + int(rng.integers(0, len(DEPOTS) - 1))) % len(DEPOTS)]
        truck_id = plat(rng, asal["plat"], terpakai)
        n = len(g)
        jitter = rng.normal(0, 0.004, size=(n, 2)).cumsum(0) * 0.05
        lat = np.linspace(asal["lat"], tujuan["lat"], n) + jitter[:, 0]
        lon = np.linspace(asal["lon"], tujuan["lon"], n) + jitter[:, 1]
        profil = CARGO_TO_PROFILE[g["cargo_type"].iloc[0]]
        mass = float(rng.choice([600, 800, 1000, 1200, 1500]))
        t = pd.DataFrame({"truck_id": truck_id, "minute": g["minute"], "lat": lat.round(6), "lon": lon.round(6)})
        for c in KOLOM_BACAAN:
            t[c] = g[c].to_numpy()
        t["sumber_trip_v4"] = tid
        parts.append(t)
        trucks.append({"id": truck_id, "depot_id": asal["id"], "label": f"Truk {k + 1:02d}"})
        tua = rng.random() < 0.3
        devices.append({
            "id": f"DEV-{k + 1:03d}", "truck_id": truck_id,
            "firmware": "1.4.2" if tua else FIRMWARE_TERBARU,
            "gateway_version": "0.8.7" if rng.random() < 0.15 else GATEWAY_TERBARU,
            "calibrated_at": str((pd.Timestamp("2026-10-01") - pd.Timedelta(days=int(rng.integers(10, 400)))).date()),
            "calibration_offset_c": round(float(rng.normal(0, 0.25)), 2),
            "battery_v": round(float(rng.uniform(2.35, 3.1)), 2),
            "sumber": "sintetik",
        })
        trips.append({
            "truck_id": truck_id, "cargo_profile": profil, "mass_kg": mass, "depot_id": asal["id"],
            "tujuan_depot_id": tujuan["id"], "sumber_trip_v4": tid, "failure_mode_v4": g["failure_mode"].iloc[-1],
            "n_menit": n, "sumber": "v4 split val; massa sintetik; nilai muatan dihitung dari harga per kg [ASUMSI]",
        })
    OUT.mkdir(parents=True, exist_ok=True)
    pd.concat(parts, ignore_index=True).to_parquet(OUT / "telemetry.parquet", index=False)
    for nama, isi in [("trucks", trucks), ("devices", devices), ("trips", trips),
                      ("depots", [{k: v for k, v in d.items() if k != "plat"} for d in DEPOTS])]:
        (OUT / f"{nama}.json").write_text(json.dumps(isi, indent=2, ensure_ascii=False), encoding="utf-8")
    modes = pd.Series([t["failure_mode_v4"] for t in trips]).value_counts().to_dict()
    print(f"{len(trucks)} truk, {sum(t['n_menit'] for t in trips)} bacaan, mode: {modes} -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
