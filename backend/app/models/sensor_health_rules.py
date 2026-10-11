"""Kesehatan sensor v0: aturan, skor 0-100 dari bacaan asli 3 jam terakhir (CONTEXT_FLEET_SCALEUP.md Fase 3).

Penalti (semua bobot [DESAIN], belum dikalibrasi terhadap kerusakan nyata; model Berkeley = Fase 8):
  status sensor per menit (app/core/sensor_rules.py)  50 x fraksi "rusak" + 20 x fraksi "curiga"
  rangkaian datar terpanjang                          >= 35 menit: 10 (Intel: datar sehat p99 ~34 menit)
                                                      >= 60 menit: 30 (FLAT_SURE_MIN)
  derau (std selisih orde-2 / sqrt 6, pintu tertutup) > 2x baseline Intel 0,073 C: 10;  > 4x: 20
  lompatan > 5 C antar menit (pintu tertutup)         10 per lompatan, maks 20
  baterai (devices.battery_v)                         < 2,6 V: 10 (waspada);  < 2,4 V: 30 (kritis)
Grade: >= 80 Sehat, >= 50 Perlu cek, < 50 Ganti. < 30 bacaan dalam 3 jam: "Data kurang" (tanpa skor).

Catatan data seed: suhu terkuantisasi 0,1 C; derau truk sehat di seed ~0,04 C (di bawah baseline Intel).
"""

from itertools import pairwise
from typing import Any, ClassVar

import numpy as np

from app.core import sensor_rules as sr
from app.models.base import Konteks, Provider

NOISE_BASELINE_C = 0.073
MIN_BACAAN = 30


def _datar_terpanjang(t: np.ndarray) -> int:
    best = run = 0
    for a, b in pairwise(t):
        run = run + 1 if a == b else 0
        best = max(best, run)
    return best


def _derau(t: np.ndarray, pintu: np.ndarray) -> float | None:
    d2 = t[2:] - 2 * t[1:-1] + t[:-2]
    ok = ~np.isnan(d2) & (pintu[2:] < 0.5) & (pintu[1:-1] < 0.5) & (np.abs(d2) < 2)
    return float(d2[ok].std() / np.sqrt(6)) if ok.sum() >= 10 else None


def nilai(t: np.ndarray, pintu: np.ndarray, t_amb: np.ndarray, speed: np.ndarray,
          battery_v: float | None) -> dict[str, Any]:
    alasan, komponen = [], {}
    pen = 0.0
    if battery_v is not None:
        if battery_v < 2.4:
            pen += 30
            alasan.append(f"Baterai kritis {battery_v:.2f} V (< 2,4 V).")
        elif battery_v < 2.6:
            pen += 10
            alasan.append(f"Baterai rendah {battery_v:.2f} V (< 2,6 V).")
    komponen["battery_v"] = battery_v
    if len(t) < MIN_BACAAN:
        return {"score": None, "grade": "Data kurang", "alasan": [*alasan, f"Hanya {len(t)} bacaan dalam 3 jam."],
                "komponen": komponen}

    st = sr.sensor_status(t, pintu > 0.5, t_amb, moving=(speed >= 1.0).astype(float))
    f_rusak, f_curiga = float((st == 2).mean()), float((st == 1).mean())
    pen += 50 * f_rusak + 20 * f_curiga
    if f_rusak:
        alasan.append(f"{f_rusak:.0%} menit terbaca rusak (di luar rentang/datar lama).")
    if f_curiga:
        alasan.append(f"{f_curiga:.0%} menit terbaca mencurigakan.")
    datar = _datar_terpanjang(t)
    if datar >= sr.FLAT_SURE_MIN:
        pen += 30
        alasan.append(f"Suhu datar {datar} menit berturut-turut.")
    elif datar >= 35:
        pen += 10
        alasan.append(f"Suhu datar {datar} menit (di atas p99 sensor sehat).")
    derau = _derau(t, pintu)
    if derau is not None and derau > 4 * NOISE_BASELINE_C:
        pen += 20
        alasan.append(f"Derau tinggi {derau:.3f} C (> 4x baseline).")
    elif derau is not None and derau > 2 * NOISE_BASELINE_C:
        pen += 10
        alasan.append(f"Derau {derau:.3f} C (> 2x baseline).")
    dt = np.diff(t)
    lompat = int(((np.abs(dt) > sr.JUMP_C) & (pintu[1:] < 0.5) & (pintu[:-1] < 0.5)).sum())
    if lompat:
        pen += min(20, 10 * lompat)
        alasan.append(f"{lompat} lompatan suhu > {sr.JUMP_C:.0f} C antar menit.")
    komponen.update(frac_rusak=round(f_rusak, 3), frac_curiga=round(f_curiga, 3), datar_maks_menit=datar,
                    derau_c=None if derau is None else round(derau, 4), lompatan=lompat, n_bacaan=len(t))
    score = round(max(0.0, 100.0 - pen))
    grade = "Sehat" if score >= 80 else "Perlu cek" if score >= 50 else "Ganti"
    return {"score": score, "grade": grade, "alasan": alasan or ["Tidak ada tanda kerusakan."], "komponen": komponen}


class SensorHealthRulesV0(Provider):
    name: ClassVar[str] = "rules_v0"
    version: ClassVar[str] = "sensor-health-rules-v0"
    kind: ClassVar[str] = "sensor_health"

    def run(self, ctx: Konteks) -> dict[str, Any]:
        r = ctx.raw
        batt = None if not ctx.device or ctx.device.get("battery_v") is None else float(ctx.device["battery_v"])
        if r.empty:
            return nilai(np.array([]), np.array([]), np.array([]), np.array([]), batt)
        r = r.sort_values("ts")
        return nilai(r.temp_c.to_numpy(float), r.door_open.to_numpy(float), r.ambient_c.to_numpy(float),
                     r.speed_kmh.to_numpy(float), batt)

    def card(self) -> dict[str, Any]:
        return {**super().card(), "jenis": "aturan", "bobot": "[DESAIN], belum dikalibrasi",
                "keterbatasan": "Ambang dari data Intel Berkeley (lab), bukan logger truk; lihat Fase 8."}
