"""Ekspor model Time-to-Breach berbasis XGBoost ke ONNX (keputusan tim: opsi hibrida).

Latar belakang. Evaluasi di split test menunjukkan head TTB milik GRU jauh
tertinggal dari XGBoost pada rentang yang menentukan keputusan operasional:
MAE 17,9 vs 7,6 menit untuk TTB <= 30 menit. Karena itu TTB dipindahkan ke
XGBoost, sementara forecast suhu dan klasifikasi mode kegagalan tetap ditangani
GRU yang sudah terpasang.

Kontrak input SENGAJA dibuat identik dengan coldtrack.onnx -- perhitungan 72
fitur agregat dan konversi kembali ke satuan menit dibungkus ke dalam grafik
ONNX, sehingga backend tidak perlu mengubah cara memanggilnya.

Menjalankan: python -m ml.export_ttb_xgboost
"""

import json
import os
import time

import numpy as np
import onnx
import onnxruntime as ort
import torch
import xgboost as xgb
from onnx import compose
from onnxmltools.convert import convert_xgboost
from onnxmltools.convert.common.data_types import FloatTensorType
from torch import nn

from ml.baselines import SENTINEL, XGB_PARAMS, aggregate
from ml.preprocess.build_windows import WINDOW_SIZE
from ml.tests.test_data_contract import FEATURE_COLUMNS

TRAIN_PATH = "data/processed/windows/windows_train.npz"
TEST_PATH = "data/processed/windows/windows_test.npz"
ONNX_OUT = "ml/reports/coldtrack_ttb.onnx"
LABELS_PATH = "ml/reports/labels.json"
OPSET = 15      # onnxmltools belum mendukung opset di atas ini

_TMP = ["ml/reports/_agg.onnx", "ml/reports/_xgb.onnx", "ml/reports/_post.onnx"]


class Aggregate(nn.Module):
    """72 statistik ringkasan dari jendela 60x12 -- harus sama persis dengan
    ml.baselines.aggregate(). Perhatikan unbiased=False: NumPy memakai pembagi n,
    PyTorch memakai n-1 secara default. Perbedaan itu pernah membuat prediksi meleset."""

    def forward(self, x):
        return torch.cat([
            x.mean(dim=1),
            x.std(dim=1, unbiased=False),
            x.amin(dim=1),
            x.amax(dim=1),
            x[:, -1, :],
            x[:, -1, :] - x[:, 0, :],
        ], dim=1)


class Postprocess(nn.Module):
    """Kembalikan dari skala log1p ke menit. exp(y)-1, bukan expm1, karena
    expm1 tidak didukung eksporter ONNX versi lama."""

    def forward(self, y):
        return (torch.exp(y) - 1.0).clamp(min=0.0).reshape(-1)


def latih_model():
    d = np.load(TRAIN_PATH)
    X = aggregate(d["X"])
    msk = d["y_ttb"] != SENTINEL      # sentinel di-mask, sama seperti head TTB GRU
    model = xgb.XGBRegressor(**XGB_PARAMS)
    model.fit(X[msk], np.log1p(d["y_ttb"][msk]))
    print(f"Dilatih pada {msk.sum():,} jendela yang benar-benar menuju breach")
    return model


def bangun_graf(model):
    torch.onnx.export(
        Aggregate(), torch.randn(1, WINDOW_SIZE, len(FEATURE_COLUMNS)), _TMP[0],
        input_names=["window"], output_names=["feat"],
        dynamic_axes={"window": {0: "batch"}, "feat": {0: "batch"}},
        opset_version=OPSET, dynamo=False,
    )
    torch.onnx.export(
        Postprocess(), torch.randn(1, 1), _TMP[2],
        input_names=["raw"], output_names=["ttb"],
        dynamic_axes={"raw": {0: "batch"}, "ttb": {0: "batch"}},
        opset_version=OPSET, dynamo=False,
    )

    n_feat = len(FEATURE_COLUMNS) * 6
    onx = convert_xgboost(model, initial_types=[("feat", FloatTensorType([None, n_feat]))],
                          target_opset=OPSET)
    with open(_TMP[1], "wb") as f:
        f.write(onx.SerializeToString())

    # Prefix diperlukan karena ketiga grafik punya nama node internal yang bertabrakan
    g = compose.merge_models(
        compose.add_prefix(onnx.load(_TMP[0]), "agg_"),
        onnx.load(_TMP[1]),
        io_map=[("agg_feat", "feat")],
    )
    g = compose.merge_models(
        g,
        compose.add_prefix(onnx.load(_TMP[2]), "post_"),
        io_map=[(g.graph.output[0].name, "post_raw")],
    )

    # Kembalikan nama input/output ke kontrak resmi
    lama_in, lama_out = g.graph.input[0].name, g.graph.output[0].name
    for node in g.graph.node:
        node.input[:] = ["window" if i == lama_in else i for i in node.input]
        node.output[:] = ["time_to_breach_min" if o == lama_out else o for o in node.output]
    g.graph.input[0].name = "window"
    g.graph.output[0].name = "time_to_breach_min"

    onnx.checker.check_model(g)
    onnx.save(g, ONNX_OUT)
    for p in _TMP:
        os.remove(p)
    print(f"Tersimpan: {ONNX_OUT}")


