"""B12 -- presisi dan recall aturan diagnosis A3/A8 (backend/app/inference.aturan_diagnosis), split VAL saja.

Aturan dihitung per menit dari data trip val (riwayat penuh sejak awal trip), lalu dinilai pada jendela yang sama
dengan model (bench/experiments/b8/b8_lib.py, label v5). Label dan aturan A8 sama-sama berlaku sampai akhir trip.

  python -m bench.experiments.b12.b12_aturan

Hasil: bench/results/lokal-cpu/B12/aturan.json
"""

import sys

import numpy as np

from bench.core.common import RESULTS_DIR, ROOT, git_info, now_iso, rel, write_json

OUT = RESULTS_DIR / "lokal-cpu" / "B12" / "aturan.json"


def main():
    import pandas as pd

    sys.path.insert(0, str(ROOT / "backend"))
    from app.inference import REEFER_MATI_MENIT, REEFER_MATI_NAIK_C, cargo_params

    from bench.experiments.b8 import b8_lib as b8
    from eval.common import CARGO_TO_PROFILE
    from ml.preprocess.build_windows import CLASS_TO_IDX

    d = b8.muat("val")
    df = pd.read_parquet(ROOT / "data/processed/v4_seed1000_700trips.parquet")
    a3, a8 = np.zeros(len(d["y_baru"]), bool), np.zeros(len(d["y_baru"]), bool)
    for tid, g in df[df.split == "val"].groupby("trip_id"):
        g = g.sort_values("minute").reset_index(drop=True)
        t_hi = cargo_params(CARGO_TO_PROFILE[g.cargo_type.iloc[0]], None)["t_hi"]
        temp = g.temp_c.ffill().bfill().to_numpy()
        mati = g.reefer_on.to_numpy() < 0.5
        run = np.zeros(len(g), int)
        for i, m in enumerate(mati):
            run[i] = (run[i - 1] + 1 if i else 1) if m else 0
        awal = temp[:5].mean()
        sel = np.where(d["trip"] == tid)[0]
        t = d["menit"][sel]
        a3[sel] = (run[t] >= REEFER_MATI_MENIT) & (temp[t] - temp[np.maximum(t - run[t], 0)] >= REEFER_MATI_NAIK_C)
        a8[sel] = awal > t_hi

    y = d["y_baru"]
    hasil = {"waktu_utc": now_iso(), "git": git_info(), "split": "val", "label": "v5",
             "aturan": {"reefer_mati_menit": REEFER_MATI_MENIT, "reefer_mati_naik_c": REEFER_MATI_NAIK_C}}
    for nama, flag, kelas in (("reefer_mati_total", a3, "A3"), ("prapendinginan_buruk", a8, "A8")):
        benar = y == CLASS_TO_IDX[kelas]
        hasil[nama] = {"n_kelas": int(benar.sum()), "n_ditandai": int(flag.sum()),
                       "presisi": float((flag & benar).sum() / max(flag.sum(), 1)),
                       "recall": float((flag & benar).sum() / max(benar.sum(), 1)),
                       "salah_tandai_per_kelas": {c: int((flag & (y == i)).sum()) for c, i in CLASS_TO_IDX.items()
                                                  if c != kelas and (flag & (y == i)).any()}}
    for k in ("reefer_mati_total", "prapendinginan_buruk"):
        print(k, {x: (round(v, 3) if isinstance(v, float) else v) for x, v in hasil[k].items()})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    print("Tersimpan:", rel(write_json(OUT, hasil)))


if __name__ == "__main__":
    main()
