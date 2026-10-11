"""Metrik G4 sesuai bench/results/keputusan/G4_definisi.json (tingkat jendela + episode alarm palsu)."""

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

MENIT_PER_JENDELA_LANGKAH = 10


def alarm_palsu_per_mote_hari(df, skor, ambang, label="y_24j"):
    """Episode = tepi naik rangkaian jendela beralarm (urut per mote); dihitung bila jendela itu negatif.
    Dibagi mote-hari yang diamati pada periode berlabel negatif."""
    d = df.assign(_a=(np.asarray(skor) >= ambang)).sort_values(["moteid", "ujung"])
    naik = d["_a"] & ~d.groupby("moteid")["_a"].shift(1, fill_value=False)
    n_palsu = int((naik & (d[label] == 0)).sum())
    mote_hari = (d[label] == 0).sum() * MENIT_PER_JENDELA_LANGKAH / 1440
    return n_palsu / mote_hari if mote_hari else float("nan"), n_palsu, float(mote_hari)


def ringkas(df, skor, ambang, label="y_24j"):
    y = df[label].to_numpy()
    s = np.asarray(skor, float)
    a = s >= ambang
    fa, n_fa, mh = alarm_palsu_per_mote_hari(df, s, ambang, label)
    # sekunder: recall tingkat kejadian + lead time (menit sebelum gagal saat alarm pertama dalam 24 jam)
    pos = df.assign(_a=a)[y == 1]
    per_mote = pos.groupby("moteid").apply(
        lambda g: g.loc[g["_a"], "menit_ke_gagal"].max() if g["_a"].any() else np.nan, include_groups=False)
    return {
        "pr_auc": float(average_precision_score(y, s)) if y.any() else float("nan"),
        "ambang": float(ambang), "recall_jendela": float(a[y == 1].mean()) if y.any() else float("nan"),
        "presisi_jendela": float(y[a].mean()) if a.any() else float("nan"),
        "alarm_palsu_per_mote_hari": fa, "n_episode_alarm_palsu": n_fa, "mote_hari_negatif": mh,
        "recall_kejadian": float(per_mote.notna().mean()) if len(per_mote) else float("nan"),
        "lead_time_median_menit": float(np.nanmedian(per_mote)) if per_mote.notna().any() else None,
        "n_jendela": len(df), "n_positif": int(y.sum()), "n_mote": int(df["moteid"].nunique()),
    }


def pilih_ambang(df, skor, recall_min, label="y_24j"):
    """Ambang dengan alarm palsu per mote-hari terkecil di antara ambang yang recall >= recall_min."""
    y = df[label].to_numpy()
    s = np.asarray(skor, float)
    terbaik = None
    for t in np.unique(np.quantile(s, np.linspace(0.5, 0.9999, 400))):
        rc = (s[y == 1] >= t).mean()
        if rc < recall_min:
            continue
        fa = alarm_palsu_per_mote_hari(df, s, t, label)[0]
        if terbaik is None or fa < terbaik[1]:
            terbaik = (float(t), fa, float(rc))
    return terbaik


def fitur_kolom(df):
    return [c for c in df.columns if c not in ("moteid", "split", "ujung", "waktu_ujung", "menit_ke_gagal", "skor_v0")
            and not c.startswith("y_")]


def muat(path=None):
    from ml.sensor_health.features import OUT

    return pd.read_parquet(path or OUT)


HALUS = {"tanpa": None, "mean3": ("mean", 3), "mean6": ("mean", 6), "max3": ("max", 3), "max6": ("max", 6)}


def haluskan(df, skor, jenis):
    """Penghalusan KAUSAL skor per mote (hanya jendela saat ini dan sebelumnya) -- mengurangi alarm
    yang berkedip sehingga satu kondisi tidak dihitung sebagai banyak episode."""
    if HALUS[jenis] is None:
        return np.asarray(skor, float)
    agg, n = HALUS[jenis]
    s = pd.Series(np.asarray(skor, float), index=df.index)
    urut = df.sort_values(["moteid", "ujung"]).index
    r = s.loc[urut].groupby(df.loc[urut, "moteid"]).rolling(n, min_periods=1)
    out = (r.mean() if agg == "mean" else r.max()).reset_index(level=0, drop=True)
    return out.reindex(df.index).to_numpy()
