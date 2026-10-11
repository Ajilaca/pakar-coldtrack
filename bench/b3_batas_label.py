"""Analisis TAMBAHAN (bukan metrik resmi): seberapa besar label implisit membatasi skor klasifikasi.

Model acuan v3 (ml/reports/coldtrack_b3.onnx) dievaluasi di split VAL dua kali:
  (a) semua jendela -- sama dengan metrik resmi;
  (b) tanpa jendela berlabel A1/A7 yang tidak memuat jejak peristiwanya (door_open / speed 0)
      di dalam jendela -- jendela yang tidak mungkin dipelajari model berbasis jendela.
Selisih (a) vs (b) adalah indikasi batas yang ditimbulkan definisi label, bukan target baru.
Split test TIDAK disentuh.

  python -m bench.b3_batas_label

Hasil: bench/results/g16-gpu/B3/batas_label.json
"""

import numpy as np

from bench.common import RESULTS_DIR, ROOT, git_info, now_iso, write_json


def skor(prob, y):
    from sklearn.metrics import average_precision_score, f1_score

    pred = prob.argmax(1)
    return {
        "n": len(y),
        "macro_f1": float(f1_score(y, pred, average="macro")),
        "akurasi": float((pred == y).mean()),
        "anomali_pr_auc": float(average_precision_score((y != 0).astype(int), 1 - prob[:, 0])),
    }


def main():
    import onnxruntime as ort

    from bench import train_lib as tl
    from ml.preprocess.build_windows import CLASS_TO_IDX
    from ml.tests.test_data_contract import FEATURE_COLUMNS

    d = np.load(tl.split_path("val"))
    X, y = d["X"].astype(np.float32), d["y_mode"]
    tanpa_jejak = ((y == CLASS_TO_IDX["A1"]) & (X[:, :, FEATURE_COLUMNS.index("door_open")].max(1) < 0.5)) | (
        (y == CLASS_TO_IDX["A7"]) & ~(X[:, :, FEATURE_COLUMNS.index("speed_kmh")] <= 0.0).any(1)
    )
    hasil = {
        "waktu_utc": now_iso(),
        "git": git_info(),
        "split": "val",
        "jenis": "analisis tambahan, bukan metrik resmi",
        "n_jendela_tanpa_jejak_dibuang": int(tanpa_jejak.sum()),
        "model": {},
    }
    for nama, path in [("v2_proposal", "ml/reports/coldtrack.onnx"), ("v3_b3", "ml/reports/coldtrack_b3.onnx")]:
        sess = ort.InferenceSession(str(ROOT / path), providers=["CPUExecutionProvider"])
        prob = np.concatenate(
            [sess.run(["failure_prob"], {"window": X[i : i + 4096]})[0] for i in range(0, len(X), 4096)]
        )
        hasil["model"][nama] = {
            "semua_jendela": skor(prob, y),
            "tanpa_jendela_tak_berjejak": skor(prob[~tanpa_jejak], y[~tanpa_jejak]),
        }
        a, b = hasil["model"][nama]["semua_jendela"], hasil["model"][nama]["tanpa_jendela_tak_berjejak"]
        print(
            f"{nama:12s} semua: F1 {a['macro_f1']:.3f} PR-AUC {a['anomali_pr_auc']:.3f} | "
            f"tanpa tak-berjejak ({b['n']}): F1 {b['macro_f1']:.3f} PR-AUC {b['anomali_pr_auc']:.3f}"
        )
    print("Tersimpan:", write_json(RESULTS_DIR / "g16-gpu" / "B3" / "batas_label.json", hasil))


if __name__ == "__main__":
    main()
