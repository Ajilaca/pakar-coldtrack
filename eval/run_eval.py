"""ColdTrack AI evaluation suite -- scores the DEPLOYED system on the held-out test split.

Usage:  python -m eval.run_eval [--tag baseline] [--api-stride 3]
Output: eval/results/<tag>_results.json  (+ confusion matrix PNG)

Groups
  G1 forecast          MAE per horizon / failure mode / cargo type
  G2 classification    per-class P/R/F1 with trip counts, bootstrap CI by trip
  G3 imminent breach   what the deployed system SHOWS when true TTB <= 30 min
  G4 robustness        sensor noise, timezone shift, stuck sensor
  G5 end-to-end API    real FastAPI endpoint: status safety, TTB shown, parity with raw ONNX
"""

import argparse
import json
import time

import numpy as np
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score

from eval.common import (
    CARGO_TO_PROFILE, CLASS_TO_IDX, FAILURE_CLASSES, IDX_AMB, IDX_DAMB, IDX_DTEMP, IDX_HOUR,
    IDX_TEMP, ROOT, SENTINEL, Models, deployed_ttb, load_test_windows, make_payload,
)

RNG = np.random.default_rng(42)
K = len(FAILURE_CLASSES)


def per_class(y, p):
    out = {}
    for c, name in enumerate(FAILURE_CLASSES):
        tp = int(((y == c) & (p == c)).sum()); fn = int(((y == c) & (p != c)).sum())
        fp = int(((y != c) & (p == c)).sum())
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        out[name] = {"support": int((y == c).sum()), "precision": pr, "recall": rc,
                     "f1": 2 * pr * rc / (pr + rc) if pr + rc else 0.0}
    return out


def bootstrap_by_trip(D, pred, n_boot=200):
    """Resample TRIPS (not windows) -> honest CI; test has only ~27 anomalous trips."""
    trips = D["meta"]["trip_id"].values
    uniq = np.unique(trips)
    idx_by = {t: np.flatnonzero(trips == t) for t in uniq}
    f1s, degr = [], []
    for _ in range(n_boot):
        pick = RNG.choice(uniq, len(uniq), replace=True)
        ii = np.concatenate([idx_by[t] for t in pick])
        f1s.append(f1_score(D["y_mode"][ii], pred[ii], average="macro", labels=list(range(K)), zero_division=0))
        m = D["y_mode"][ii] == CLASS_TO_IDX["degradasi_bertahap"]
        degr.append(float((pred[ii][m] == CLASS_TO_IDX["degradasi_bertahap"]).mean()) if m.any() else np.nan)
    q = lambda a: [float(np.nanpercentile(a, 2.5)), float(np.nanpercentile(a, 97.5))]
    return {"macro_f1_ci95": q(f1s), "degradasi_recall_ci95": q(degr)}


def g1_forecast(D, F):
    err = np.abs(F - D["y_forecast"])
    r = {f"mae_t{h}": float(err[:, i].mean()) for i, h in enumerate([15, 30, 60])}
    r["p95_abs_err_t30"] = float(np.percentile(err[:, 1], 95))
    r["max_abs_err_t30"] = float(err[:, 1].max())
    r["bias_t30"] = float((F[:, 1] - D["y_forecast"][:, 1]).mean())
    now = D["X"][:, -1, IDX_TEMP]
    persist = np.abs(D["y_forecast"][:, 1] - now)
    slope = (D["X"][:, -1, IDX_TEMP] - D["X"][:, -6, IDX_TEMP]) / 5.0
    extrap = np.abs(D["y_forecast"][:, 1] - (now + slope * 30))
    moving = persist >= 1.0          # windows where temperature really changes in 30 min
    r["naive_persistence_mae_t30"] = float(persist.mean())
    r["naive_linear_extrapolation_mae_t30"] = float(extrap.mean())
    r["moving_windows_n"] = int(moving.sum())
    r["moving_windows_gru_mae_t30"] = float(err[moving, 1].mean())
    r["moving_windows_persistence_mae_t30"] = float(persist[moving].mean())
    r["moving_windows_extrapolation_mae_t30"] = float(extrap[moving].mean())
    m = D["meta"]
    r["mae_t30_by_mode"] = {k: float(err[(m.raw_mode == k).values, 1].mean()) for k in sorted(m.raw_mode.unique())}
    r["mae_t30_by_cargo"] = {k: float(err[(m.cargo_type == k).values, 1].mean()) for k in sorted(m.cargo_type.unique())}
    return r


