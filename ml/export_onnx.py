"""Fase 6 R2 -- ekspor model ke ONNX untuk diserahkan ke R3.

Menjalankan: python -m ml.export_onnx
"""

import json
import sys
import time

import numpy as np
import onnxruntime as ort
import torch

from ml.model import ColdTrackGRU, ColdTrackDeploy
from ml.preprocess.build_windows import FAILURE_CLASSES, MODE_MAPPING, WINDOW_SIZE, HORIZONS
from ml.scaler import load_scaler
from ml.tests.test_data_contract import FEATURE_COLUMNS

sys.stdout.reconfigure(encoding='utf-8')   # exporter PyTorch mencetak emoji; konsol Windows perlu ini

CHECKPOINT = "ml/reports/coldtrack_finetuned.pt"
SCALER_PATH = "ml/reports/scaler_finetune.npz"
VAL_PATH = "data/processed/windows/windows_val.npz"
ONNX_PATH = "ml/reports/coldtrack.onnx"
LABELS_PATH = "ml/reports/labels.json"

TOLERANCE = 1e-4


def build_deploy_model():
    mean, std = load_scaler(SCALER_PATH)
    core = ColdTrackGRU()
    core.load_state_dict(torch.load(CHECKPOINT))
    core.eval()
    return ColdTrackDeploy(core, mean, std).eval()


def export(model):
    torch.onnx.export(
        model,
        torch.randn(1, WINDOW_SIZE, len(FEATURE_COLUMNS)),
        ONNX_PATH,
        input_names=['window'],
        output_names=['forecast_c', 'failure_prob', 'time_to_breach_min'],
        dynamic_axes={
            'window': {0: 'batch'},
            'forecast_c': {0: 'batch'},
            'failure_prob': {0: 'batch'},
            'time_to_breach_min': {0: 'batch'},
        },
        opset_version=17,
        dynamo=False,      # exporter lama -- dynamic_axes untuk output baru berlaku di sini
    )
    print(f"Tersimpan: {ONNX_PATH}")


def verify_parity(model):
    """Bandingkan output ONNX vs PyTorch di data val asli."""
    raw = np.load(VAL_PATH)['X'][:64].astype(np.float32)

    with torch.no_grad():
        ref = [t.numpy() for t in model(torch.tensor(raw))]

    sess = ort.InferenceSession(ONNX_PATH)
    got = sess.run(None, {'window': raw})

    print(f"\nVerifikasi kesetaraan numerik (toleransi {TOLERANCE}):")
    all_ok = True
    for name, a, b in zip(['forecast_c', 'failure_prob', 'time_to_breach_min'], ref, got):
        abs_diff = np.abs(a - b).max()
        rel_diff = abs_diff / max(np.abs(a).max(), 1e-9)
        ok = abs_diff < TOLERANCE or rel_diff < TOLERANCE
        all_ok &= ok
        catatan = "" if abs_diff < TOLERANCE else f"  (lolos via selisih relatif {rel_diff:.2e})"
        print(f"  {name:20s} selisih maks = {abs_diff:.3e}  {'OK' if ok else 'GAGAL'}{catatan}")
    return all_ok, sess


def benchmark(sess, n=200):
    sample = np.random.randn(1, WINDOW_SIZE, len(FEATURE_COLUMNS)).astype(np.float32)
    sess.run(None, {'window': sample})            # sekali dulu untuk pemanasan
    t0 = time.perf_counter()
    for _ in range(n):
        sess.run(None, {'window': sample})
    ms = (time.perf_counter() - t0) / n * 1000
    print(f"\nLatensi inferensi (batch=1, CPU): {ms:.2f} ms   (target <300 ms)")


def write_labels():
    """Kontrak model untuk R3 -- semua yang perlu diketahui backend."""
    contract = {
        "model_version": "v1-finetuned-on-v3",
        "input": {
            "name": "window",
            "shape": ["batch", WINDOW_SIZE, len(FEATURE_COLUMNS)],
            "dtype": "float32",
            "features": FEATURE_COLUMNS,
            "catatan": "Nilai MENTAH, tidak perlu dinormalisasi. Urutan kolom wajib persis seperti di atas. Baris terakhir jendela = menit 'sekarang'.",
        },
        "outputs": {
            "forecast_c": {
                "shape": ["batch", len(HORIZONS)],
                "satuan": "derajat Celsius",
                "horizons_menit": HORIZONS,
            },
            "failure_prob": {
                "shape": ["batch", len(FAILURE_CLASSES)],
                "satuan": "probabilitas 0-1, jumlahnya 1",
                "classes": FAILURE_CLASSES,
            },
            "time_to_breach_min": {
                "shape": ["batch"],
                "satuan": "menit",
                "catatan": "Hanya bermakna bila failure_prob menunjuk ke kelas non-A0. Head ini dilatih dengan sentinel 999 di-mask dari loss, jadi keluarannya tidak terdefinisi untuk kondisi sehat.",
            },
        },
        "mode_mapping": MODE_MAPPING,
        "keterbatasan": [
            "Dilatih pada dataset v3, yang failure_mode-nya konstan per trip (bug dilaporkan ke R1). Sekitar 48% jendela anomali salah label.",
            "Metrik head-2 dan head-3 belum mencapai target; akan dilatih ulang begitu dataset v4 tersedia.",
        ],
    }
    with open(LABELS_PATH, 'w', encoding='utf-8') as f:
        json.dump(contract, f, indent=2, ensure_ascii=False)
    print(f"Tersimpan: {LABELS_PATH}")


def main():
    model = build_deploy_model()
    export(model)
    ok, sess = verify_parity(model)
    benchmark(sess)
    write_labels()
    print("\nSiap diserahkan ke R3." if ok else "\nADA YANG GAGAL -- jangan diserahkan dulu.")


if __name__ == "__main__":
    main()
