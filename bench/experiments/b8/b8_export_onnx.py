"""Ekspor GRU B8 (label v5 + konteks trip) ke ONNX untuk backend, split VAL saja.

Masukan ONNX: `window` [n, 60, 12] dan `konteks` [n, 6] (bench/experiments/b8/b8_lib.KONTEKS), keduanya
MENTAH; normalisasi train ada di dalam graf, sama seperti ColdTrackDeploy. Keluaran sama dengan v3.
Skrip menolak menulis bila ONNX beda dari PyTorch atau macro F1 val beda dari angka seleksi B8.

  python -m bench.experiments.b8.b8_export_onnx

Hasil: backend/models/candidates/coldtrack_gru_v5_context.{onnx,json}
"""

import json
import sys

import numpy as np
import onnxruntime as ort
import torch
from torch import nn

from bench.core.common import ROOT, git_info, now_iso, rel, sha256_file

CKPT = ROOT / "data" / "processed" / "windows" / "gru_v5_context_seed1000.pt"
SELEKSI = ROOT / "bench" / "results" / "local-cpu" / "B8" / "gru_v5_context_seed1000.json"
OUT = ROOT / "backend" / "models" / "candidates" / "coldtrack_gru_v5_context"
TOLERANSI = 1e-4


class Deploy(nn.Module):
    def __init__(self, core, ck):
        super().__init__()
        self.core = core
        self.register_buffer("mean", torch.tensor(ck["mean"], dtype=torch.float32).view(1, 1, -1))
        self.register_buffer("std", torch.tensor(ck["std"], dtype=torch.float32).view(1, 1, -1))
        self.register_buffer("ctx_mean", torch.tensor(ck["ctx_mean"]).view(1, -1))
        self.register_buffer("ctx_std", torch.tensor(ck["ctx_std"]).view(1, -1))

    def forward(self, window, konteks):
        f, logits, ttb_log = self.core((window - self.mean) / self.std, (konteks - self.ctx_mean) / self.ctx_std)
        return (f * self.std[0, 0, 0] + self.mean[0, 0, 0], torch.softmax(logits, dim=1),
                (torch.exp(ttb_log) - 1.0).clamp(min=0.0))


def main():
    from bench.experiments.b8 import b8_lib as b8
    from bench.experiments.b8.b8_gru import kelas_model
    from bench.experiments.b8.b8_label_context import metrik_kelas
    from ml.preprocess.build_windows import FAILURE_CLASSES
    from ml.tests.test_data_contract import FEATURE_COLUMNS

    ck = torch.load(CKPT, weights_only=False)
    cfg = ck["cfg"]
    core = kelas_model()(n_konteks=len(b8.KONTEKS), hidden_size=cfg["hidden_size"], num_layers=cfg["num_layers"],
                         dropout=cfg["dropout"])
    core.load_state_dict(ck["state"])
    model = Deploy(core, ck).eval()

    X = np.load(b8.path_npz("val"))["X"].astype(np.float32)
    d = b8.muat("val")
    ctx = d["ctx"].astype(np.float32)
    onnx_path = OUT.with_suffix(".onnx")
    torch.onnx.export(model, (torch.tensor(X[:1]), torch.tensor(ctx[:1])), onnx_path,
                      input_names=["window", "konteks"],
                      output_names=["forecast_c", "failure_prob", "time_to_breach_min"],
                      dynamic_axes={k: {0: "batch"} for k in ("window", "konteks", "forecast_c", "failure_prob",
                                                               "time_to_breach_min")},
                      opset_version=17, dynamo=False)

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    with torch.no_grad():
        ref = [t.numpy() for t in model(torch.tensor(X[:256]), torch.tensor(ctx[:256]))]
    got = sess.run(None, {"window": X[:256], "konteks": ctx[:256]})
    # aturan ml/export/export_onnx.py: per keluaran, selisih absolut ATAU relatif < TOLERANSI
    selisih = {n: float(np.abs(a - b).max()) / max(float(np.abs(a).max()), 1.0)
               for n, a, b in zip(("forecast_c", "failure_prob", "time_to_breach_min"), ref, got, strict=True)}
    if max(selisih.values()) > TOLERANSI:
        onnx_path.unlink()
        sys.exit(f"DITOLAK: ONNX beda dari PyTorch {selisih}")

    prob = np.concatenate([sess.run(None, {"window": X[i:i + 4096], "konteks": ctx[i:i + 4096]})[1]
                           for i in range(0, len(X), 4096)])
    val = metrik_kelas(d["y_baru"], prob)
    seleksi = json.loads(SELEKSI.read_text(encoding="utf-8"))
    if abs(val["macro_f1"] - seleksi["macro_f1"]) > 0.002:
        onnx_path.unlink()
        sys.exit(f"DITOLAK: macro F1 val ONNX {val['macro_f1']:.4f} != seleksi {seleksi['macro_f1']:.4f}")

    kontrak = {
        "status": "KANDIDAT v5 (B8). Split test lewat bench/experiments/b10/b10_gru_test_once.py.",
        "dibuat_utc": now_iso(), "git": git_info(), "checkpoint": rel(CKPT), "sha256_onnx": sha256_file(onnx_path),
        "label": "v5 (bench/experiments/b8/b8_lib.py: A1/A7 sementara)",
        "konfigurasi": cfg,
        "parameter": sum(p.numel() for p in core.parameters()),
        "kontrak": {
            "input": {"name": "window", "shape": ["batch", 60, len(FEATURE_COLUMNS)], "features": FEATURE_COLUMNS,
                      "catatan": "identik dengan coldtrack_v3.onnx"},
            "input_konteks": {"name": "konteks", "shape": ["batch", len(b8.KONTEKS)], "features": b8.KONTEKS,
                              "catatan": "mentah, kausal dari temp_c sejak awal trip (b8_lib.konteks_trip)"},
            "outputs": {"forecast_c": {"horizons_menit": [15, 30, 60]},
                        "failure_prob": {"classes": FAILURE_CLASSES},
                        "time_to_breach_min": {"catatan": "head GRU; TTB produksi tetap mesin fisika"}},
        },
        "paritas_onnx_vs_pytorch": selisih,
        "metrik_val": {k: val[k] for k in ("macro_f1", "anomali_pr_auc", "akurasi")} | {"per_kelas": val["per_kelas"]},
    }
    OUT.with_suffix(".json").write_text(json.dumps(kontrak, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Tersimpan: {rel(onnx_path)}  paritas {max(selisih.values()):.1e}  macro F1 val {val['macro_f1']:.4f}")


if __name__ == "__main__":
    main()