def g2_classification(D, P):
    y, pred = D["y_mode"], P.argmax(1)
    cm = confusion_matrix(y, pred, labels=list(range(K)))
    anom = (y != 0).astype(int)
    r = {
        "macro_f1": float(f1_score(y, pred, average="macro", labels=list(range(K)), zero_division=0)),
        "accuracy": float((y == pred).mean()),
        "anomaly_pr_auc": float(average_precision_score(anom, 1 - P[:, 0])),
        "anomaly_recall_at_argmax": float((pred[anom == 1] != 0).mean()),
        "false_alarm_rate_healthy": float((pred[anom == 0] != 0).mean()),
        "per_class": per_class(y, pred), "confusion_matrix": cm.tolist(),
        "classes": FAILURE_CLASSES,
        "trips_per_true_mode": D["meta"].groupby("raw_mode")["trip_id"].nunique().to_dict(),
    }
    r.update(bootstrap_by_trip(D, pred))
    # detection vs. time since fault onset -- is the miss inherent (fault not yet visible)?
    m = D["meta"]; since = m.min_since_onset.values
    bins = [(0, 10), (10, 30), (30, 60), (60, 120), (120, 10_000)]
    curve = {}
    for lo, hi in bins:
        sel = (anom == 1) & (since >= lo) & (since < hi)
        curve[f"{lo}-{hi if hi < 10_000 else 'inf'}"] = {
            "n": int(sel.sum()), "recall_non_A0": float((pred[sel] != 0).mean()) if sel.any() else None,
            "recall_exact_class": float((pred[sel] == y[sel]).mean()) if sel.any() else None}
    r["recall_by_minutes_since_onset"] = curve
    return r


def g3_imminent(D, P, T):
    ttb, shown = D["y_ttb"], deployed_ttb(P, T)
    pred = P.argmax(1)
    breach = ttb != SENTINEL
    out = {"n_breach_windows": int(breach.sum()), "n_healthy_no_breach": int((~breach).sum())}
    for name, lim in [("le10", 10), ("le30", 30)]:
        sel = ttb <= lim
        sh = ~np.isnan(shown[sel])
        out[f"true_ttb_{name}"] = {
            "n": int(sel.sum()), "shown_rate": float(sh.mean()),
            "mae_when_shown": float(np.abs(shown[sel][sh] - ttb[sel][sh]).mean()) if sh.any() else None,
            "mae_all_incl_missing_as_30": float(np.abs(np.where(sh, shown[sel], 30.0) - ttb[sel]).mean()),
            "miss_gate_A0": float((pred[sel] == 0).mean()),
            "miss_gate_sensor_class": float((pred[sel] == CLASS_TO_IDX["masalah_sensor"]).mean()),
            "miss_ttb_model_above_cap": float(((pred[sel] != 0) & (T[sel] >= 30)).mean()),
        }
    out["raw_xgb_ttb_mae_true_le30_ungated"] = float(np.abs(T[ttb <= 30] - ttb[ttb <= 30]).mean())
    out["raw_xgb_ttb_mae_all_breach"] = float(np.abs(T[breach] - ttb[breach]).mean())
    h = ~breach
    out["healthy_windows_showing_ttb"] = float((~np.isnan(shown[h])).mean())
    by = {}
    m = D["meta"]
    for c in sorted(m.cargo_type.unique()):
        sel = (ttb <= 30) & (m.cargo_type == c).values
        by[c] = {"n": int(sel.sum()), "mae_raw_ungated": float(np.abs(T[sel] - ttb[sel]).mean()) if sel.any() else None,
                 "shown_rate": float((~np.isnan(shown[sel])).mean()) if sel.any() else None}
    out["by_cargo_true_le30"] = by
    return out


def refeat(X):
    X = X.copy()
    X[:, :, IDX_DTEMP] = np.concatenate([np.zeros_like(X[:, :1, 0]), np.diff(X[:, :, IDX_TEMP], axis=1)], 1)
    X[:, :, IDX_DAMB] = X[:, :, IDX_TEMP] - X[:, :, IDX_AMB]
    return X


def g4_robustness(D, M, base):
    y, ttb = D["y_mode"], D["y_ttb"]
    imm = ttb <= 30
    def score(X):
        F, P, T = M.run(X)
        sh = deployed_ttb(P, T)
        return {"macro_f1": float(f1_score(y, P.argmax(1), average="macro", labels=list(range(K)), zero_division=0)),
                "forecast_mae_t30": float(np.abs(F[:, 1] - D["y_forecast"][:, 1]).mean()),
                "imminent_ttb_shown_rate": float((~np.isnan(sh[imm])).mean()),
                "imminent_pred_A0_rate": float((P.argmax(1)[imm] == 0).mean())}
    out = {"clean": base}
    for sigma in [0.1, 0.3, 0.5]:
        X = D["X"].copy(); X[:, :, IDX_TEMP] += RNG.normal(0, sigma, X[:, :, IDX_TEMP].shape).astype(np.float32)
        out[f"sensor_noise_sigma_{sigma}C"] = score(refeat(X))
    X = D["X"].copy(); X[:, :, IDX_HOUR] = (X[:, :, IDX_HOUR] + 7) % 24
    out["hour_shift_utc_vs_wib_+7h"] = score(X)
    # stuck sensor while cargo is truly heading for breach: sensor freezes 30 min before "now"
    X = D["X"][imm].copy(); X[:, 30:, IDX_TEMP] = X[:, 29:30, IDX_TEMP]
    X = refeat(X)
    F, P, T = M.run(X)
    pred = P.argmax(1)
    out["stuck_sensor_on_imminent_breach"] = {
        "n": int(imm.sum()), "pred_masalah_sensor": float((pred == CLASS_TO_IDX["masalah_sensor"]).mean()),
        "pred_A0_healthy": float((pred == 0).mean()),
        "pred_other_fault": float(((pred != 0) & (pred != CLASS_TO_IDX["masalah_sensor"])).mean())}
    return out


