"""Muat data Intel Berkeley Lab, resample per menit per mote, dan tentukan kejadian kegagalan.

Kegagalan (G4_kriteria.json): pembacaan ekstrem pertama (nilai 122,15 C; ml/CHECKPOINT2_CONTEXT.md
§8: ~91 % bacaan ekstrem tepat bernilai ini, hanya saat tegangan < 2,4 V) ATAU mote mati (berhenti
mengirim lebih dari H jam sebelum akhir data). Waktu kegagalan = yang lebih dulu.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "berkeley"
KOLOM = ["date", "time", "epoch", "moteid", "temperature", "humidity", "light", "voltage"]
MOTE_VALID = range(1, 55)            # 54 mote di denah lab; id lain (mis. 65407) adalah bit error
NILAI_EKSTREM = 122.0                # bacaan >= ini dianggap nilai ekstrem (122,153 di data)


def muat_mentah(path=DATA_DIR / "data.txt"):
    df = pd.read_csv(path, sep=r"\s+", header=None, names=KOLOM, engine="c")
    df = df[df["moteid"].isin(MOTE_VALID)].copy()
    df["ts"] = pd.to_datetime(df["date"] + " " + df["time"], format="mixed", errors="coerce")
    df = df.dropna(subset=["ts"]).drop(columns=["date", "time", "epoch"])
    df["moteid"] = df["moteid"].astype(int)
    return df.sort_values(["moteid", "ts"]).reset_index(drop=True)


def muat_lokasi(path=DATA_DIR / "mote_locs.txt"):
    loc = pd.read_csv(path, sep=r"\s+", header=None, names=["moteid", "x", "y"])
    return loc.set_index("moteid")


def per_menit(df):
    """Rata-rata per menit per mote. Menit tanpa bacaan tidak muncul (dihitung sebagai missing di fitur).

    Bacaan ekstrem tidak dirata-ratakan dengan bacaan normal: kolom `ekstrem` = ada bacaan ekstrem
    di menit itu, dan suhu menit itu dihitung dari bacaan non-ekstrem saja (NaN bila semuanya ekstrem).
    """
    d = df.copy()
    d["menit"] = d["ts"].dt.floor("min")
    d["ekstrem"] = d["temperature"] >= NILAI_EKSTREM
    d.loc[d["ekstrem"], "temperature"] = np.nan
    g = d.groupby(["moteid", "menit"])
    m = g[["temperature", "humidity", "light", "voltage"]].mean()
    m["ekstrem"] = g["ekstrem"].any()
    m["n_bacaan"] = g.size()
    return m.reset_index()


def kejadian_gagal(df, h_jam):
    """Per mote: waktu kegagalan (atau NaT) + jenisnya. `df` = data mentah (bukan per menit)."""
    akhir_data = df["ts"].max()
    out = []
    for mote, g in df.groupby("moteid"):
        ekstrem = g.loc[g["temperature"] >= NILAI_EKSTREM, "ts"]
        t_ekstrem = ekstrem.min() if len(ekstrem) else pd.NaT
        terakhir = g["ts"].max()
        t_mati = terakhir if (akhir_data - terakhir) > pd.Timedelta(hours=h_jam) else pd.NaT
        kandidat = [(t, j) for t, j in [(t_ekstrem, "ekstrem"), (t_mati, "mati")] if pd.notna(t)]
        t_gagal, jenis = min(kandidat) if kandidat else (pd.NaT, None)
        out.append({"moteid": mote, "awal": g["ts"].min(), "terakhir": terakhir, "t_ekstrem": t_ekstrem,
                    "t_mati": t_mati, "t_gagal": t_gagal, "jenis": jenis, "n_bacaan": len(g)})
    return pd.DataFrame(out).set_index("moteid")
