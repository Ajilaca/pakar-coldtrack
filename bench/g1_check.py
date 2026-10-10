"""Gerbang G1 (reproduksi): angka acuan berada dalam rata-rata +/- 2 SD dari lima seed?

  python -m bench.g1_check --tag g16-cpu

Acuan DIBACA dari berkas repo, tidak diketik ulang:
- GRU      : ml/reports/metrics.json -> metrik_val_pembanding (model asli, split val)
- XGBoost  : ml/reports/baseline_metrics.json (split val)
Angka tabel proposal berasal dari split TEST, jadi tidak dipakai untuk G1 (B1 tidak menyentuh
test). TTB XGBoost <= 30 menit (7,08) hanya ada untuk test -> dicatat "tidak ada acuan val".

Hasil: bench/results/<tag>/B1/G1.json
"""

import argparse
import json

import numpy as np

from bench.common import RESULTS_DIR, ROOT, now_iso, rel, write_json


def acuan():
    with open(ROOT / "ml/reports/metrics.json", encoding="utf-8") as f:
        gru = json.load(f)["metrik_val_pembanding"]
    with open(ROOT / "ml/reports/baseline_metrics.json", encoding="utf-8") as f:
        base = json.load(f)
    src_gru = "ml/reports/metrics.json:metrik_val_pembanding"
    src_base = "ml/reports/baseline_metrics.json"
    return {
        "gru": {k: (gru[k], src_gru) for k in
                ["forecast_t15_mae_c", "forecast_t30_mae_c", "forecast_t60_mae_c", "macro_f1",
                 "akurasi", "ttb_mae_menit", "anomali_pr_auc"]},
        "xgb_ttb": {
            "ttb_mae_semua_menit": (base["ttb_mae_menit"]["xgboost"], src_base),
            "ttb_mae_le30_menit": (None, "tidak ada acuan val (7,08 hanya di split test)"),
            "ttb_mae_le10_menit": (None, "tidak ada acuan val"),
        },
        "xgb_clf": {
            "macro_f1": (base["failure_mode"]["xgboost_macro_f1"], src_base),
            "akurasi": (base["failure_mode"]["xgboost_akurasi"], src_base),
            "anomali_pr_auc": (base["anomali_pr_auc"]["xgboost"], src_base),
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", required=True)
    a = ap.parse_args(argv)

    b1 = RESULTS_DIR / a.tag / "B1"
    hasil, baris = {}, []
    for model, refs in acuan().items():
        files = sorted(b1.glob(f"{model}_seed*.json"))
        if not files:
            continue
        runs = [json.loads(f.read_text(encoding="utf-8")) for f in files]
        hasil[model] = {"sumber": [rel(f) for f in files], "metrik": {}}
        for metrik, (ref, src) in refs.items():
            v = np.array([r["metrik_val"][metrik] for r in runs], dtype=float)
            mu, sd = float(v.mean()), float(v.std(ddof=1)) if len(v) > 1 else float("nan")
            lo, hi = mu - 2 * sd, mu + 2 * sd
            lulus = None if ref is None else bool(lo <= ref <= hi)
            hasil[model]["metrik"][metrik] = {
                "nilai_per_seed": v.tolist(), "mean": mu, "sd": sd, "rentang_2sd": [lo, hi],
                "acuan": ref, "sumber_acuan": src, "lulus": lulus,
            }
            status = "tanpa acuan" if lulus is None else ("LULUS" if lulus else "TIDAK")
            ref_s = "-" if ref is None else f"{ref:.4f}"
            baris.append(f"| {model} | {metrik} | {mu:.4f} ± {sd:.4f} | [{lo:.4f}, {hi:.4f}] | {ref_s} | {status} |")

    nilai = [m["lulus"] for h in hasil.values() for m in h["metrik"].values() if m["lulus"] is not None]
    hasil["_ringkas"] = {"tag": a.tag, "waktu_utc": now_iso(), "n_dicek": len(nilai),
                         "n_lulus": sum(nilai), "G1_lulus": bool(nilai) and all(nilai)}
    path = write_json(b1 / "G1.json", hasil)

    print("| model | metrik | mean ± sd (5 seed) | rentang ±2sd | acuan val | G1 |")
    print("|---|---|---|---|---|---|")
    print("\n".join(baris))
    print(f"\nG1: {hasil['_ringkas']['n_lulus']}/{hasil['_ringkas']['n_dicek']} lulus -> {path}")


if __name__ == "__main__":
    main()
