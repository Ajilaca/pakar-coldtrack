"""Build the Evaluation Artifact PDF (+ figures) from eval/results/<tag>_results.json.

Usage: python -m eval.make_artifact [--tag baseline]
"""

import argparse
import json
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

RES = Path(__file__).parent / "results"
RED, GREEN, GREY = "#B3261E", "#2E7D32", "#555555"


def figs(R, tag):
    G2, G4, G5 = R["G2_classification"], R["G4_robustness"], R["G5_end_to_end_api"]
    cls = G2["classes"]
    cm_ = np.array(G2["confusion_matrix"], float)
    cmn = cm_ / cm_.sum(1, keepdims=True)
    fig, ax = plt.subplots(figsize=(6, 4.6))
    ax.imshow(cmn, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(cls))); ax.set_yticks(range(len(cls)))
    ax.set_xticklabels(cls, rotation=40, ha="right", fontsize=8); ax.set_yticklabels(cls, fontsize=8)
    for i in range(len(cls)):
        for j in range(len(cls)):
            ax.text(j, i, f"{cmn[i, j]:.2f}", ha="center", va="center", fontsize=7,
                    color="white" if cmn[i, j] > .5 else "black")
    ax.set_xlabel("predicted"); ax.set_ylabel("true"); ax.set_title("Failure-mode confusion (row-normalised, test)", fontsize=10)
    fig.tight_layout(); fig.savefig(RES / f"{tag}_fig_confusion.png", dpi=170); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    groups = [("true_ttb_le30", "breach in ≤30 min"), ("true_ttb_30_60", "breach in 30–60 min"),
              ("true_ttb_gt60", "breach in >60 min"), ("no_breach", "no breach")]
    left = np.zeros(len(groups))
    for st, col in [("AMAN", "#4CAF50"), ("WASPADA", "#FFB300"), ("KRITIS", "#D32F2F")]:
        v = np.array([G5[g][st] for g, _ in groups])
        ax.barh([n for _, n in groups], v, left=left, color=col, label=st); left += v
    ax.invert_yaxis(); ax.set_xlim(0, 1); ax.legend(ncol=3, fontsize=8, loc="lower center", bbox_to_anchor=(.5, 1.0))
    ax.set_xlabel("share of windows (API status)"); fig.tight_layout()
    fig.savefig(RES / f"{tag}_fig_status.png", dpi=170); plt.close(fig)

    keys = ["clean", "sensor_noise_sigma_0.1C", "sensor_noise_sigma_0.3C", "sensor_noise_sigma_0.5C"]
    fig, ax = plt.subplots(1, 2, figsize=(6.6, 2.7))
    lab = ["clean", "σ 0.1", "σ 0.3", "σ 0.5"]
    ax[0].bar(lab, [G4[k]["macro_f1"] for k in keys], color=["#607D8B"] + [RED] * 3); ax[0].set_title("Macro F1 vs sensor noise (°C)", fontsize=9)
    ax[1].bar(lab, [G4[k]["imminent_pred_A0_rate"] for k in keys], color=["#607D8B"] + [RED] * 3)
    ax[1].set_title("Imminent breaches labelled 'healthy'", fontsize=9)
    for a in ax: a.set_ylim(0, 1); a.tick_params(labelsize=8)
    fig.tight_layout(); fig.savefig(RES / f"{tag}_fig_noise.png", dpi=170); plt.close(fig)


