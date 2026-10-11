"""Banding checkpoint-2 (backend saat ini) vs v3 (coldtrack_b3.onnx) vs v2 (proposal) pada jendela SAMA.

  python -m bench.b7_banding_model [--split val]

- Jendela dan label = eval/common.eval_rows (seleksi jendela yang sama dengan suite eval backend).
- checkpoint-2 dijalankan seperti terpasang: inference_engine.analyze_trip (engine + GRU + aturan).
- v2/v3: ONNX pada jendela 60 x 12 fitur mentah (urutan FEATURE_COLUMNS, reefer_duration dihitung
  ulang per jendela seperti ml/preprocess/build_windows).
- Pemetaan kejadian = eval/common.EVENT_OF_MODE: A1 -> pintu, A7 -> kejut ambien, A5/A6 -> sensor.
  Untuk v2/v3: P(pintu) = P(A1), P(kejut) = P(A7), P(sensor) = P(masalah_sensor); label = argmax 7 kelas.

Bawaan split VAL: split test sudah dipakai sekali untuk v3 (G3), jadi tidak dipakai lagi di sini.
Bias yang harus disebut: v3 dipilih di val (sedikit optimistis); v4 out-of-distribution untuk
checkpoint-2 (dilatih di simulator lain).

Hasil: bench/results/g16-cpu/B7/banding_model_<split>.json
"""

import argparse
import time

import numpy as np
import pandas as pd

from bench.common import RESULTS_DIR, ROOT, git_info, now_iso, rel, write_json

MODEL_ONNX = {"v2_proposal": "ml/reports/coldtrack.onnx", "v3_b3": "ml/reports/coldtrack_b3.onnx"}
KELAS_EVENT = {"door": "A1", "shock": "A7", "sensor": "masalah_sensor"}


def jendela_12fitur(g, ts):
    from ml.preprocess.build_windows import WINDOW_SIZE, hitung_ulang_reefer_duration
    from ml.tests.test_data_contract import FEATURE_COLUMNS

    feats = g[FEATURE_COLUMNS].ffill().bfill().to_numpy(np.float32)
    return np.stack([hitung_ulang_reefer_duration(feats[t - WINDOW_SIZE + 1 : t + 1]) for t in ts])


def auc(y, s):
    from sklearn.metrics import roc_auc_score

    y = np.asarray(y, bool)
    return float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else None


def main(argv=None):
    import onnxruntime as ort
    from sklearn.metrics import f1_score

    from eval import common as ec
    from ml.preprocess.build_windows import CLASS_TO_IDX, FAILURE_CLASSES, MODE_MAPPING

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--split", default="val", choices=["val", "train"])
    a = ap.parse_args(argv)

    df = pd.read_parquet(ec.DATA_PATH)
    df = df[df["split"] == a.split]
    trips = {tid: g.sort_values("minute").reset_index(drop=True) for tid, g in df.groupby("trip_id")}
    t0 = time.perf_counter()
    D = ec.eval_rows(trips)  # keluaran checkpoint-2 terpasang + kebenaran
    t_ckpt2 = time.perf_counter() - t0

    sesi = {k: ort.InferenceSession(str(ROOT / p), providers=["CPUExecutionProvider"]) for k, p in MODEL_ONNX.items()}
    keluaran = {k: {"fc": [], "prob": []} for k in sesi}
    for tid, idx in D.groupby("trip_id").groups.items():
        X = jendela_12fitur(trips[tid], D.loc[idx, "t"].to_numpy())
        for k, s in sesi.items():
            fc, prob, _ = s.run(None, {"window": X})
            keluaran[k]["fc"].append(pd.DataFrame(fc, index=idx))
            keluaran[k]["prob"].append(pd.DataFrame(prob, index=idx, columns=FAILURE_CLASSES))
    keluaran = {k: {n: pd.concat(v).loc[D.index] for n, v in o.items()} for k, o in keluaran.items()}

    healthy = D.raw_mode == "A0"
    y7 = D.raw_mode.map(lambda m: CLASS_TO_IDX[MODE_MAPPING[m]])
    hasil = {
        "split": a.split,
        "n_jendela": len(D),
        "n_trip": int(D.trip_id.nunique()),
        "waktu_utc": now_iso(),
        "git": git_info(),
        "detik_ckpt2_analyze": t_ckpt2,
        "bias": [
            "v3 dipilih di split val (sedikit optimistis)",
            "v4 out-of-distribution untuk checkpoint-2 (dilatih di simulator garis checkpoint-2)",
        ],
        "catatan_target_forecast": "checkpoint-2 memprediksi suhu muatan; di v4 sensor == muatan (eval/common.py)",
        "model": {},
    }

    def forecast(fc):
        return {
            f"mae_t{h}": float((fc[:, i] - D[f"y{h}"].to_numpy()).__abs__().mean())
            for i, h in enumerate((15, 30, 60))
        }

    # checkpoint-2
    c2 = {"forecast": forecast(D[["t15", "t30", "t60"]].to_numpy()), "event": {}}
    for e in ec.EVENTS:
        pos = D.event == e
        sel = pos | healthy
        c2["event"][e] = {
            "n_pos": int(pos.sum()),
            "auroc_vs_sehat": auc(pos[sel], D[f"ev_{e}"][sel]),
            "recall_label": float((D.label[pos] == ec.EVENT_LABEL[e]).mean()),
        }
    c2["sehat_dilabel_gangguan"] = float((D.label[healthy] != "normal_sehat").mean())
    hasil["model"]["checkpoint2_backend"] = c2

    for k, o in keluaran.items():
        prob, pred = o["prob"], o["prob"].to_numpy().argmax(1)
        r = {"forecast": forecast(o["fc"].to_numpy()), "event": {}}
        for e, kelas in KELAS_EVENT.items():
            pos = D.event == e
            sel = pos | healthy
            r["event"][e] = {
                "n_pos": int(pos.sum()),
                "auroc_vs_sehat": auc(pos[sel], prob[kelas][sel]),
                "recall_label": float((pred[pos.to_numpy()] == CLASS_TO_IDX[kelas]).mean()),
            }
        r["sehat_dilabel_gangguan"] = float((pred[healthy.to_numpy()] != 0).mean())
        r["macro_f1_7kelas"] = float(f1_score(y7, pred, average="macro"))
        hasil["model"][k] = r

    path = write_json(RESULTS_DIR / "g16-cpu" / "B7" / f"banding_model_{a.split}.json", hasil)
    print(f"{len(D)} jendela, {hasil['n_trip']} trip ({a.split})")
    for k, r in hasil["model"].items():
        ev = " ".join(f"{e}:AUC {v['auroc_vs_sehat']:.3f}/rec {v['recall_label']:.2f}" for e, v in r["event"].items())
        print(
            f"{k:20s} MAE t30 {r['forecast']['mae_t30']:.3f} | {ev} | sehat->gangguan {r['sehat_dilabel_gangguan']:.3f}"
        )
    print("Tersimpan:", rel(path))


if __name__ == "__main__":
    main()
