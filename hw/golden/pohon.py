"""Model acuan fitur bilangan bulat dan inferensi tree ensemble (RTL: hw/rtl/tree_engine.sv, fitur.sv).

Masukan per menit = kolom rekaman tersegel (hw/golden/segel.py), dalam satuan bilangan bulat SKALA:
temp/ambient/humidity/speed 0,01, solar 1/16 W/m2, duty 1/10000, sisanya bilangan bulat. Satuan desimal
membuat kelipatan 0,1 C data simulator eksak (ambang pohon sering tepat di nilai data).

Fitur (urutan = bench/b10_test_once.fitur):
  0..71   6 statistik x 12 kolom jendela 60 menit (ml.baselines.aggregate):
          rata-rata -> JUMLAH, simpangan baku -> V = 60*sum(x^2) - (sum x)^2, min, maks, terakhir, tren
  72..75  konteks: menit_trip, tren_240, rata240_minus_rata60 dan kemiringan_240 (0,01 C x 2^24)
  76..81  6 statistik siklus kerja kompresor (hanya model b9)

Ambang pohon (float32) dikonversi EKSAK ke domain bilangan bulat fitur dengan Fraction, sehingga
"x < ambang" di float sama dengan "v < ambang_int" di chip untuk masukan yang sama; perbedaan hanya
dari kuantisasi masukan. Nilai daun dan base_score: Q8.16 bertanda; skor kelas = jumlah; hasil = argmax.
"""

import json
from fractions import Fraction
from pathlib import Path

import numpy as np

KOLOM = ["temp_c", "delta_temp", "ambient_c", "delta_ambient", "solar_radiation", "humidity", "door_open",
         "reefer_on", "reefer_duration_min", "speed_kmh", "harsh_events", "hour_of_day"]
SKALA = {"temp_c": 100, "delta_temp": 100, "ambient_c": 100, "delta_ambient": 100, "solar_radiation": 16,
         "humidity": 100, "door_open": 1, "reefer_on": 1, "reefer_duration_min": 1, "speed_kmh": 100,
         "harsh_events": 1, "hour_of_day": 1}
SKALA_DUTY = 10000
N = 60
Q24 = 1 << 24
FRAK_DAUN = 16
STAT = ["sum", "var", "min", "max", "last", "trend"]


def jenis_fitur(pakai_duty):
    j = [(s, SKALA[k]) for s in STAT for k in KOLOM]
    j += [("plain", 1), ("plain", 100), ("plain", 100 * Q24), ("plain", 100 * Q24)]
    if pakai_duty:
        j += [(s, SKALA_DUTY) for s in STAT]
    return j


