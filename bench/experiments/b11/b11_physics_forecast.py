"""B11 -- apakah forecast suhu +15/30/60 menit bisa dihitung chip dengan fisika, tanpa GRU? Split VAL saja.

Target dan jendela sama dengan head forecast GRU (ml/preprocess/build_windows.py): suhu sensor temp_c[t + h],
jendela 60 menit tanpa NaN, t = menit terakhir jendela. Pembanding yang bisa dihitung chip dari register yang
sudah ada di hw/rtl/physics.sv (keluaran hw/golden/physics.py, dihitung float dari nilai bulat chip):
  persistensi   suhu sekarang (batas bawah yang harus dikalahkan siapa pun)
  fisika_tc     taksiran suhu muatan diproyeksikan ke kabin: Tc + (kabin - Tc) (1 - e^-kT), kabin = aturan TTB
  fisika_kabin  rata-rata 10 menit (ts10) sebagai kabin yang bertahan
  tren20        ts10 + T x kemiringan 20 menit (sinyal "hanyut" mesin fisika)
GRU v3 (backend/models/coldtrack_v3.onnx) dijalankan pada jendela yang sama.

  python -m bench.experiments.b11.b11_physics_forecast
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

H = [15, 30, 60]
W = 60
OUT = ROOT / "bench/results/local-cpu/B11/physics_forecast.json"


def fisika_trip(g, prod):
    """Keluaran golden per menit -> array float (tc, ts10, kabin, slope20, e^-k)."""
    from hw.golden import physics as fx
    from hw.golden import trees as ph

    cfg = fx.konfigurasi(prod["t_lo"], prod["t_hi"], prod["t_set"], prod["c"], prod["mass_kg"])
    m = fx.MesinFisika(cfg)
    q = ph.kuantisasi_trip(g)
    n = len(g)
    tc, ts10 = np.zeros(n), np.zeros(n)
    for t in range(n):
        o = m.langkah(-32768 if q["nan"][t] else int(q["temp"][t]), int(q["amb"][t]), bool(q["door"][t]),
                      int(q["speed"][t]) >= 100)
        tc[t], ts10[t] = o["tc"] / 2**16 / 100, o["ts10"] / 2**16 / 100
    amb, door = q["amb"] / 100, q["door"].astype(bool)
    moving = q["speed"] >= 100
    clean = pd.Series(np.where(q["nan"], np.nan, q["temp"] / 100)).ffill().bfill().to_numpy()
    naik5 = np.r_[np.zeros(5, bool), (clean[5:] - clean[:-5]) > fx.SLOPE5 / 100]
    panas = door | (~moving & naik5)
    kabin = np.where(panas & (amb > ts10), amb, ts10)
    slope = np.r_[np.zeros(20), (ts10[20:] - ts10[:-20]) / 20]
    return tc, ts10, kabin, slope, cfg["ek"] / 2**40


def main():
    import onnxruntime as ort
    from app.inference import cargo_params

    from eval.common import CARGO_TO_PROFILE
    from ml.preprocess.build_windows import (
        FEATURE_COLUMNS,
        hitung_ulang_reefer_duration,
    )

    t0 = time.perf_counter()
    df = pd.read_parquet(ROOT / "data/processed/v4_seed1000_700trips.parquet")
    val = df[df.split == "val"]
    sess = ort.InferenceSession(str(ROOT / "backend/models/coldtrack_v3.onnx"), providers=["CPUExecutionProvider"])
    kolom = ["persistensi", "fisika_tc", "fisika_kabin", "tren20", "gru"]
    err = {k: [] for k in kolom}
    mode_list = []
    for tid, g in val.groupby("trip_id"):
        g = g.sort_values("minute").reset_index(drop=True)
        n = len(g)
        if n - W - max(H) < 0:
            continue
        prod = cargo_params(CARGO_TO_PROFILE[g.cargo_type.iloc[0]], None)
        tc, ts10, kabin, slope, ek = fisika_trip(g, prod)
        feats = g[FEATURE_COLUMNS].to_numpy(np.float32)
        temp = g["temp_c"].to_numpy(float)
        mode = next((x for x in pd.unique(g["failure_mode"]) if x != "A0"), "A0")
        xs, ts = [], []
        for start in range(n - W - max(H) + 1):
            t = start + W - 1
            win = hitung_ulang_reefer_duration(feats[start:start + W])
            y = temp[[t + h for h in H]]
            if np.isnan(win).any() or np.isnan(y).any():
                continue
            xs.append(win)
            ts.append(t)
        if not ts:
            continue
        ts = np.array(ts)
        y = np.stack([temp[ts + h] for h in H], 1)
        pT = np.array([ek ** h for h in H])[None, :]
        pred = {
            "persistensi": np.repeat(temp[ts][:, None], 3, 1),
            "fisika_tc": tc[ts][:, None] + (kabin[ts][:, None] - tc[ts][:, None]) * (1 - pT),
            "fisika_kabin": np.repeat(ts10[ts][:, None], 3, 1),
            "tren20": ts10[ts][:, None] + slope[ts][:, None] * np.array(H)[None, :],
        }
        fc = np.concatenate([sess.run(None, {"window": np.stack(xs[i:i + 2048]).astype(np.float32)})[0]
                             for i in range(0, len(xs), 2048)])
        pred["gru"] = fc
        for k in kolom:
            err[k].append(np.abs(pred[k] - y))
        mode_list += [mode] * len(ts)
    mode_arr = np.array(mode_list)
    hasil = {"split": "val", "n_jendela": len(mode_arr), "target": "temp_c[t+h], jendela build_windows",
             "mae_c": {}, "mae_per_mode_t30": {}}
    for k in kolom:
        e = np.concatenate(err[k])
        hasil["mae_c"][k] = {f"t{h}": round(float(e[:, i].mean()), 4) for i, h in enumerate(H)}
        hasil["mae_per_mode_t30"][k] = {m: round(float(e[mode_arr == m, 1].mean()), 4) for m in sorted(set(mode_list))}
    hasil["waktu_s"] = round(time.perf_counter() - t0, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(hasil, indent=2) + "\n")
    print(json.dumps(hasil["mae_c"], indent=1))


if __name__ == "__main__":
    main()
