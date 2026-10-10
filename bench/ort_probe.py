"""Uji ONNX Runtime yang berdiri sendiri (hanya butuh numpy + onnxruntime).

Dipanggil sebagai subprocess dari venv ORT GPU (~/.venvs/coldtrack-ort). Alasannya:
onnxruntime-gpu 1.31 dibangun untuk CUDA 13, sedangkan PyTorch cu128 memakai CUDA 12; memasang
pustaka CUDA 13 di venv torch menimpa libcudnn.so.9 milik torch (terbukti 2026-10-10). Dua
tumpukan CUDA dipisah per venv supaya keduanya tetap bersih.

  python bench/ort_probe.py --providers CUDAExecutionProvider,CPUExecutionProvider MODEL.onnx ...

Keluaran: satu baris JSON di stdout.
"""

import argparse
import json

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--providers", required=True)
    ap.add_argument("--windows", help="npz jendela (kunci X) sebagai masukan uji")
    ap.add_argument("models", nargs="+")
    a = ap.parse_args()

    import onnxruntime as ort

    minta = a.providers.split(",")
    if "CUDAExecutionProvider" in minta and hasattr(ort, "preload_dlls"):
        # muat pustaka CUDA/cuDNN dari paket pip nvidia-* (tanpa LD_LIBRARY_PATH)
        ort.preload_dlls(cuda=True, cudnn=True, msvc=False)

    out = {"onnxruntime": ort.__version__, "available_providers": ort.get_available_providers(), "models": {}}
    # Masukan: jendela val ASLI bila ada. Masukan acak menyesatkan: TTB = exp(x)-1 meledak ke ~1e16
    # sehingga selisih absolut CUDA vs CPU terlihat 1e12 padahal relatifnya 4e-4 (temuan 2026-10-10).
    if a.windows:
        x_uji = np.load(a.windows)["X"][:4096].astype(np.float32)
        out["masukan"] = f"{a.windows}[:4096]"
    else:
        x_uji = np.random.default_rng(0).normal(size=(32, 60, 12)).astype(np.float32)
        out["masukan"] = "acak N(0,1) 32x60x12"
    # TF32 dimatikan untuk cek paritas: dengan TF32 bawaan, selisih forecast GRU ~4e-3 C; tanpa TF32 ~2e-6.
    cuda_opts = {"use_tf32": 0}
    out["cuda_provider_options"] = cuda_opts
    prov = [(p, cuda_opts) if p == "CUDAExecutionProvider" else p for p in minta]
    for path in a.models:
        r = {"diminta": minta}
        try:
            cpu = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
            inp = cpu.get_inputs()[0]
            x = x_uji
            ref = cpu.run(None, {inp.name: x})
            sess = ort.InferenceSession(path, providers=prov)
            r["aktif"] = sess.get_providers()
            r["cuda_ep_aktif"] = r["aktif"][0] == "CUDAExecutionProvider"
            got = sess.run(None, {inp.name: x})
            # per keluaran: selisih maks + porsi sampel yang berbeda > 1e-3. Model pohon (XGB TTB) wajar
            # punya porsi besar: agregat float dihitung beda urutan di GPU sehingga melewati ambang split.
            r["paritas_vs_cpu_ep"] = {
                o.name: {"maxabs": float(np.abs(p - q).max()),
                         "porsi_beda_gt_1e-3": float(np.mean(np.abs(p - q).reshape(len(p), -1).max(1) > 1e-3))}
                for o, p, q in zip(sess.get_outputs(), map(np.asarray, got), map(np.asarray, ref))}
            r["ok"] = True
        except Exception as e:  # noqa: BLE001 -- EP gagal dimuat adalah temuan, dicatat apa adanya
            r["ok"] = False
            r["error"] = f"{type(e).__name__}: {e}"
        out["models"][path] = r
    print(json.dumps(out))


if __name__ == "__main__":
    main()