def ambang_int(thr_f32, jenis):
    """Bilangan bulat T sehingga (fitur_float < thr) <=> (v < T), untuk v hasil fitur_bulat."""
    s, sk = jenis
    t = Fraction(float(np.float32(thr_f32)))
    if s == "sum":
        x = t * N * sk
    elif s == "var":
        if t <= 0:
            return 0                      # simpangan >= 0, "x < thr" tidak pernah benar; v >= 0
        x = (t * N * sk) ** 2
    else:
        x = t * sk
    return -((-x.numerator) // x.denominator)        # ceil


def kuantisasi_trip(g, duty=None):
    """DataFrame satu trip (urut menit, kolom dataset v4) -> dict array int per menit (tanpa NaN pada temp)."""
    temp = g["temp_c"].to_numpy(float)
    out = {
        "temp": np.round(np.nan_to_num(temp) * 100).astype(np.int64),     # celah ditandai di "nan"
        "amb": np.round(g["ambient_c"].to_numpy(float) * 100).astype(np.int64),
        "solar": np.round(g["solar_radiation"].to_numpy(float) * 16).astype(np.int64),
        "rh": np.round(g["humidity"].to_numpy(float) * 100).astype(np.int64),
        "door": (g["door_open"].to_numpy(float) >= 0.5).astype(np.int64),
        "reefer": (g["reefer_on"].to_numpy(float) >= 0.5).astype(np.int64),
        "speed": np.round(g["speed_kmh"].to_numpy(float) * 100).astype(np.int64),
        "harsh": g["harsh_events"].to_numpy(float).astype(np.int64),
        "hour": g["hour_of_day"].to_numpy(float).astype(np.int64),
        "nan": np.isnan(temp),
    }
    if duty is not None:
        out["duty"] = np.round(np.asarray(duty, float) * SKALA_DUTY).astype(np.int64)
    return out


def _stat(v):
    v = [int(x) for x in v]
    s = sum(v)
    return [s, N * sum(x * x for x in v) - s * s, min(v), max(v), v[-1], v[-1] - v[0]]


def fitur_bulat(q, t, pakai_duty):
    """Fitur bilangan bulat untuk jendela yang berakhir di menit t (t >= 59, tanpa NaN di jendela)."""
    a = t - N + 1
    temp = q["temp"]
    tw = temp[a:t + 1]
    prev = temp[a - 1] if a > 0 else temp[a]
    dtemp = np.diff(np.concatenate([[prev], tw]))
    rdur, run = [], 0
    for r in q["reefer"][a:t + 1]:
        run = run + 1 if r else 0
        rdur.append(run)
    kolom = [tw, dtemp, q["amb"][a:t + 1], tw - q["amb"][a:t + 1], q["solar"][a:t + 1], q["rh"][a:t + 1],
             q["door"][a:t + 1], q["reefer"][a:t + 1], rdur, q["speed"][a:t + 1], q["harsh"][a:t + 1],
             q["hour"][a:t + 1]]
    st = [_stat(c) for c in kolom]
    f = [st[k][si] for si in range(6) for k in range(12)]

    y = q["temp_ff"]
    lo = max(0, t - 239)
    m = t - lo + 1
    yy = [int(x) for x in y[lo:t + 1]]
    s240, s60 = sum(yy), sum(yy[-60:])
    # pembagian floor eksak (RTL: satu pembagi iteratif)
    rata = ((60 * s240 - m * s60) << 24) // (60 * m)
    sxy = sum(p * v for p, v in enumerate(yy))
    num = m * sxy - (m * (m - 1) // 2) * s240
    slope = ((12 * num) << 24) // (m * m * (m * m - 1)) if m >= 2 else 0     # m*Sxx - Sx^2 = m^2(m^2-1)/12
    f += [t, yy[-1] - yy[0], rata, slope]
    if pakai_duty:
        f += _stat(q["duty"][a:t + 1])
    return f


def ffill_temp(q, t_set=0):
    temp = q["temp"].copy()
    ok = ~q["nan"]
    if not ok.any():
        q["temp_ff"] = np.full(len(temp), t_set)
        return q
    idx = np.where(ok, np.arange(len(temp)), 0)
    np.maximum.accumulate(idx, out=idx)
    temp = temp[idx]
    temp[:np.argmax(ok)] = temp[np.argmax(ok)]
    q["temp_ff"] = temp
    return q


def muat_model(path, pakai_duty):
    """JSON XGBoost -> daftar pohon {kelas, simpul}: simpul daun (None, None, nilai) atau (fitur, T_int, kiri, kanan)."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))["learner"]
    base = [round(float(x) * (1 << FRAK_DAUN)) for x in json.loads(d["learner_model_param"]["base_score"])]
    model = d["gradient_booster"]["model"]
    jenis = jenis_fitur(pakai_duty)
    pohon = []
    for kls, t in zip(model["tree_info"], model["trees"]):
        simpul = []
        for i in range(len(t["left_children"])):
            if t["left_children"][i] == -1:
                simpul.append(("daun", round(float(np.float32(t["split_conditions"][i])) * (1 << FRAK_DAUN))))
            else:
                fi = t["split_indices"][i]
                simpul.append(("cabang", fi, ambang_int(t["split_conditions"][i], jenis[fi]),
                               t["left_children"][i], t["right_children"][i]))
        pohon.append({"kelas": kls, "simpul": simpul})
    return {"base": base, "pohon": pohon, "n_kelas": len(base)}


def skor_bulat(m, f):
    skor = list(m["base"])
    for p in m["pohon"]:
        i = 0
        while p["simpul"][i][0] == "cabang":
            _, fi, thr, ki, ka = p["simpul"][i]
            i = ki if f[fi] < thr else ka
        skor[p["kelas"]] += p["simpul"][i][1]
    return skor


def kelas_bulat(m, f):
    s = skor_bulat(m, f)
    return max(range(len(s)), key=lambda k: (s[k], -k))