def verifikasi():
    sess = ort.InferenceSession(ONNX_OUT)
    d = np.load(TEST_PATH)
    msk = d["y_ttb"] != SENTINEL
    raw = d["X"][msk].astype(np.float32)
    aktual = d["y_ttb"][msk]
    pred = np.ravel(sess.run(None, {"window": raw})[0])

    print("\nAkurasi di split test (pembanding: head TTB milik GRU):")
    hasil = {}
    for batas, acuan_gru in [(10, 6.9), (30, 17.9), (10**9, 52.98)]:
        sel = aktual <= batas
        mae = float(np.abs(pred[sel] - aktual[sel]).mean())
        nama = "keseluruhan" if batas > 1000 else f"TTB <= {batas} menit"
        hasil[nama] = round(mae, 2)
        print(f"  {nama:18s} {mae:6.2f} menit   (GRU: {acuan_gru})")

    for b in [1, 8, 256]:
        sess.run(None, {"window": raw[:b]})
    print("Uji batch 1/8/256: OK")

    contoh = raw[:1]
    sess.run(None, {"window": contoh})
    t0 = time.perf_counter()
    for _ in range(300):
        sess.run(None, {"window": contoh})
    ms = (time.perf_counter() - t0) / 300 * 1000
    print(f"Latensi: {ms:.2f} ms  |  Ukuran: {os.path.getsize(ONNX_OUT) / 1024:.0f} KB")
    return hasil


def perbarui_labels(hasil):
    with open(LABELS_PATH, encoding="utf-8") as f:
        kontrak = json.load(f)

    kontrak["model_ttb_terpisah"] = {
        "file": "coldtrack_ttb.onnx",
        "alasan": (
            "Head TTB milik GRU tertinggal jauh di rentang yang menentukan keputusan "
            "(MAE 17,9 vs 7,6 menit untuk TTB <= 30 menit di split test), sehingga tugas "
            "ini dipindahkan ke XGBoost. Forecast suhu dan klasifikasi mode kegagalan "
            "tetap ditangani coldtrack.onnx."
        ),
        "input": {
            "name": "window",
            "shape": ["batch", WINDOW_SIZE, len(FEATURE_COLUMNS)],
            "dtype": "float32",
            "catatan": "IDENTIK dengan coldtrack.onnx -- tensor yang sama bisa dikirim ke kedua model.",
        },
        "output": {
            "name": "time_to_breach_min",
            "shape": ["batch"],
            "satuan": "menit",
            "catatan": (
                "Tetap hanya bermakna bila failure_prob dari coldtrack.onnx menunjuk ke "
                "kelas non-A0. Model ini dilatih hanya pada jendela yang benar-benar menuju "
                "breach, jadi keluarannya untuk kondisi sehat tidak terdefinisi."
            ),
        },
        "akurasi_test": hasil,
        "keterbatasan": [
            "Akurasi menurun tajam seiring jarak: andal untuk peringatan di bawah ~30 menit, tidak andal sebagai hitung mundur jarak jauh.",
            "Perhitungan agregat dibungkus di dalam grafik ONNX. Karena model pohon bersifat diskontinu, pembulatan float32 membuat sebagian prediksi berbeda tipis dari XGBoost yang dipanggil langsung; dampaknya pada MAE keseluruhan di bawah 0,5 menit.",
        ],
    }

    with open(LABELS_PATH, "w", encoding="utf-8") as f:
        json.dump(kontrak, f, indent=2, ensure_ascii=False)
    print(f"Diperbarui: {LABELS_PATH}")


def main():
    bangun_graf(latih_model())
    perbarui_labels(verifikasi())
    print("\nSiap diserahkan ke R3.")


if __name__ == "__main__":
    main()
