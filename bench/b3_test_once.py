"""G3 -- evaluasi split TEST, SEKALI per model. Hanya dijalankan setelah user menyetujui di G3.

  python -m bench.b3_test_once --model ml/reports/coldtrack.onnx --id baseline_proposal
  python -m bench.b3_test_once --model backend/models/candidates/coldtrack_gru_b3.onnx --id kandidat_b3

Setiap akses dicatat di bench/results/test_access_log.json (append). Bila --id yang sama sudah
pernah dievaluasi, skrip MENOLAK berjalan (aturan: split test dipakai sekali per model).
Evaluasi lewat ONNX Runtime CPU EP -- artefak yang benar-benar akan dipasang, bukan bobot PyTorch.

Hasil: bench/results/test/<id>.json
"""

import argparse
import json
import sys

import numpy as np

from bench.common import (
    RESULTS_DIR,
    ROOT,
    git_info,
    now_iso,
    rel,
    sha256_file,
    write_json,
)

LOG = RESULTS_DIR / "test_access_log.json"
TEST_PATH = ROOT / "data" / "processed" / "windows" / "windows_test.npz"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True)
    ap.add_argument("--id", required=True)
    a = ap.parse_args(argv)

    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else []
    if any(e["id"] == a.id for e in log):
        sys.exit(f"DITOLAK: model '{a.id}' sudah pernah dievaluasi di split test ({LOG.name}).")

    import onnxruntime as ort
    from sklearn.metrics import average_precision_score, f1_score

    model = ROOT / a.model
    entri = {"id": a.id, "model": rel(model), "sha256_model": sha256_file(model), "waktu_utc": now_iso(),
             "git": git_info()}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(log + [entri], indent=2, ensure_ascii=False), encoding="utf-8")  # catat DULU

    d = np.load(TEST_PATH)
    sess = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    X = d["X"].astype(np.float32)
    outs = [sess.run(None, {"window": X[i:i + 4096]}) for i in range(0, len(X), 4096)]
    names = [o.name for o in sess.get_outputs()]
    o = {n: np.concatenate([b[k] for b in outs]) for k, n in enumerate(names)}

    m = {}
    if "forecast_c" in o:
        for k, h in enumerate([15, 30, 60]):
            m[f"forecast_t{h}_mae_c"] = float(np.abs(o["forecast_c"][:, k] - d["y_forecast"][:, k]).mean())
    if "failure_prob" in o:
        pred = o["failure_prob"].argmax(1)
        m["macro_f1"] = float(f1_score(d["y_mode"], pred, average="macro"))
        m["akurasi"] = float((pred == d["y_mode"]).mean())
        m["anomali_pr_auc"] = float(average_precision_score((d["y_mode"] != 0).astype(int),
                                                            1 - o["failure_prob"][:, 0]))
    if "time_to_breach_min" in o:
        msk = d["y_ttb"] != 999.0
        p, y = np.ravel(o["time_to_breach_min"])[msk], d["y_ttb"][msk]
        m["ttb_mae_semua_menit"] = float(np.abs(p - y).mean())
        for b in (10, 30):
            m[f"ttb_mae_le{b}_menit"] = float(np.abs(p[y <= b] - y[y <= b]).mean())
    path = write_json(RESULTS_DIR / "test" / f"{a.id}.json", entri | {"split": "test", "metrik_test": m})
    print(json.dumps(m, indent=2), "\nTersimpan:", rel(path))


if __name__ == "__main__":
    main()
