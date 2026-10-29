"""Kuantisasi GRU ONNX (kontrak coldtrack_v5) menjadi image flash gru_engine, lalu cek image itu terhadap golden.

  python hw/asic/GRU/golden/make_image.py [--onnx backend/models/coldtrack_v5.onnx] [--out hw/asic/GRU/model/coldtrack_v5_gru.bin]

Butuh paket onnx (hanya untuk membaca bobot). Image belum bertag HMAC; tag ditambahkan saat integrasi chip
(sama dengan image XGBoost, hw/asic/xgboost/golden/flash_tag.py).
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

import gru_golden as G

ROOT = Path(__file__).resolve().parents[4]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--onnx", default=str(ROOT / "backend/models/coldtrack_v5.onnx"))
    ap.add_argument("--out", default=str(ROOT / "hw/asic/GRU/model/coldtrack_v5_gru.bin"))
    ap.add_argument("--T", type=int, default=60)
    a = ap.parse_args()
    p = G.params_dari_onnx(a.onnx)
    m = G.kuantisasi(p, a.T)
    img = G.image(m)
    # image -> model harus identik dengan model hasil kuantisasi
    m2 = G.baca_image(img)
    rng = np.random.default_rng(0)
    xr = G.raw_q(p["mean"] + rng.normal(0, 1, (4, a.T, len(p["mean"]))) * p["std"])
    cr = G.raw_q(p["cmean"] + rng.normal(0, 1, (4, len(p["cmean"]))) * p["cstd"])
    assert (G.maju(m, xr, cr) == G.maju(m2, xr, cr)).all()
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img)
    info = dict(sumber=Path(a.onnx).name, sha256_onnx=hashlib.sha256(Path(a.onnx).read_bytes()).hexdigest(),
                sha256_image=hashlib.sha256(img).hexdigest(), byte=len(img),
                L=m.L, H=m.H, NI=m.NI, NC=m.NC, T=m.T, NO=m.NO,
                byte_per_langkah=int.from_bytes(img[13:16], "little") - int.from_bytes(img[10:13], "little"),
                forecast_mul=np.asarray(p["fc_mul"]).tolist(), forecast_add=np.asarray(p["fc_add"]).tolist(),
                forecast_residual=bool(p["residual"]),
                keluaran=("0..2 forecast t15/t30/t60: C = v/1024*mul + add" + (" + temp_c terakhir" if p["residual"] else "")
                          + "; 3..9 logit kelas; 10 ttb mentah (menit = exp(v/1024) - 1)"))
    out.with_suffix(".json").write_text(json.dumps(info, indent=1) + "\n")
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
