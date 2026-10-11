"""G4 -- evaluasi mote TEST, sekali per model, dengan kriteria pra-registrasi
(bench/results/keputusan/G4_kriteria.json + G4_definisi.json). Ambang dan penghalusan berasal dari
meta model (dipilih di mote val), tidak disetel ulang di sini.

  python -m ml.sensor_health.test_once --model berkeley_v1_kesehatan

Akses dicatat dulu di bench/results/test_access_log.json; id yang sama ditolak bila diulang.
Hasil: bench/results/test/b4_<model>.json
"""

import argparse
import json
import sys

import numpy as np

from ml.sensor_health import evaluate as ev
from ml.sensor_health.train import ART, LABEL


def main(argv=None):
    from bench.common import (
        RESULTS_DIR,
        git_info,
        now_iso,
        rel,
        sha256_file,
        write_json,
    )

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default="berkeley_v1_kesehatan")
    a = ap.parse_args(argv)

    log_path = RESULTS_DIR / "test_access_log.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
    tid = f"b4_{a.model}"
    if any(e["id"] == tid for e in log):
        sys.exit(f"DITOLAK: '{tid}' sudah pernah dievaluasi di mote test.")
    model_path = ART / f"{a.model}.json"
    meta = json.loads((ART / f"{a.model}.meta.json").read_text(encoding="utf-8"))
    entri = {"id": tid, "model": rel(model_path), "sha256_model": sha256_file(model_path), "waktu_utc": now_iso(),
             "git": git_info(), "split": "mote test (B4)"}
    log_path.write_text(json.dumps(log + [entri], indent=2, ensure_ascii=False), encoding="utf-8")

    import xgboost as xgb

    df = ev.muat()
    te = df[df["split"] == "test"]
    m = xgb.XGBClassifier()
    m.load_model(model_path)
    skor = ev.haluskan(te, m.predict_proba(te[meta["fitur"]].to_numpy(np.float32))[:, 1], meta["penghalusan"])
    v0 = ev.ringkas(te, te["skor_v0"], 1.0, LABEL)
    v1 = ev.ringkas(te, skor, meta["ambang"], LABEL)

    k1 = v1["pr_auc"] >= v0["pr_auc"] + 0.05
    k2 = (v1["alarm_palsu_per_mote_hari"] <= v0["alarm_palsu_per_mote_hari"]
          and v1["recall_jendela"] >= v0["recall_jendela"])
    hasil = entri | {"label": LABEL, "ambang_dari_val": meta["ambang"], "penghalusan_dari_val": meta["penghalusan"],
                     "v0": v0, "v1": v1,
                     "kriteria": {"1_pr_auc_v1_ge_v0_plus_0.05": bool(k1),
                                  "2_alarm_palsu_le_v0_pada_recall_ge_v0": bool(k2), "G4_lulus": bool(k1 and k2)}}
    path = write_json(RESULTS_DIR / "test" / f"{tid}.json", hasil)
    for n, r in (("v0", v0), ("v1", v1)):
        print(f"{n}: PR-AUC {r['pr_auc']:.4f} recall {r['recall_jendela']:.3f} "
              f"alarm palsu/mote-hari {r['alarm_palsu_per_mote_hari']:.3f} recall kejadian {r['recall_kejadian']:.2f} "
              f"lead time median {r['lead_time_median_menit']} menit")
    print("kriteria:", hasil["kriteria"], "\nTersimpan:", rel(path))


if __name__ == "__main__":
    main()
