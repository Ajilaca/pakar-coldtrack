"""ColdTrack AI evaluation suite -- scores the DEPLOYED hybrid system on the held-out test split.

Usage:  python -m eval.run_eval [--tag iter1] [--api-stride 10] [--stuck-stride 3]
Output: eval/results/<tag>_results.json

Groups (same test trips/windows as the baseline; metrics follow the new contract)
  G1 forecast          GRU cargo-temperature forecast vs what really happened
  G2 events            door / ambient shock / sensor fault: detection per event + healthy false alarms
  G3 imminent breach   what the system SHOWS when true TTB <= 10 / 30 min (status + countdown)
  G4 robustness        sensor noise, timezone shift, stuck sensor during a real warming
  G5 end-to-end API    real FastAPI endpoint: status safety, TTB shown, latency, parity with G1-G3
"""

import argparse
import json
import time

import numpy as np
import pandas as pd

from eval.common import (
    CARGO_TO_PROFILE, EVENT_LABEL, EVENTS, ROOT, SENTINEL, eval_rows, load_test_trips, trip_readings,
)

RNG = np.random.default_rng(42)
STATUSES = ["AMAN", "WASPADA", "KRITIS"]


def auc(y: pd.Series, score: pd.Series) -> float:
    """ROC AUC via the Mann-Whitney rank statistic (ties get average rank)."""
    r = score.rank().to_numpy()
    pos = y.to_numpy().astype(bool)
    n1, n0 = pos.sum(), (~pos).sum()
    return float((r[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def status_rates(st: pd.Series) -> dict:
    return {s: float((st == s).mean()) if len(st) else None for s in STATUSES}


def g1_forecast(D):
    r = {}
    for h in (15, 30, 60):
        r[f"mae_t{h}"] = float((D[f"t{h}"] - D[f"y{h}"]).abs().mean())
    err30 = (D.t30 - D.y30).abs()
    r["p95_abs_err_t30"] = float(err30.quantile(0.95))
    r["max_abs_err_t30"] = float(err30.max())
    r["bias_t30"] = float((D.t30 - D.y30).mean())
    r["mae_t30_vs_true_temp"] = float((D.t30 - D.y30_true).abs().mean())
    persist = (D.y30 - D.temp_now).abs()
    extrap = (D.y30 - (D.temp_now + (D.temp_now - D.temp_now_5) / 5 * 30)).abs()
    moving = persist >= 1.0
    r["naive_persistence_mae_t30"] = float(persist.mean())
    r["naive_linear_extrapolation_mae_t30"] = float(extrap.mean())
    r["moving_windows_n"] = int(moving.sum())
    r["moving_windows_gru_mae_t30"] = float(err30[moving].mean())
    r["moving_windows_persistence_mae_t30"] = float(persist[moving].mean())
    r["moving_windows_extrapolation_mae_t30"] = float(extrap[moving].mean())
    r["mae_t30_by_mode"] = err30.groupby(D.raw_mode).mean().to_dict()
    r["mae_t30_by_cargo"] = err30.groupby(D.cargo_type).mean().to_dict()
    return r


def event_scores(D):
    """Deployed diagnosis per covered event: recall = window labelled with that event."""
    out = {}
    for e in EVENTS:
        pos = D.event == e
        prob = D[f"ev_{e}"]
        out[e] = {
            "n_windows": int(pos.sum()), "n_trips": int(D.trip_id[pos].nunique()),
            "recall": float((D.label[pos] == EVENT_LABEL[e]).mean()) if pos.any() else None,
            "precision": float((D.event[D.label == EVENT_LABEL[e]] == e).mean()) if (D.label == EVENT_LABEL[e]).any() else None,
            "gru_auc_vs_healthy": auc(pos[pos | (D.raw_mode == "A0")], prob[pos | (D.raw_mode == "A0")])
            if pos.any() else None,
        }
    return out


def g2_events(D):
    healthy = D.raw_mode == "A0"
    r = {
        "per_event": event_scores(D),
        "healthy_labelled_fault_rate": float((D.label[healthy] != "normal_sehat").mean()),
        "healthy_alert_rate": float((D.status[healthy] != "AMAN").mean()),
        "label_share": D.label.value_counts(normalize=True).to_dict(),
        "status_by_true_mode": {m: status_rates(g.status) for m, g in D.groupby("raw_mode")},
        "trips_per_true_mode": D.groupby("raw_mode").trip_id.nunique().to_dict(),
        "uncovered_modes_note": "A2/A4 (cooling degradation), A3 (reefer off), A8 (pre-cooling) have no event; "
                                "judged only via status/TTB (G3).",
    }
    r["mean_event_recall"] = float(np.mean([v["recall"] for v in r["per_event"].values()]))
    # detection vs minutes since fault onset, covered events only
    since, cov = D.min_since_onset, D.event.notna()
    hit = D.label == D.event.map(EVENT_LABEL)
    curve = {}
    for lo, hi in [(0, 10), (10, 30), (30, 60), (60, 120), (120, 10_000)]:
        sel = cov & (since >= lo) & (since < hi)
        curve[f"{lo}-{hi if hi < 10_000 else 'inf'}"] = {"n": int(sel.sum()),
                                                          "recall": float(hit[sel].mean()) if sel.any() else None}
    r["recall_by_minutes_since_onset"] = curve
    return r


def g3_imminent(D):
    ttb, shown, breach = D.y_ttb, D.ttb_show, D.y_ttb != SENTINEL
    out = {"n_breach_windows": int(breach.sum()), "n_healthy_no_breach": int((~breach).sum())}
    for name, lim in [("le10", 10), ("le30", 30)]:
        sel = ttb <= lim
        sh = shown[sel].notna()
        out[f"true_ttb_{name}"] = {
            "n": int(sel.sum()), "shown_rate": float(sh.mean()),
            "mae_when_shown": float((shown[sel][sh] - ttb[sel][sh]).abs().mean()) if sh.any() else None,
            "mae_all_incl_missing_as_60": float((shown[sel].fillna(60.0) - ttb[sel]).abs().mean()),
            **status_rates(D.status[sel]),
            "hidden_sensor_broken": float((D.sensor_status[sel] == 2).mean()),
            "hidden_physics_ttb_above_60": float(((D.sensor_status[sel] < 2) & (D.ttb_phys[sel] > 60)).mean()),
        }
    le30 = ttb <= 30
    out["physics_ttb_mae_true_le30_ungated"] = float((D.ttb_phys[le30] - ttb[le30]).abs().mean())
    out["xgb_ttb_mae_true_le30"] = float((D.ttb_model[le30] - ttb[le30]).abs().mean())
    out["xgb_ttb_mae_all_breach"] = float((D.ttb_model[breach] - ttb[breach]).abs().mean())
    out["healthy_windows_showing_ttb"] = float(shown[~breach].notna().mean())
    out["status_by_true_ttb"] = {
        name: status_rates(D.status[m]) | {"n": int(m.sum())}
        for name, m in [("le30", le30), ("30_60", (ttb > 30) & (ttb <= 60)),
                        ("gt60", (ttb > 60) & breach), ("no_breach", ~breach)]}
    out["by_cargo_true_le30"] = {
        c: {"n": int((le30 & (D.cargo_type == c)).sum()),
            "shown_rate": float(shown[le30 & (D.cargo_type == c)].notna().mean()) if (le30 & (D.cargo_type == c)).any() else None,
            "aman_rate": float((D.status[le30 & (D.cargo_type == c)] == "AMAN").mean()) if (le30 & (D.cargo_type == c)).any() else None}
        for c in sorted(CARGO_TO_PROFILE)}
    return out


def summary(D):
    imm = D.y_ttb <= 30
    return {"mean_event_recall": g2_events(D)["mean_event_recall"],
            "forecast_mae_t30": float((D.t30 - D.y30).abs().mean()),
            "imminent_ttb_shown_rate": float(D.ttb_show[imm].notna().mean()),
            "imminent_aman_rate": float((D.status[imm] == "AMAN").mean()),
            "healthy_alert_rate": float((D.status[D.raw_mode == "A0"] != "AMAN").mean())}


def g4_robustness(trips, D, stuck_stride):
    from eval.common import score_trip
    out = {"clean": summary(D)}
    for sigma in [0.1, 0.3, 0.5]:
        noisy = {tid: g.assign(temp_c=g.temp_c + RNG.normal(0, sigma, len(g))) for tid, g in trips.items()}
        out[f"sensor_noise_sigma_{sigma}C"] = summary(eval_rows(noisy))
    out["hour_shift_utc_vs_wib_+7h"] = summary(eval_rows(trips, hour_shift=7))
    # stuck sensor while cargo truly heads for breach: sensor freezes 30 min before "now"
    imm = D[D.y_ttb <= 30].iloc[::stuck_stride]
    res = []
    for tid, t in zip(imm.trip_id, imm.t):
        g = trips[tid].iloc[:t + 1].copy()
        temp = g.temp_c.to_numpy().copy()
        temp[t - 29:] = temp[t - 30]
        res.append(score_trip(g, temp=temp).iloc[-1])
    R = pd.DataFrame(res)
    out["stuck_sensor_on_imminent_breach"] = {
        "n": int(len(R)), "flagged_sensor": float((R.label == "masalah_sensor").mean()),
        "status_aman": float((R.status == "AMAN").mean()),
        "status_kritis": float((R.status == "KRITIS").mean()),
        "note": "sensor_rules needs >=15 min flat plus context (door/ambient rise) for 'suspect', 60 min for 'broken'."}
    return out


def g5_api(trips, D, stride):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    sub = D.iloc[::stride]
    rows, lat = [], []
    for tid, t in zip(sub.trip_id, sub.t):
        g = trips[tid].iloc[:t + 1]
        body = {"shipment_id": f"EVAL-{tid}-{t}", "cargo_profile": CARGO_TO_PROFILE[g.cargo_type.iloc[0]],
                "readings": [r.model_dump(mode="json") for r in trip_readings(g)]}
        t0 = time.perf_counter()
        r = client.post("/api/v1/analyze", json=body)
        lat.append((time.perf_counter() - t0) * 1000)
        rows.append(r.json() if r.status_code == 200 else None)
    ok = np.array([j is not None for j in rows])
    S, J = sub[ok], [j for j in rows if j]
    status = pd.Series([j["status"] for j in J], index=S.index)
    shown = pd.Series([j["time_to_breach_min"] for j in J], index=S.index, dtype=float)
    ttb = S.y_ttb
    out = {"n_requests": int(len(sub)), "n_http_errors": int((~ok).sum()),
           "latency_ms_p50": float(np.percentile(lat, 50)), "latency_ms_p95": float(np.percentile(lat, 95))}
    for name, m in [("true_ttb_le30", ttb <= 30), ("true_ttb_30_60", (ttb > 30) & (ttb <= 60)),
                    ("true_ttb_gt60", (ttb > 60) & (ttb != SENTINEL)), ("no_breach", ttb == SENTINEL)]:
        out[name] = status_rates(status[m]) | {"n": int(m.sum()),
                                               "ttb_shown": float(shown[m].notna().mean()) if m.any() else None}
    out["by_true_mode_status"] = {k: status_rates(status[S.raw_mode == k]) for k in sorted(S.raw_mode.unique())}
    fa = np.array([[j["forecast"][h] for h in ("t15", "t30", "t60")] for j in J])
    out["parity_forecast_max_abs_diff_C"] = float(np.abs(fa - S[["t15", "t30", "t60"]].to_numpy()).max())
    out["parity_status_agreement"] = float((status == S.status).mean())
    out["parity_label_agreement"] = float((pd.Series([j["failure_mode"]["label"] for j in J], index=S.index) == S.label).mean())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="iter1")
    ap.add_argument("--api-stride", type=int, default=10)
    ap.add_argument("--stuck-stride", type=int, default=3)
    a = ap.parse_args()
    t0 = time.time()
    trips = load_test_trips()
    D = eval_rows(trips)
    print(f"[{time.time()-t0:4.0f}s] {len(D):,} test windows, {D.trip_id.nunique()} trips")
    res = {"tag": a.tag, "contract": "hybrid-v3", "n_windows": int(len(D)), "n_trips": int(D.trip_id.nunique())}
    res["G1_forecast"] = g1_forecast(D)
    res["G2_events"] = g2_events(D)
    res["G3_imminent_breach"] = g3_imminent(D)
    print(f"[{time.time()-t0:4.0f}s] G1-G3 done")
    res["G4_robustness"] = g4_robustness(trips, D, a.stuck_stride)
    print(f"[{time.time()-t0:4.0f}s] G4 done")
    res["G5_end_to_end_api"] = g5_api(trips, D, a.api_stride)
    print(f"[{time.time()-t0:4.0f}s] G5 done")
    out = ROOT / "eval/results" / f"{a.tag}_results.json"
    out.write_text(json.dumps(res, indent=2, default=float))
    print("wrote", out)


if __name__ == "__main__":
    main()