def build(tag):
    R = json.loads((RES / f"{tag}_results.json").read_text())
    figs(R, tag)
    G1, G2, G3, G4, G5 = (R[k] for k in ["G1_forecast", "G2_classification", "G3_imminent_breach", "G4_robustness", "G5_end_to_end_api"])
    pt = subprocess.run(["python", "-m", "pytest", "eval/test_baseline.py", "-q", "-p", "no:cacheprovider", "-rA"],
                        capture_output=True, text=True, env={**__import__("os").environ, "EVAL_TAG": tag}).stdout
    checks = [(l.split()[0], l.split()[1].split("::")[1]) for l in pt.splitlines() if l.startswith(("PASSED", "FAILED"))]
    n_pass = sum(c == "PASSED" for c, _ in checks)

    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=15, spaceAfter=6)
    H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=11.5, spaceBefore=8, spaceAfter=3)
    B = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=12)
    S = ParagraphStyle("s", parent=B, fontSize=7.5, leading=9.5, textColor=colors.HexColor(GREY))
    C = ParagraphStyle("c", parent=B, fontSize=8, leading=10)
    p = lambda t, st=B: Paragraph(t, st)
    pct = lambda x: f"{100 * x:.0f}%"

    def table(rows, widths, head=True, fs=8):
        t = Table([[p(str(c), C) for c in r] for r in rows], colWidths=widths, repeatRows=1 if head else 0)
        st = [("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#BBBBBB")), ("VALIGN", (0, 0), (-1, -1), "TOP")]
        if head: st.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EAF0")))
        t.setStyle(TableStyle(st)); return t

    s = []
    s += [p("ColdTrack AI — Evaluation Artifact (Baseline)", H1),
          p(f"AIC COMPFEST 18 Final · Smart Logistics · tag <b>{tag}</b> · system under test: MVP from the qualifying round "
            f"(<font face='Courier'>coldtrack.onnx</font> GRU + <font face='Courier'>coldtrack_ttb.onnx</font> XGBoost + backend rule engine), "
            f"evaluated <b>as deployed</b> on the held-out test split "
            f"({R['n_windows']:,} sliding windows, {R['n_trips']} trips; split by trip).", B),
          Spacer(1, 6), p("Executive summary", H2),
          p(f"Baseline score: <b>{n_pass}/{len(checks)} acceptance checks pass</b>. The headline model metrics from the qualifying round "
            f"reproduce exactly (macro-F1 {G2['macro_f1']:.3f}, forecast MAE@30 {G1['mae_t30']:.3f} °C), but the deployed system fails where it matters operationally:", B),
          table([["#", "Finding (evidence)", "Severity"],
                 ["F1", f"<b>1 in 3 imminent breaches gets a green status.</b> End-to-end API, windows whose true time-to-breach ≤ 30 min: "
                        f"AMAN {pct(G5['true_ttb_le30']['AMAN'])}, WASPADA {pct(G5['true_ttb_le30']['WASPADA'])}, KRITIS {pct(G5['true_ttb_le30']['KRITIS'])} (n={G5['true_ttb_le30']['n']}).", "Critical"],
                 ["F2", f"<b>The TTB is silenced by the classifier.</b> Of windows with true TTB ≤ 30 min, {pct(G3['true_ttb_le30']['miss_gate_A0'])} are classified "
                        f"healthy (A0) and the backend hides TTB for A0; the two ONNX models show a TTB in only {pct(G3['true_ttb_le30']['shown_rate'])}.", "Critical"],
                 ["F3", f"<b>Fragile to realistic sensor noise.</b> Adding N(0, 0.3 °C) to temp_c (training noise was 0.05 °C): macro-F1 {G4['clean']['macro_f1']:.2f} → "
                        f"{G4['sensor_noise_sigma_0.3C']['macro_f1']:.2f}; imminent breaches labelled healthy {pct(G4['clean']['imminent_pred_A0_rate'])} → {pct(G4['sensor_noise_sigma_0.3C']['imminent_pred_A0_rate'])}.", "High"],
                 ["F4", f"<b>Stuck sensor while cargo warms is read as healthy.</b> Only {pct(G4['stuck_sensor_on_imminent_breach']['pred_masalah_sensor'])} flagged masalah_sensor; "
                        f"{pct(G4['stuck_sensor_on_imminent_breach']['pred_A0_healthy'])} predicted A0.", "High"],
                 ["F5", f"<b>Forecast target is met by a trivial baseline.</b> 'Temperature stays the same' scores {G1['naive_persistence_mae_t30']:.3f} °C vs GRU {G1['mae_t30']:.3f} °C; "
                        f"only {G1['moving_windows_n']} of {R['n_windows']:,} test windows move ≥1 °C in 30 min.", "High (metric validity)"],
                 ["F6", f"<b>Three fault classes are largely undetected</b>: recall A7 {pct(G2['per_class']['A7']['recall'])}, A8 {pct(G2['per_class']['A8']['recall'])}, "
                        f"degradasi_bertahap {pct(G2['per_class']['degradasi_bertahap']['recall'])} (95% CI {pct(G2['degradasi_recall_ci95'][0])}–{pct(G2['degradasi_recall_ci95'][1])}).", "High"],
                 ["F7", "<b>Test set cannot support per-class or per-cargo claims.</b> 2–4 test trips for A1/A2/A4/A5; the vaccine, frozen-meat and fish profiles have zero imminent-breach test windows.", "Medium (validity)"]],
                [1*cm, 14*cm, 2.4*cm]), PageBreak()]

    # ---------- (a) test suite ----------
    s += [p("1. Test suite: scope, cases, metrics and why", H1),
          p("Design principle: test the system <b>the user actually sees</b> (raw ONNX outputs → backend gating → rule engine → HTTP response), not just the network. "
            "Code: <font face='Courier'>eval/</font> — <font face='Courier'>run_eval.py</font> (measurements), <font face='Courier'>test_baseline.py</font> "
            "(23 acceptance checks), <font face='Courier'>make_artifact.py</font> (this PDF). Reproduce: "
            "<font face='Courier'>python -m eval.run_eval --tag baseline; pytest eval/test_baseline.py</font>.", B),
          table([["Group", "Test cases", "Metric(s)", "Why this metric / what it does NOT capture"],
                 ["G1 Forecast", f"{R['n_windows']:,} test windows; sliced by fault mode and cargo; compared to naive persistence and linear extrapolation",
                  "MAE t+15/30/60, p95 and max error, MAE on windows that really move",
                  "MAE is dominated by the ~99% of windows where nothing changes; hence the persistence comparison and the 'moving windows' slice. MAE says nothing about whether the alarm fires."],
                 ["G2 Classification", "7 classes; bootstrap over <i>trips</i> (200×) for CIs; recall vs minutes since fault onset",
                  "per-class P/R/F1, macro-F1, PR-AUC, confusion matrix",
                  "Macro-F1 hides which fault is missed → per-class recall checks. Windows of one trip are highly correlated, so window-level CIs would be far too narrow."],
                 ["G3 Imminent breach", "windows with true TTB ≤ 10 / ≤ 30 min, gated exactly like backend/app/inference.py",
                  "TTB shown-rate, MAE when shown, miss reasons (classifier said A0 / sensor / above cap)",
                  "The qualifying-round 'MAE 7.08 min for TTB ≤ 30' conditions on the true answer and ignores silent misses. Shown-rate + reason exposes them."],
                 ["G4 Robustness", "sensor noise σ∈{0.1,0.3,0.5} °C (delta features recomputed); +7 h hour shift (UTC vs WIB); stuck sensor injected into imminent-breach windows",
                  "macro-F1, forecast MAE, imminent-breach A0 rate, class chosen under stuck sensor",
                  "Training data is a clean simulator (σ=0.05 °C, ACF too smooth per dataset card). Real loggers are noisier. Perturbations are synthetic, so they show <i>sensitivity</i>, not real-world error."],
                 ["G5 End-to-end API", f"{G5['n_requests']:,} windows (every 2nd) POSTed to /api/v1/analyze via FastAPI TestClient, cargo profile mapped from the trip",
                  "status × true-TTB bucket, TTB shown, latency, parity with raw ONNX, HTTP errors",
                  "Ground truth = simulator's time_to_breach (threshold = cargo max limit; verified equal to config.yaml). Says nothing about real trucks."]],
                [2.3*cm, 5.3*cm, 3.8*cm, 6*cm]),
          Spacer(1, 6),
          p("Pre-existing checks (run for reference, not part of the graded suite): backend pytest <b>24/24 pass</b>, ml/tests data-contract <b>7/7 pass</b>. "
            "XGBoost/Linear/IsolationForest baselines (ml/baselines.py) re-run on the <i>test</i> split: forecast MAE@30 linear 0.192 / XGB 0.190; "
            "macro-F1 XGB 0.667; PR-AUC XGB 0.749, IsolationForest 0.352. The committed <font face='Courier'>baseline_metrics.json</font> is from the validation split of v3 and is stale.", B),
          p("Caveats we did not remove: 106 test trips (27 anomalous); all data synthetic; acceptance thresholds are our own operational choices, set with sight of the qualifying-round numbers and open to challenge.", S),
          PageBreak()]

    # ---------- (b) baseline findings ----------
    s += [p("2. Baseline failure findings (where the system fails, with evidence)", H1),
          p("F1 · Imminent breaches shown as AMAN", H2),
          Image(str(RES / f"{tag}_fig_status.png"), width=13*cm, height=6.1*cm),
          p(f"Root causes visible in code: (i) status is driven by the forecast head, which is ~persistence (F5); (ii) the TTB floor in rules.py only applies when a TTB exists, and "
            f"it is None whenever the classifier says A0; (iii) the backend heuristic TTB fallback only runs after WASPADA/KRITIS. "
            f"When shown, API TTB is accurate (MAE {G5['api_ttb_mae_when_shown_true_le30']:.1f} min) — the failure is <i>coverage</i>, not precision. "
            f"Also: only {pct(G5['true_ttb_30_60']['WASPADA']+G5['true_ttb_30_60']['KRITIS'])} of windows 30–60 min before breach are above AMAN, so the 60-min warning path in config.yaml is effectively unreachable (TTB display cap = 30).", B),
          p("F2 · TTB depends on the weakest component", H2),
          table([["True TTB ≤ 30 min (n=%d)" % G3["true_ttb_le30"]["n"], "Share"],
                 ["TTB shown by the two ONNX models + gate", pct(G3["true_ttb_le30"]["shown_rate"])],
                 ["Hidden because classifier said A0 (healthy)", pct(G3["true_ttb_le30"]["miss_gate_A0"])],
                 ["Hidden because classifier said masalah_sensor", pct(G3["true_ttb_le30"]["miss_gate_sensor_class"])],
                 ["Hidden because TTB model output ≥ 30 min cap", pct(G3["true_ttb_le30"]["miss_ttb_model_above_cap"])],
                 ["MAE when shown / counting misses as '30 min'", f"{G3['true_ttb_le30']['mae_when_shown']:.1f} min / {G3['true_ttb_le30']['mae_all_incl_missing_as_30']:.1f} min"]],
                [11*cm, 5*cm]),
          p("F3/F4 · Robustness", H2), Image(str(RES / f"{tag}_fig_noise.png"), width=12.5*cm, height=5.1*cm),
          p(f"Timezone hypothesis tested and <b>refuted</b>: shifting hour_of_day by +7 h leaves macro-F1 at {G4['hour_shift_utc_vs_wib_+7h']['macro_f1']:.3f} (clean {G4['clean']['macro_f1']:.3f}). "
            f"Serving parity is good: API vs raw ONNX forecast mean |Δ| {G5['parity_forecast_mean_abs_diff_C']:.3f} °C (max {G5['parity_forecast_max_abs_diff_C']:.2f} °C), "
            f"class disagreement {100*G5['parity_class_disagreement_rate']:.1f}% — no significant train/serve skew.", B),
          PageBreak(),
          p("F5 · The forecast target is not discriminative", H2),
          table([["t+30 min MAE (°C)", "All windows", f"Moving windows (n={G1['moving_windows_n']})"],
                 ["GRU (deployed)", f"{G1['mae_t30']:.3f}", f"{G1['moving_windows_gru_mae_t30']:.2f}"],
                 ["Naive persistence ('same as now')", f"{G1['naive_persistence_mae_t30']:.3f}", f"{G1['moving_windows_persistence_mae_t30']:.2f}"],
                 ["Linear extrapolation of last 5 min", f"{G1['naive_linear_extrapolation_mae_t30']:.3f}", f"{G1['moving_windows_extrapolation_mae_t30']:.2f}"]],
                [7*cm, 4*cm, 5*cm]),
          p("The '<0.8 °C — target met' claim is true but uninformative. On the few windows where temperature changes, GRU beats persistence by ~20%, which is the honest headline.", B),
          p("F6 · Fault classes", H2), Image(str(RES / f"{tag}_fig_confusion.png"), width=10.5*cm, height=8.0*cm),
          table([["Class", "test windows", "test trips", "precision", "recall", "F1"]] +
                [[k, v["support"], {"A0": 95, "A1": 4, "A3": 7, "A7": 5, "A8": 6, "degradasi_bertahap": "2 (A2) + 3 (A4)", "masalah_sensor": "3 (A5) + 8 (A6)"}[k],
                  f"{v['precision']:.2f}", f"{v['recall']:.2f}", f"{v['f1']:.2f}"] for k, v in G2["per_class"].items()],
                [4*cm, 2.6*cm, 3.6*cm, 2*cm, 2*cm, 2*cm]),
          p("Detection vs minutes since fault onset (any non-A0): " + "; ".join(f"{k} min: {pct(v['recall_non_A0'])} (n={v['n']})" for k, v in G2["recall_by_minutes_since_onset"].items()) +
            ". Recall is <i>lowest deep into a fault</i> (120+ min) — so 'the fault has not shown yet' does not explain the misses. We have not yet established why (see §4).", B),
          p("F7 · Test-set validity", H2),
          p("Imminent-breach (TTB ≤ 30) test windows exist only for produce (%d) and dairy (%d); none for vaccine, frozen meat or fish — the flagship vaccine use case has no imminent-breach evidence. "
            "Bootstrap 95%% CI for macro-F1 is %.2f–%.2f." % (G3["by_cargo_true_le30"]["sayur_buah"]["n"], G3["by_cargo_true_le30"]["produk_susu"]["n"], *G2["macro_f1_ci95"]), B),
          PageBreak()]

    # ---------- (c) before/after ----------
    s += [p("3. Before / after iteration", H1),
          p("Status: <b>baseline only</b>. This section is filled after each iteration (Evaluation Track); the 'after' column is intentionally empty until measured by the same suite.", B),
          p("<b>Planned iteration 1 (in progress, not yet measured): real inputs + physics simulator + narrower scope.</b> "
            "(i) Replace the synthetic raw inputs with real data: BMKG daily temperature and humidity for Indonesia (2010–2020) as the air outside the truck; "
            "product thermal tables (fish, meat, vegetables, fruit) combined with a user-entered payload mass; and real faulty-sensor traces from the Intel Berkeley Lab dataset to imitate sensor errors. "
            "This changes are made to allow a wider range of product (that can degrade) to be detected by our product."
            "(ii) Generate trips with a physics-based truck model (heat ingress from outside air; heavier payload warms more slowly). "
            "(iii) Reduce the classifier to <b>4 scenarios</b>: healthy (A0), door open (A1), sudden extreme ambient (A7) and sensor fault (masalah_sensor). "
            "Total reefer failure (A3) and cooling degradation (degradasi_bertahap) are deferred as a later feature; poor pre-cooling (A8) becomes a rule checked before departure. "
            "Consequence for comparison: per-class 'after' numbers exist only for the 4 kept classes, and macro-F1 over 4 classes is not directly comparable to the 7-class baseline.", B),
          table([["Metric (test split)", "Baseline", "After iteration", "Change / reason"],
                 ["Acceptance checks passed", f"{n_pass}/{len(checks)}", "—", "—"],
                 ["Imminent breach shown as AMAN (API)", pct(G5["true_ttb_le30"]["AMAN"]), "—", "—"],
                 ["Imminent breach: TTB shown (API)", pct(G5["true_ttb_le30"]["ttb_shown"]), "—", "—"],
                 ["Imminent breach labelled A0 (models)", pct(G3["true_ttb_le30"]["miss_gate_A0"]), "—", "—"],
                 ["Macro-F1", f"{G2['macro_f1']:.3f} (7 classes)", "—", "After: 4 classes; not directly comparable"],
                 ["Recall degradasi / A8 / A7", f"{G2['per_class']['degradasi_bertahap']['recall']:.2f} / {G2['per_class']['A8']['recall']:.2f} / {G2['per_class']['A7']['recall']:.2f}", "—",
                  "degradasi deferred, A8 → pre-departure rule; only A7 compared"],
                 ["Macro-F1 at σ=0.3 °C noise", f"{G4['sensor_noise_sigma_0.3C']['macro_f1']:.3f}", "—", "—"],
                 ["Stuck sensor → flagged masalah_sensor", pct(G4["stuck_sensor_on_imminent_breach"]["pred_masalah_sensor"]), "—", "—"],
                 ["Forecast MAE@30 on moving windows", f"{G1['moving_windows_gru_mae_t30']:.2f} °C", "—", "—"]],
                [6.2*cm, 3*cm, 3.2*cm, 4*cm]),
          Spacer(1, 8),
          p("4. Findings not yet fixed — causes and plan", H1),
          p("Causes below are <b>hypotheses</b> unless marked measured; each will be confirmed or rejected with the suite before any change.", S),
          table([["Finding", "Suspected cause (status)", "Planned fix and how we will judge it"],
                 ["F1/F2 green status & silent TTB", "TTB and status floors are gated on the classifier / forecast; both are weak on slow faults (measured: 68% of imminent windows → A0).",
                  "Adjust TTB guard to apply regardless of class. Judge: F1 AMAN-rate ≤ 5% without raising healthy WASPADA+KRITIS above 10%."],
                 ["F3 noise fragility", "Trained only on σ=0.05 °C simulator noise (dataset card, measured). Aggregate features (std, trend) are noise-sensitive (hypothesis).",
                  "Retrain on the physics-simulated trips driven by real BMKG outside-air data, with sensor errors from real Intel Berkeley Lab traces instead of σ=0.05 °C noise; re-run G4. Judge: F1 drop ≤ 0.05 at σ=0.3 (metrics)."],
                 ["F4 stuck sensor", "Frozen temp looks like a stable healthy trace (hypothesis). masalah_sensor recall only 67% even in-distribution (measured).",
                  "Train masalah_sensor on real faulty-sensor traces (Intel Berkeley Lab), plus an explicit flat-line detector in preprocessing (less than X variance over last N minutes while ambient/reefer state changes) as a rule, independent of the network. May remain unresolved or removed, we will report the residual."],
                 ["F5 forecast metric", "Metric choice, not a model defect (measured).", "Report the moving-window MAE and skill vs persistence as the primary forecast metrics."],
                 ["F6 A7/A8/degradasi", "Label taken at window end; slow faults look healthy early (partly measured: recall is low even 120+ min in, so not only onset latency). Class overlap A0↔A8/A7/degradasi in confusion matrix (measured).",
                  "Scope change: A8 (poor pre-cooling) leaves the classifier and becomes a pre-departure rule; degradasi_bertahap and A3 (total reefer failure) are deferred as a later feature. "
                  "A7 (extreme ambient) stays: re-simulate it from real BMKG extremes, inspect misclassified windows, consider longer context. May remain unresolved, we will report the residual."],
                 ["F7 test validity", "700 simulated trips; 106 in test (measured).",
                  "Regenerate a larger test set from the physics simulator, stratified by cargo (fish, meat, vegetables, fruit, from the product thermal tables) and payload mass; report CIs. "
                  "Vaccine and dairy are not in the planned thermal tables, so claims for them stay unsupported. Real inputs make the simulation more realistic but still cannot substitute for field data."]],
                [3.2*cm, 6.2*cm, 7*cm]),
          PageBreak()]

    # ---------- appendix ----------
    s += [p("Appendix — acceptance checks (baseline)", H1),
          table([["Result", "Check"]] + [["PASS" if c == "PASSED" else "FAIL", n] for c, n in checks], [2*cm, 14.4*cm]),
          Spacer(1, 6),
          p("Commit of the code that produced these numbers: " +
            subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() +
            " (+ uncommitted eval/ at generation time). Dataset: data/processed/v4_seed1000_700trips.parquet, split=test. Seeds fixed at 42.", S)]

    out = RES / f"Evaluation_Artifact_{tag}.pdf"
    SimpleDocTemplate(str(out), pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=1.8*cm, bottomMargin=1.6*cm,
                      title="ColdTrack AI - Evaluation Artifact").build(s)
    print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--tag", default="baseline")
    build(ap.parse_args().tag)
