"""B10 -- evaluasi split TEST, SEKALI, untuk GRU B8 (label v5 + konteks) yang sudah diekspor ke ONNX.

Urutan sama dengan b10_test_once.py: artefak beku (ONNX dari b8_export_onnx, sha256 dicatat), macro F1 val
dicek ulang terhadap angka seleksi B8 (tolak bila beda), akses dicatat DULU di test_access_log.json, baru
split test dibangun dan dinilai. Bila id sudah tercatat, skrip menolak berjalan.

  python -m bench.experiments.b10.b10_gru_test_once

Hasil: bench/results/test/b8_gru_v5_konteks.json
"""

import json
import sys

import numpy as np

from bench.core.common import (
    RESULTS_DIR,
    ROOT,
    git_info,
    now_iso,
    rel,
    sha256_file,
    write_json,
)
from bench.experiments.b10.b10_test_once import LOG

ID = "b8_gru_v5_konteks"
ONNX = ROOT / "backend" / "models" / "candidates" / "coldtrack_gru_v5_konteks.onnx"
SELEKSI = RESULTS_DIR / "local-cpu" / "B8" / "gru_v5_konteks_seed1000.json"
HORIZON = (15, 30, 60)


def jalankan(sess, X, ctx, bs=4096):
    out = [sess.run(None, {"window": X[i:i + bs], "konteks": ctx[i:i + bs]}) for i in range(0, len(X), bs)]
    return np.concatenate([o[0] for o in out]), np.concatenate([o[1] for o in out])


def main():
    import onnxruntime as ort

    from bench.experiments.b8 import b8_lib as b8
    from bench.experiments.b8.b8_label_konteks import metrik_kelas

    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else []
    if any(e["id"] == ID for e in log):
        sys.exit(f"DITOLAK: model '{ID}' sudah pernah dievaluasi di split test ({LOG.name}).")

    sess = ort.InferenceSession(str(ONNX), providers=["CPUExecutionProvider"])
    dva = b8.muat("val")
    _, prob = jalankan(sess, np.load(b8.path_npz("val"))["X"].astype(np.float32), dva["ctx"].astype(np.float32))
    val = metrik_kelas(dva["y_baru"], prob)
    seleksi = json.loads(SELEKSI.read_text(encoding="utf-8"))["macro_f1"]
    if abs(val["macro_f1"] - seleksi) > 0.002:
        sys.exit(f"DIBATALKAN sebelum akses test: val {val['macro_f1']:.4f} != angka seleksi {seleksi:.4f}")

    entri = {"id": ID, "model": rel(ONNX), "sha256_model": sha256_file(ONNX), "waktu_utc": now_iso(), "git": git_info()}
    LOG.write_text(json.dumps(log + [entri], indent=2, ensure_ascii=False), encoding="utf-8")  # catat DULU

    dte, _ = b8.bangun("test", izinkan_test=True)
    npz = np.load(b8.path_npz("test", izinkan_test=True))
    fc, prob = jalankan(sess, npz["X"].astype(np.float32), dte["ctx"].astype(np.float32))
    mae = np.abs(fc - npz["y_forecast"]).mean(0)
    hasil = entri | {
        "split": "test", "label": "v5 (bench/experiments/b8/b8_lib.py)",
        "model_jenis": "GRU 3x128 + 72 statistik jendela + 6 konteks trip (B8, seed 1000)",
        "val_seleksi": {"macro_f1": seleksi, "sumber": rel(SELEKSI)},
        "val_artefak_beku": {k: val[k] for k in ("macro_f1", "anomali_pr_auc", "akurasi")},
        "metrik_test_label_v5": metrik_kelas(dte["y_baru"], prob),
        "metrik_test_label_lama": metrik_kelas(dte["y_lama"], prob),
        "forecast_mae_c": {f"t{h}": float(m) for h, m in zip(HORIZON, mae, strict=True)},
    }
    path = write_json(RESULTS_DIR / "test" / f"{ID}.json", hasil)
    for lab in ("metrik_test_label_v5", "metrik_test_label_lama"):
        m = hasil[lab]
        print(f"{lab:24s} macro F1 {m['macro_f1']:.3f}  PR-AUC {m['anomali_pr_auc']:.3f}  akurasi {m['akurasi']:.3f} | "
              + " ".join(f"{c[:6]}:{v['f1']:.2f}" for c, v in m["per_kelas"].items()))
    print("forecast MAE", hasil["forecast_mae_c"])
    print("Tersimpan:", rel(path))


if __name__ == "__main__":
    main()