def g5_api(D, F, P, T, stride):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    idx = np.arange(0, len(D["X"]), stride)
    ttb, m = D["y_ttb"], D["meta"]
    rows, lat = [], []
    for i in idx:
        prof = CARGO_TO_PROFILE[m.cargo_type.iloc[i]]
        t0 = time.perf_counter()
        r = client.post("/api/v1/analyze", json=make_payload(D, i, prof))
        lat.append((time.perf_counter() - t0) * 1000)
        if r.status_code != 200:
            rows.append((i, None)); continue
        rows.append((i, r.json()))
    ok = [(i, j) for i, j in rows if j]
    status = np.array([j["status"] for _, j in ok]); ii = np.array([i for i, _ in ok])
    shown = np.array([np.nan if j["time_to_breach_min"] is None else j["time_to_breach_min"] for _, j in ok])
    t_true = ttb[ii]
    def rate(mask, label):
        return float((status[mask] == label).mean()) if mask.any() else None
    out = {"n_requests": int(len(idx)), "n_http_errors": int(len(idx) - len(ok)),
           "latency_ms_p50": float(np.percentile(lat, 50)), "latency_ms_p95": float(np.percentile(lat, 95))}
    for name, mask in [("true_ttb_le30", t_true <= 30), ("true_ttb_30_60", (t_true > 30) & (t_true <= 60)),
                       ("true_ttb_gt60", (t_true > 60) & (t_true != SENTINEL)), ("no_breach", t_true == SENTINEL)]:
        out[name] = {"n": int(mask.sum()), "AMAN": rate(mask, "AMAN"), "WASPADA": rate(mask, "WASPADA"),
                     "KRITIS": rate(mask, "KRITIS"),
                     "ttb_shown": float((~np.isnan(shown[mask])).mean()) if mask.any() else None}
    sel = (t_true <= 30) & ~np.isnan(shown)
    out["api_ttb_mae_when_shown_true_le30"] = float(np.abs(shown[sel] - t_true[sel]).mean()) if sel.any() else None
    # parity: API vs raw ONNX on the SAME windows (serving-path skew)
    fa = np.array([[j["forecast"]["t15"], j["forecast"]["t30"], j["forecast"]["t60"]] for _, j in ok])
    out["parity_forecast_max_abs_diff_C"] = float(np.abs(fa - F[ii]).max())
    out["parity_forecast_mean_abs_diff_C"] = float(np.abs(fa - F[ii]).mean())
    lab = {"normal_sehat": 0, "pintu_terbuka_lama": 1, "kegagalan_reefer_total": 2, "fluktuasi_ambien_ekstrem": 3,
           "prapendinginan_buruk": 4, "degradasi_pendinginan": 5, "masalah_sensor": 6}
    pa = np.array([lab[j["failure_mode"]["label"]] for _, j in ok])
    out["parity_class_disagreement_rate"] = float((pa != P[ii].argmax(1)).mean())
    # over-alert by mode: healthy windows pushed to KRITIS
    out["by_true_mode_status"] = {k: {s: float((status[(m.raw_mode.values[ii] == k)] == s).mean())
                                      for s in ["AMAN", "WASPADA", "KRITIS"]}
                                  for k in sorted(m.raw_mode.unique())}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="baseline")
    ap.add_argument("--api-stride", type=int, default=3)
    a = ap.parse_args()
    t0 = time.time()
    D = load_test_windows()
    M = Models()
    F, P, T = M.run(D["X"])
    print(f"[{time.time()-t0:4.0f}s] {len(D['X']):,} test windows, {D['meta'].trip_id.nunique()} trips")
    res = {"tag": a.tag, "n_windows": int(len(D["X"])), "n_trips": int(D["meta"].trip_id.nunique())}
    res["G1_forecast"] = g1_forecast(D, F)
    res["G2_classification"] = g2_classification(D, P)
    res["G3_imminent_breach"] = g3_imminent(D, P, T)
    print(f"[{time.time()-t0:4.0f}s] G1-G3 done")
    base = {"macro_f1": res["G2_classification"]["macro_f1"], "forecast_mae_t30": res["G1_forecast"]["mae_t30"],
            "imminent_ttb_shown_rate": res["G3_imminent_breach"]["true_ttb_le30"]["shown_rate"],
            "imminent_pred_A0_rate": res["G3_imminent_breach"]["true_ttb_le30"]["miss_gate_A0"]}
    res["G4_robustness"] = g4_robustness(D, M, base)
    print(f"[{time.time()-t0:4.0f}s] G4 done")
    res["G5_end_to_end_api"] = g5_api(D, F, P, T, a.api_stride)
    print(f"[{time.time()-t0:4.0f}s] G5 done")
    out = ROOT / "eval/results" / f"{a.tag}_results.json"
    out.write_text(json.dumps(res, indent=2, default=float))
    print("wrote", out)


if __name__ == "__main__":
    main()
