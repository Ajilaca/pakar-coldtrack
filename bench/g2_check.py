"""Gerbang G2 (paritas kualitas): speedup yang mengorbankan kualitas TIDAK dilaporkan sebagai speedup.

  python -m bench.g2_check --cpu-tag g16-cpu --gpu-tag g16-gpu

Kriteria DITETAPKAN SEBELUM run penuh W1/W2/W7 (commit berkas ini mendahului hasilnya):

W1 (GRU, 5 seed): untuk tiap metrik, |mean_A - mean_B| <= max(rentang_A, rentang_B), rentang =
  maks - min antar-seed. Pasangan yang dibandingkan:
  - config sama di tag CPU vs tag GPU (b256/b1024/b4096 fp32, b1024 resident)
  - varian khusus GPU (AMP, pin, workers) vs config fp32 berbatch sama di tag CPU (acuan kualitas)
W2 (XGBoost, deterministik -> rentang 0): selisih relatif tiap metrik <= 2 %.
W7 (inferensi ONNX, deterministik): selisih relatif MAE TTB dan MAE forecast <= 2 %; selisih
  akurasi mode <= 0,005 (absolut). Pembanding: CPU EP pada batch yang sama.

Catatan transparansi: ambang 2 % untuk W2/W7 dipilih setelah melihat hasil B1 dan uji cepat
(selisih yang teramati jauh di bawahnya); ambang W1 mengikuti dokumen rencana (rentang antar-seed).

Hasil: bench/results/G2.json
"""

import argparse
import json

import numpy as np

from bench.common import RESULTS_DIR, now_iso, rel, write_json

W1_METRIK = ["forecast_t15_mae_c", "forecast_t30_mae_c", "forecast_t60_mae_c", "macro_f1", "akurasi",
             "ttb_mae_menit", "anomali_pr_auc"]
W1_ACUAN_CPU = {   # varian khusus GPU -> config CPU acuan kualitas
    "b256_bf16": "b256_fp32", "b1024_bf16": "b1024_fp32", "b4096_bf16": "b4096_fp32",
    "b256_fp16": "b256_fp32", "b1024_fp16": "b1024_fp32", "b4096_fp16": "b4096_fp32",
    "b1024_fp32_pin": "b1024_fp32", "b1024_fp32_w2pin": "b1024_fp32",
}
REL_TOL = 0.02
AKURASI_TOL = 0.005


def runs(tag, workload, cid):
    files = sorted((RESULTS_DIR / tag / workload / cid).glob("run_*.json"))
    out = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    return [r for r in out if not r["pemanasan"]], [rel(f) for f in files]


def cek_w1(cpu, gpu):
    hasil = {}
    configs = sorted({p.name for p in (RESULTS_DIR / gpu / "W1").glob("*") if p.is_dir()})
    for cid in configs:
        g_runs, g_src = runs(gpu, "W1", cid)
        acuan = W1_ACUAN_CPU.get(cid, cid)
        c_runs, c_src = runs(cpu, "W1", acuan)
        if not g_runs or not c_runs:
            continue
        per = {}
        for m in W1_METRIK:
            g = np.array([r["metrik_val"][m] for r in g_runs])
            c = np.array([r["metrik_val"][m] for r in c_runs])
            selisih = float(g.mean() - c.mean())
            batas = float(max(np.ptp(g), np.ptp(c)))
            per[m] = {"mean_gpu": float(g.mean()), "mean_cpu": float(c.mean()), "selisih": selisih,
                      "batas_rentang_antar_seed": batas, "setara": abs(selisih) <= batas}
        hasil[cid] = {"acuan_cpu": f"{cpu}/W1/{acuan}", "n_seed": [len(g_runs), len(c_runs)],
                      "setara": all(v["setara"] for v in per.values()), "metrik": per,
                      "sumber": g_src + c_src}
    return hasil


def _rel(a, b):
    return abs(a - b) / max(abs(b), 1e-12)


def cek_deterministik(cpu, gpu, workload, pasangan, ambil):
    hasil = {}
    for cid_g, cid_c in pasangan:
        g_runs, g_src = runs(gpu, workload, cid_g)
        c_runs, c_src = runs(cpu, workload, cid_c)
        if not g_runs or not c_runs:
            continue
        g, c = ambil(g_runs[0]), ambil(c_runs[0])
        per = {}
        for m in g:
            if m.startswith("akurasi"):
                ok = abs(g[m] - c[m]) <= AKURASI_TOL
                per[m] = {"gpu": g[m], "cpu": c[m], "selisih_abs": g[m] - c[m], "setara": ok}
            else:
                r = _rel(g[m], c[m])
                per[m] = {"gpu": g[m], "cpu": c[m], "selisih_rel": r, "setara": r <= REL_TOL}
        hasil[cid_g] = {"acuan_cpu": f"{cpu}/{workload}/{cid_c}", "setara": all(v["setara"] for v in per.values()),
                        "metrik": per, "sumber": g_src + c_src}
    return hasil


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cpu-tag", default="g16-cpu")
    ap.add_argument("--gpu-tag", default="g16-gpu")
    a = ap.parse_args(argv)

    w7_pasangan = [(f"{m}_{v}_b{b}", f"{m}_cpu_b{b}") for m, vs in [("gru", ["cuda", "cuda_notf32"]),
                   ("xgb_ttb", ["cuda"])] for v in vs for b in [1, 32, 256, 1024]]
    hasil = {
        "waktu_utc": now_iso(), "cpu_tag": a.cpu_tag, "gpu_tag": a.gpu_tag,
        "kriteria": {"W1": "|mean_gpu - mean_cpu| <= max(rentang antar-seed)", "W2_W7_rel": REL_TOL,
                     "W7_akurasi_abs": AKURASI_TOL},
        "W1": cek_w1(a.cpu_tag, a.gpu_tag),
        "W2": cek_deterministik(a.cpu_tag, a.gpu_tag, "W2", [("cuda_hist", "cpu_hist")],
                                lambda r: {k: v for k, v in r["metrik_val"].items() if k != "n_val"}),
        "W7": cek_deterministik(a.cpu_tag, a.gpu_tag, "W7", w7_pasangan, lambda r: r["inferensi"]["kualitas_val"]),
    }
    semua = [h["setara"] for w in ("W1", "W2", "W7") for h in hasil[w].values()]
    hasil["_ringkas"] = {"n_config": len(semua), "n_setara": sum(semua),
                         "tidak_setara": [f"{w}/{c}" for w in ("W1", "W2", "W7") for c, h in hasil[w].items()
                                          if not h["setara"]]}
    path = write_json(RESULTS_DIR / "G2.json", hasil)
    for w in ("W1", "W2", "W7"):
        for cid, h in hasil[w].items():
            gagal = [m for m, v in h["metrik"].items() if not v["setara"]]
            print(f"{w} {cid:22s} {'SETARA' if h['setara'] else 'TIDAK SETARA ' + str(gagal)}")
    print(f"\nG2: {hasil['_ringkas']['n_setara']}/{hasil['_ringkas']['n_config']} config setara -> {rel(path)}")


if __name__ == "__main__":
    main()
