"""Sapuan ambang "suhu mendekati batas" mesin fisika (engine.CFG margin_waspada_frac) di split VAL v4.

  python -m eval.margin_sweep_val            (dari root repo, PYTHONPATH=backend:.)

Tujuan: usulan ambang untuk menurunkan alarm pada trip normal tanpa menambah breach yang terlewat.
Keputusan memakai VAL (aturan proyek). Sapuan lama eval/results/margin_sweep_iter2.json dihitung di split
TEST (eval.common.load_test_trips) dan tidak dipakai untuk keputusan ini.

KRITERIA (ditetapkan sebelum hasil dilihat, 2026-10-11):
  usulan = margin dengan alarm palsu per menit normal TERENDAH yang breach terlewat (trip, lead < 10 menit)
  TIDAK LEBIH BANYAK dari margin sekarang (0,35). Bila tidak ada, tetap 0,35. Tidak diterapkan otomatis.

Metrik (status mesin fisika per menit; hanya menit >= 59 = saat dasbor menampilkan status, dan menit tanpa
celah di 60 bacaan terakhir, sama dengan seleksi eval):
  alarm_palsu_per_menit_normal  fraksi menit trip NORMAL (failure_mode A0 di SEMUA menit trip) berstatus bukan AMAN
  alarm_per_menit_label_A0      pembanding, definisi eval: menit berlabel A0, termasuk menit sebelum onset di trip
                                yang kemudian gagal (failure_mode v4 berubah per menit setelah onset)
  episode_alarm_per_jam_normal  transisi AMAN -> bukan AMAN per jam trip normal (= pembuka insiden di dasbor)
  breach_terlewat_lead_lt10     trip val dengan breach (menit breach >= 70) yang peringatannya < 10 menit
                                sebelum breach (lead = panjang rangkaian bukan-AMAN yang berakhir di menit breach-1)
  breach_tanpa_peringatan       lead = 0 (menit breach-1 berstatus AMAN)
  urgent_aman                   menit dengan TTB asli <= 30 yang tampil AMAN (definisi eval)
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]

from app.core import engine  # noqa: E402
from app.inference import cargo_params, readings_to_trip  # noqa: E402
from eval.common import CARGO_TO_PROFILE, DATA_PATH, SENTINEL, trip_readings  # noqa: E402

FRACS = (0.15, 0.20, 0.25, 0.30, 0.35, 0.40)
SEKARANG = 0.35
W = 60
LEAD_MIN = 10
OUT = ROOT / "eval" / "results" / "margin_sweep_val.json"


def muat_val() -> dict[int, pd.DataFrame]:
    df = pd.read_parquet(DATA_PATH)
    df = df[df["split"] == "val"]
    return {tid: g.sort_values("minute").reset_index(drop=True) for tid, g in df.groupby("trip_id")}


def siapkan(trips):
    """Input engine per trip (tidak bergantung pada margin) + label."""
    out = []
    for tid, g in trips.items():
        prof = CARGO_TO_PROFILE[g["cargo_type"].iloc[0]]
        prod = cargo_params(prof, float(g["mass_kg"].iloc[0]) if "mass_kg" in g else None)
        trip = readings_to_trip(trip_readings(g), prod)
        temp = g["temp_c"].to_numpy()
        n = len(g)
        nan = np.isnan(temp)
        tanpa_celah = np.array([t >= W - 1 and not nan[t - W + 1:t + 1].any() for t in range(n)])
        ttb = g["time_to_breach"].to_numpy(float)
        breach = [t + ttb[t] for t in range(n) if ttb[t] != SENTINEL]
        mode_menit = g["failure_mode"].to_numpy()
        out.append({"tid": tid, "prof": prof, "prod": prod, "trip": trip,
                    "normal": bool((mode_menit == "A0").all()), "a0_menit": mode_menit == "A0",
                    "ok": tanpa_celah, "ttb": ttb, "breach_min": int(min(breach)) if breach else None})
    return out


def nilai(data, frac):
    keep = engine.CFG["margin_waspada_frac"]
    engine.CFG["margin_waspada_frac"] = frac
    try:
        normal_m = normal_alarm = normal_ep = 0
        a0_m = a0_alarm = 0
        per_prof: dict[str, list[int]] = {}
        leads, urgent_n, urgent_aman = [], 0, 0
        for d in data:
            st = engine.run(d["trip"], d["prod"], d["prod"]["mass_kg"]).status_txt.to_numpy()
            alarm = st != "AMAN"
            ok = d["ok"]
            urg = ok & (d["ttb"] != SENTINEL) & (d["ttb"] <= 30)
            urgent_n += int(urg.sum())
            urgent_aman += int((urg & ~alarm).sum())
            a0 = ok & d["a0_menit"]
            a0_m += int(a0.sum())
            a0_alarm += int((a0 & alarm).sum())
            if d["normal"]:
                m = int(ok.sum())
                a = int((alarm & ok).sum())
                normal_m += m
                normal_alarm += a
                p = per_prof.setdefault(d["prof"], [0, 0])
                p[0] += m
                p[1] += a
                tampil = np.arange(len(st)) >= W - 1
                normal_ep += int((alarm[1:] & ~alarm[:-1] & tampil[1:]).sum())
            b = d["breach_min"]
            if b is not None and b >= W + LEAD_MIN and b - 1 < len(st):
                lead, t = 0, b - 1
                while t >= W - 1 and alarm[t]:
                    lead += 1
                    t -= 1
                leads.append(lead)
        leads = np.array(leads)
        return {
            "frac": frac,
            "margin_2_4C_K": round(min(engine.CFG["margin_waspada_k"], frac * 2.0), 2),
            "margin_2_8C_K": round(min(engine.CFG["margin_waspada_k"], frac * 6.0), 2),
            "alarm_palsu_per_menit_normal": normal_alarm / normal_m,
            "episode_alarm_per_jam_normal": normal_ep / (normal_m / 60.0),
            "alarm_per_menit_label_A0": a0_alarm / a0_m,
            "alarm_palsu_per_profil": {k: v[1] / v[0] for k, v in sorted(per_prof.items())},
            "n_trip_breach_dinilai": int(len(leads)),
            "breach_terlewat_lead_lt10": int((leads < LEAD_MIN).sum()),
            "breach_tanpa_peringatan": int((leads == 0).sum()),
            "lead_median_menit": float(np.median(leads)) if len(leads) else None,
            "urgent_aman": urgent_aman / urgent_n if urgent_n else None,
            "n_menit_normal": normal_m,
            "n_menit_urgent": urgent_n,
        }
    finally:
        engine.CFG["margin_waspada_frac"] = keep


def main():
    t0 = time.time()
    trips = muat_val()
    data = siapkan(trips)
    hasil = [nilai(data, f) for f in FRACS]
    acuan = next(h for h in hasil if h["frac"] == SEKARANG)
    lolos = [h for h in hasil if h["breach_terlewat_lead_lt10"] <= acuan["breach_terlewat_lead_lt10"]]
    usulan = min(lolos, key=lambda h: h["alarm_palsu_per_menit_normal"])
    OUT.write_text(json.dumps({
        "split": "val", "data": DATA_PATH.name, "n_trip": len(trips),
        "n_trip_normal_A0": sum(d["normal"] for d in data),
        "n_trip_breach": sum(d["breach_min"] is not None for d in data),
        "kriteria": "alarm palsu terendah dengan breach_terlewat_lead_lt10 <= margin sekarang (0,35); ditetapkan sebelum hasil",
        "sekarang": SEKARANG, "usulan_frac": usulan["frac"], "diterapkan": False,
        "catatan": "Sapuan lama eval/results/margin_sweep_iter2.json memakai split TEST; tidak dipakai di sini.",
        "sapuan": hasil, "durasi_s": round(time.time() - t0, 1),
    }, indent=2), encoding="utf-8")
    for h in hasil:
        print(h["frac"], round(h["alarm_palsu_per_menit_normal"], 3), round(h["episode_alarm_per_jam_normal"], 2),
              h["breach_terlewat_lead_lt10"], h["breach_tanpa_peringatan"], "/", h["n_trip_breach_dinilai"],
              h["lead_median_menit"], round(h["urgent_aman"], 3))
    print("usulan", usulan["frac"], "->", OUT)


if __name__ == "__main__":
    main()
