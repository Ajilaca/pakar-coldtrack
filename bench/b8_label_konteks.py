"""B8 -- label v5 (A1/A7 sementara) dan fitur konteks trip, split VAL saja.

Langkah (lihat bench/b8_lib.py untuk definisi):
  v3     skor ulang model produksi backend/models/coldtrack_v3.onnx dengan label lama dan v5 (tanpa latih ulang)
  xgb    XGBoost 72 statistik jendela: label lama/v5 x tanpa/dengan konteks, ukuran baseline dan ukuran chip
  gru    GRU konfigurasi v3 (labels_b3.json) dilatih ulang dengan label v5, tanpa/dengan konteks
  ringkas  gabungkan hasil ke satu tabel

  python -m bench.b8_label_konteks v3
  python -m bench.b8_label_konteks xgb --seeds 1000 1001 1002
  python -m bench.b8_label_konteks gru --konteks --seed 1000      # berhenti dini, --patience 8

Hasil: bench/results/lokal-cpu/B8/. Split test tidak disentuh.
"""

import argparse
import json
import time

import numpy as np

from bench.common import RESULTS_DIR, ROOT, git_info, now_iso, write_json

OUT = RESULTS_DIR / "lokal-cpu" / "B8"
UKURAN = {"baseline": {"n_estimators": 300, "max_depth": 6}, "chip": {"n_estimators": 60, "max_depth": 4}}


def metrik_kelas(y, proba):
    from sklearn.metrics import (
        average_precision_score,
        f1_score,
        precision_recall_fscore_support,
    )

    from ml.preprocess.build_windows import FAILURE_CLASSES

    pred = proba.argmax(1)
    p, r, f, s = precision_recall_fscore_support(y, pred, labels=range(len(FAILURE_CLASSES)), zero_division=0)
    return {
        "macro_f1": float(f1_score(y, pred, average="macro")),
        "akurasi": float((pred == y).mean()),
        "anomali_pr_auc": float(average_precision_score((y != 0).astype(int), 1 - proba[:, 0])),
        "per_kelas": {c: {"presisi": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "n": int(s[i])}
                      for i, c in enumerate(FAILURE_CLASSES)},
    }


def cmd_v3(_):
    import onnxruntime as ort

    from bench import b8_lib as b8

    path = ROOT / "backend" / "models" / "coldtrack_v3.onnx"
    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    X = np.load(ROOT / "data/processed/windows/windows_val.npz")["X"]
    nama = [o.name for o in sess.get_outputs()]
    keluar = dict(zip(nama, sess.run(None, {sess.get_inputs()[0].name: X})))
    proba = keluar["failure_prob"]
    d = b8.muat("val")
    hasil = {"waktu_utc": now_iso(), "git": git_info(), "model": str(path.relative_to(ROOT)), "split": "val",
             "catatan": "model v3 produksi dilatih dengan label lama; tidak dilatih ulang",
             "label_lama": metrik_kelas(d["y_lama"], proba), "label_v5": metrik_kelas(d["y_baru"], proba)}
    for k in ("label_lama", "label_v5"):
        print(f"{k:10s} macro F1 {hasil[k]['macro_f1']:.3f}  PR-AUC {hasil[k]['anomali_pr_auc']:.3f}")
    print("Tersimpan:", write_json(OUT / "v3_skor_ulang.json", hasil))


def _fitur_xgb(split, konteks):
    from bench import b8_lib as b8
    from ml.baselines import aggregate

    X = aggregate(np.load(ROOT / f"data/processed/windows/windows_{split}.npz")["X"])
    d = b8.muat(split)
    if konteks:
        X = np.concatenate([X, d["ctx"]], axis=1)
    return X, d


def cmd_xgb(a):
    import xgboost as xgb

    from ml.baselines import XGB_PARAMS
    from ml.preprocess.build_windows import FAILURE_CLASSES

    hasil = {"waktu_utc": now_iso(), "git": git_info(), "split": "val", "ukuran": UKURAN, "run": []}
    for ukuran in a.ukuran:
        for konteks in (False, True):
            Xtr, dtr = _fitur_xgb("train", konteks)
            Xva, dva = _fitur_xgb("val", konteks)
            for label in ("y_lama", "y_baru"):
                for seed in a.seeds:
                    params = {**XGB_PARAMS, **UKURAN[ukuran], "random_state": seed}
                    clf = xgb.XGBClassifier(objective="multi:softprob", num_class=len(FAILURE_CLASSES),
                                            disable_default_eval_metric=True, **params)
                    t0 = time.perf_counter()
                    clf.fit(Xtr, dtr[label])
                    m = metrik_kelas(dva[label], clf.predict_proba(Xva))
                    m.update(ukuran=ukuran, konteks=konteks, label="lama" if label == "y_lama" else "v5",
                             seed=seed, detik_latih=time.perf_counter() - t0)
                    hasil["run"].append(m)
                    print(f"{ukuran:8s} konteks={konteks!s:5s} label={m['label']:4s} seed={seed} "
                          f"F1 {m['macro_f1']:.3f} PR-AUC {m['anomali_pr_auc']:.3f} ({m['detik_latih']:.0f} s)")
    print("Tersimpan:", write_json(OUT / "xgb.json", hasil))


def cmd_gru(a):
    import torch

    from bench import b8_gru
    from bench import b8_lib as b8

    torch.set_num_threads(a.threads)
    cfg = json.loads((ROOT / "ml/reports/labels_b3.json").read_text(encoding="utf-8"))["konfigurasi"]
    cfg["n_epochs"] = a.epochs or cfg["n_epochs"]
    cfg["patience"] = a.patience
    data = b8_gru.siapkan(b8.muat("train"), b8.muat("val"), konteks=a.konteks, label="y_baru")
    model, info = b8_gru.latih(data, cfg, a.seed, log=print)
    m = b8_gru.evaluasi(model, data)
    nama = f"gru_v5_{'konteks' if a.konteks else 'tanpa_konteks'}_seed{a.seed}"
    torch.save({"state": model.state_dict(), "mean": data["mean"], "std": data["std"],
                "ctx_mean": data["ctx_mean"], "ctx_std": data["ctx_std"], "cfg": cfg, "konteks": a.konteks},
               ROOT / "data" / "processed" / "windows" / f"{nama}.pt")
    hasil = {"waktu_utc": now_iso(), "git": git_info(), "split": "val", "label": "v5", "konteks": a.konteks,
             "seed": a.seed, "konfigurasi": cfg, "latih": info, **m}
    print(f"macro F1 {m['macro_f1']:.3f}  PR-AUC {m['anomali_pr_auc']:.3f}  forecast t+30 {m['forecast_t30_mae_c']:.3f} C")
    print("Tersimpan:", write_json(OUT / f"{nama}.json", hasil))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("v3")
    p = sub.add_parser("xgb")
    p.add_argument("--seeds", type=int, nargs="+", default=[1000])
    p.add_argument("--ukuran", nargs="+", default=["baseline", "chip"], choices=list(UKURAN))
    p = sub.add_parser("gru")
    p.add_argument("--konteks", action="store_true")
    p.add_argument("--seed", type=int, default=1000)
    p.add_argument("--epochs", type=int, default=None)
    p.add_argument("--patience", type=int, default=8, help="berhenti bila val loss tidak membaik sekian epoch")
    p.add_argument("--threads", type=int, default=6)
    a = ap.parse_args()
    {"v3": cmd_v3, "xgb": cmd_xgb, "gru": cmd_gru}[a.cmd](a)


if __name__ == "__main__":
    main()
