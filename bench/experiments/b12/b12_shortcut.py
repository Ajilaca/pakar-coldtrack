"""B12 -- seberapa besar GRU v5 bergantung pada satu sinyal? Uji gangguan masukan, split VAL saja.

Model produksi backend/models/coldtrack_v5.onnx dijalankan ulang pada jendela val dengan SATU sinyal diubah,
lalu F1 per kelas (label v5) dibandingkan dengan masukan asli. Tidak ada latih ulang, split test tidak disentuh.
F1 yang jatuh jauh berarti kelas itu bergantung pada sinyal tersebut (calon jalan pintas simulator); F1 yang
bertahan berarti model juga membaca pola lain. Ini mengukur ketergantungan, bukan kebenaran di data nyata.

  python -m bench.experiments.b12.b12_shortcut

Hasil: bench/results/lokal-cpu/B12/shortcut.json
"""

import time

import numpy as np

from bench.core.common import RESULTS_DIR, ROOT, git_info, now_iso, rel, write_json

ONNX = ROOT / "backend" / "models" / "coldtrack_v5.onnx"
CKPT = ROOT / "data" / "processed" / "windows" / "gru_v5_konteks_seed1000.pt"
OUT = RESULTS_DIR / "lokal-cpu" / "B12" / "shortcut.json"
SEED = 1000


def uji_gangguan(onnx_path, ctx_mean, log=print):
    """Jalankan semua uji gangguan pada `onnx_path` (masukan window + konteks). ctx_mean = rata-rata konteks train."""
    import onnxruntime as ort

    from bench.experiments.b8 import b8_lib as b8
    from bench.experiments.b8.b8_label_konteks import metrik_kelas
    from ml.preprocess.build_windows import FAILURE_CLASSES
    from ml.tests.test_data_contract import FEATURE_COLUMNS

    ix = {c: i for i, c in enumerate(FEATURE_COLUMNS)}
    kx = {c: i for i, c in enumerate(b8.KONTEKS)}
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    X0 = np.load(b8.path_npz("val"))["X"].astype(np.float32)
    d = b8.muat("val")
    y, C0 = d["y_baru"], d["ctx"].astype(np.float32)
    ctx_mean = np.asarray(ctx_mean, dtype=np.float32)
    rng = np.random.default_rng(SEED)
    posisi = np.arange(1, X0.shape[1] + 1, dtype=np.float32)[None, :]

    def jalankan(X, C):
        return np.concatenate([sess.run(None, {"window": X[i:i + 4096], "konteks": C[i:i + 4096]})[1]
                               for i in range(0, len(X), 4096)])

    def reefer(X, nyala):
        """reefer_on diganti, reefer_duration_min dihitung ulang dari awal jendela seperti build_windows."""
        X[:, :, ix["reefer_on"]] = nyala
        run = np.zeros_like(nyala)
        for t in range(nyala.shape[1]):
            run[:, t] = (run[:, t - 1] + 1) * nyala[:, t] if t else nyala[:, t]
        X[:, :, ix["reefer_duration_min"]] = np.minimum(run, posisi)
        return X

    def derau_suhu(X, sd):
        e = rng.normal(0, sd, X.shape[:2]).astype(np.float32)
        X[:, :, ix["temp_c"]] += e
        X[:, :, ix["delta_temp"]] = np.diff(X[:, :, ix["temp_c"]], axis=1, prepend=X[:, :1, ix["temp_c"]])
        X[:, 0, ix["delta_temp"]] = X0[:, 0, ix["delta_temp"]] + e[:, 0]
        X[:, :, ix["delta_ambient"]] = X[:, :, ix["temp_c"]] - X[:, :, ix["ambient_c"]]
        return X

    def isi_rata(C, kolom):
        for k in kolom:
            C[:, kx[k]] = ctx_mean[kx[k]]
        return C

    perm = rng.permutation(len(X0))
    uji = {
        "asli": ("tanpa perubahan", lambda X, C: (X, C)),
        "reefer_selalu_nyala": ("reefer_on = 1 di semua menit", lambda X, C: (reefer(X, np.ones(X.shape[:2], np.float32)), C)),
        "reefer_diacak": ("kanal reefer_on ditukar antar jendela", lambda X, C: (reefer(X, X0[perm][:, :, ix["reefer_on"]].copy()), C)),
        "pintu_diacak": ("kanal door_open ditukar antar jendela",
                         lambda X, C: (X.__setitem__((slice(None), slice(None), ix["door_open"]), X0[perm][:, :, ix["door_open"]]) or X, C)),
        "pintu_selalu_tutup": ("door_open = 0 di semua menit",
                               lambda X, C: (X.__setitem__((slice(None), slice(None), ix["door_open"]), 0.0) or X, C)),
        "tanpa_suhu_awal": ("suhu_awal_muat dan kini_minus_awal = rata-rata train",
                            lambda X, C: (X, isi_rata(C, ["suhu_awal_muat", "kini_minus_awal"]))),
        "tanpa_konteks": ("6 fitur konteks = rata-rata train", lambda X, C: (X, isi_rata(C, b8.KONTEKS))),
        "derau_suhu_0.1": ("derau Gaussian 0,1 C pada temp_c", lambda X, C: (derau_suhu(X, 0.1), C)),
        "derau_suhu_0.3": ("derau Gaussian 0,3 C pada temp_c", lambda X, C: (derau_suhu(X, 0.3), C)),
        "derau_suhu_0.5": ("derau Gaussian 0,5 C pada temp_c", lambda X, C: (derau_suhu(X, 0.5), C)),
    }

    hasil = {"model": rel(onnx_path), "split": "val", "label": "v5", "n_jendela": len(y),
             "n_per_kelas": {c: int((y == i).sum()) for i, c in enumerate(FAILURE_CLASSES)}, "uji": {}}
    for nama, (ket, ubah) in uji.items():
        X, C = ubah(X0.copy(), C0.copy())
        prob = jalankan(X, C)
        m = metrik_kelas(y, prob)
        pred = prob.argmax(1)
        ke = {c: {FAILURE_CLASSES[j]: round(float(np.mean(pred[y == i] == j)), 4)
                  for j in np.unique(pred[y == i])} for i, c in enumerate(FAILURE_CLASSES)}
        hasil["uji"][nama] = {"keterangan": ket, "macro_f1": m["macro_f1"],
                              "f1": {c: v["f1"] for c, v in m["per_kelas"].items()}, "prediksi_per_kelas": ke}
        log(f"{nama:22s} macro {m['macro_f1']:.3f} | "
              + " ".join(f"{c[:6]}:{v['f1']:.2f}" for c, v in m["per_kelas"].items()), flush=True)
    return hasil


def main():
    import torch

    t0 = time.perf_counter()
    ctx_mean = torch.load(CKPT, weights_only=False)["ctx_mean"]          # rata-rata konteks train
    hasil = {"waktu_utc": now_iso(), "git": git_info(), **uji_gangguan(ONNX, ctx_mean)}
    hasil["detik"] = round(time.perf_counter() - t0, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    print("Tersimpan:", rel(write_json(OUT, hasil)))


if __name__ == "__main__":
    main()
