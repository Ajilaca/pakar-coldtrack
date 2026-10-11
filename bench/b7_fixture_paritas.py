"""B7 -- fixture paritas ONNX v3 vs PyTorch untuk tes CI backend (tanpa torch di CI).

Bobot PyTorch v3 tidak disimpan saat ekspor (bench/b3_export.py). Skrip ini melatih ulang konfigurasi
yang sama dengan seed 1000 lalu MEMVERIFIKASI bahwa keluarannya sama dengan berkas ONNX yang sudah
diuji di G3 (ml/reports/coldtrack_b3.onnx) -- bila tidak sama, skrip gagal dan tidak menulis fixture.
Bila sama, keluaran PyTorch (ColdTrackDeploy) pada 64 jendela VAL disimpan sebagai acuan; tes
backend membandingkan ONNX Runtime terhadap acuan itu. Split test tidak dipakai.

  python -m bench.b7_fixture_paritas --tag g16-gpu

Keluaran: backend/tests/fixtures/v3_parity.npz (+ .json metadata)
"""

import argparse
import json

import numpy as np
import torch

from bench.common import ROOT, git_info, now_iso, sha256_file

ONNX = ROOT / "ml" / "reports" / "coldtrack_b3.onnx"
OUT = ROOT / "backend" / "tests" / "fixtures" / "v3_parity.npz"
TOL_ABS, TOL_REL = 1e-4, 1e-4          # sama dengan ml/export_onnx.TOLERANCE
N = 64


def main(argv=None):
    from bench.run import apply_device_env, check_cuda_or_die, resolve_tag

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", default="g16-gpu")
    a = ap.parse_args(argv)
    _, kind = resolve_tag(a.tag)
    apply_device_env(kind)
    check_cuda_or_die(kind)
    import onnxruntime as ort

    from bench import b3_lib as b3
    from bench import train_lib as tl
    from ml.model import ColdTrackDeploy, ColdTrackGRU

    kartu = json.loads((ROOT / "ml" / "reports" / "labels_b3.json").read_text(encoding="utf-8"))
    cfg = b3.GruCfg(**kartu["konfigurasi"])
    data, _ = tl.prepare_gru_data()
    model, _ = b3.train(data, cfg, kartu["seed_final"], kind)
    core = ColdTrackGRU(hidden_size=cfg.hidden_size, num_layers=cfg.num_layers, dropout=cfg.dropout)
    core.load_state_dict({k: v.cpu() for k, v in model.state_dict().items()})
    deploy = ColdTrackDeploy(core.eval(), data["mean"], data["std"]).eval()

    X = np.load(tl.split_path("val"))["X"][:N].astype(np.float32)
    with torch.no_grad():
        ref = [t.numpy() for t in deploy(torch.tensor(X))]
    got = ort.InferenceSession(str(ONNX), providers=["CPUExecutionProvider"]).run(None, {"window": X})
    nama = ["forecast_c", "failure_prob", "time_to_breach_min"]
    selisih = {}
    for n, p, q in zip(nama, ref, got):
        ab = float(np.abs(p - q).max())
        selisih[n] = {"maxabs": ab, "rel": ab / max(float(np.abs(p).max()), 1e-9)}
    ok = all(v["maxabs"] < TOL_ABS or v["rel"] < TOL_REL for v in selisih.values())
    print("selisih PyTorch(latih ulang) vs ONNX teruji:", selisih)
    if not ok:
        raise SystemExit("GAGAL: model latih ulang tidak sama dengan ONNX yang diuji di G3 -- fixture TIDAK ditulis")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT, window=X, **dict(zip(nama, ref)))
    meta = {"dibuat_utc": now_iso(), "git": git_info(), "onnx_acuan": "ml/reports/coldtrack_b3.onnx",
            "sha256_onnx": sha256_file(ONNX), "masukan": "64 jendela pertama split VAL v4 (mentah)",
            "toleransi": {"abs": TOL_ABS, "rel": TOL_REL,
                          "aturan": "lulus bila maxabs < abs ATAU maxabs/maks|acuan| < rel, per keluaran"},
            "selisih_saat_dibuat": selisih, "seed": kartu["seed_final"], "device_latih": a.tag}
    OUT.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("Tersimpan:", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
