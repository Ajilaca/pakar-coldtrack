"""B3 -- cek hipotesis "label implisit" dari DATA saja (tanpa model), split VAL.

Katalog anomali (role/context-r1-ai-data.md): A1 pintu terbuka 5-40 menit, A7 kejut ambien saat
berhenti > 20 menit, A8 prapendinginan buruk di awal trip -- peristiwa sementara. Label
failure_mode bertahan dari onset sampai akhir trip (ml/tests: test_labels_match_onset_minute).
Bila hipotesis benar, banyak jendela berlabel A1/A7 jauh setelah onset tidak memuat jejak
peristiwanya sama sekali -> tidak bisa dipelajari model apa pun dari jendela 60 menit.

Jejak per jendela (60 menit): A1 = ada menit door_open = 1; A7 = ada menit speed_kmh = 0.

  python -m bench.b3_label_check

Hasil: bench/results/g16-gpu/B3/label_check.json
"""

import numpy as np

from bench.common import RESULTS_DIR, git_info, now_iso, write_json

BUCKET = [(0, 10), (10, 30), (30, 60), (60, 120), (120, 10_000)]


def main():
    from bench import b3_lib as b3
    from bench import train_lib as tl
    from ml.preprocess.build_windows import CLASS_TO_IDX
    from ml.tests.test_data_contract import FEATURE_COLUMNS

    tl.ensure_windows()
    d = np.load(tl.split_path("val"))
    onset = b3.menit_sejak_onset("val")
    X, y = d["X"], d["y_mode"]
    jejak = {
        "A1": X[:, :, FEATURE_COLUMNS.index("door_open")].max(1) >= 0.5,
        "A7": (X[:, :, FEATURE_COLUMNS.index("speed_kmh")] <= 0.0).any(1),
    }
    hasil = {"waktu_utc": now_iso(), "git": git_info(), "split": "val", "kelas": {}}
    for kelas, ada in jejak.items():
        sel_k = y == CLASS_TO_IDX[kelas]
        per = {}
        for lo, hi in BUCKET:
            sel = sel_k & (onset >= lo) & (onset < hi)
            if sel.any():
                per[f"{lo}-{hi if hi < 10_000 else 'inf'}"] = {
                    "n": int(sel.sum()), "porsi_tanpa_jejak": float(1 - ada[sel].mean())}
        # pembanding: seberapa sering jejak yang sama muncul di jendela sehat (A0)
        hasil["kelas"][kelas] = {"jumlah_jendela": int(sel_k.sum()),
                                 "porsi_tanpa_jejak_total": float(1 - ada[sel_k].mean()),
                                 "per_bucket_menit_sejak_onset": per,
                                 "porsi_A0_dengan_jejak": float(ada[y == 0].mean())}
        print(f"{kelas}: {sel_k.sum()} jendela, tanpa jejak {1 - ada[sel_k].mean():.1%} "
              f"(A0 yang punya jejak sama: {ada[y == 0].mean():.1%})")
        for b, v in per.items():
            print(f"   {b:8s} n={v['n']:5d} tanpa jejak {v['porsi_tanpa_jejak']:.1%}")
    print("Tersimpan:", write_json(RESULTS_DIR / "g16-gpu" / "B3" / "label_check.json", hasil))


if __name__ == "__main__":
    main()
