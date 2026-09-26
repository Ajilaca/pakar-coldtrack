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
    A1, A2, A3 = G5["true_ttb_le30"], G3["true_ttb_le30"], G4["stuck_sensor_on_imminent_breach"]
    N3 = G4["sensor_noise_sigma_0.3C"]
    s += [p("ColdTrack AI — Evaluation Artifact (Baseline)", H1),
          p("AIC COMPFEST 18 Final · Smart Logistics · version tag: <b>%s</b>" % tag, S),
          Spacer(1, 4), p("What is this document?", H2),
          p("ColdTrack AI watches the sensors of a refrigerated truck and warns the operator before the cargo gets too warm. "
            "This document reports how well the <b>prototype from the qualifying round</b> does that <b>today, before any improvement</b>. "
            "We tested it the way an operator would use it: feed in the last 60 minutes of sensor readings, then look at the status "
            "(<b>AMAN</b> = safe, <b>WASPADA</b> = warning, <b>KRITIS</b> = critical) and at the countdown to the moment the cargo leaves its safe temperature range. "
            f"The test used {R['n_trips']} simulated trips ({R['n_windows']:,} one-hour snapshots) that the model never saw while it was being trained.", B),
          p("Key terms", H2),
          table([["Term", "Meaning"],
                 ["Breach", "The cargo temperature goes outside its safe range (for example above 8 °C for vaccines)."],
                 ["Countdown (time-to-breach)", "Minutes left before a breach. This is the main feature of the product."],
                 ["Window", "One snapshot: the last 60 minutes of sensor readings from one truck."],
                 ["Imminent breach", "A window where a breach really happens within 30 minutes (this is when the operator must act)."],
                 ["Fault types", "A0 = healthy · A1 = door left open · A3 = cooling unit fully off · A7 = sudden extreme outside heat · A8 = poor pre-cooling · "
                                 "degradasi = cooling slowly getting weaker · masalah_sensor = faulty temperature sensor."]],
                [4.2*cm, 12.2*cm]),
          Spacer(1, 4), p("Summary", H2),
          p(f"The prototype passed <b>{n_pass} of {len(checks)}</b> checks. It is good at predicting temperature, "
            f"and the scores we reported in the qualifying round are confirmed (fault-identification score {G2['macro_f1']:.2f}, forecast error {G1['mae_t30']:.2f} °C). "
            "However, when we looked at what an operator would actually see, the system often <b>fails to raise the alarm when it matters most</b>:", B),
          table([["#", "What we found", "Why it matters", "Severity"],
                 ["F1", f"When the cargo was less than 30 minutes from a breach, the system still showed <b>green (AMAN) in {pct(A1['AMAN'])} of cases</b> (about 1 in 3). "
                        f"It showed warning in {pct(A1['WASPADA'])} and critical in only {pct(A1['KRITIS'])}.", "A false “all clear” is the most dangerous mistake for a cold chain.", "Critical"],
                 ["F2", f"The countdown is often missing when it is needed. The two AI models alone show it in only {pct(A2['shown_rate'])} of urgent cases "
                        f"({pct(A1['ttb_shown'])} once the backup rule in the server is added). Reason: the system first decides if the truck is healthy, "
                        f"and it wrongly said “healthy” for {pct(A2['miss_gate_A0'])} of the urgent cases, which hides the countdown.", "The main feature of the product does not appear in many urgent situations.", "Critical"],
                 ["F3", f"Sensor noise confuses it. With small random noise (0.3 °C, common in real sensors) urgent cases judged “healthy” rise from {pct(G4['clean']['imminent_pred_A0_rate'])} to {pct(N3['imminent_pred_A0_rate'])}. "
                        "Our training data had almost no noise (0.05 °C).", "Real trucks have noisier sensors than our simulator.", "High"],
                 ["F4", f"A frozen (stuck) temperature sensor is read as “healthy”: {pct(A3['pred_A0_healthy'])} of such cases, and only {pct(A3['pred_masalah_sensor'])} are flagged as a sensor problem.", "A stuck sensor hides real warming.", "High"],
                 ["F5", f"The temperature-forecast score looks good but proves little. Simply guessing “the temperature stays the same” has an error of {G1['naive_persistence_mae_t30']:.3f} °C, "
                        f"which is as good as our AI ({G1['mae_t30']:.3f} °C). In almost all test snapshots the temperature barely moves (only {G1['moving_windows_n']} of {R['n_windows']:,} change by 1 °C or more).", "The forecast target we passed does not show the AI is useful.", "High"],
                 ["F6", f"Three fault types are mostly missed: sudden outside heat (A7) is found {pct(G2['per_class']['A7']['recall'])} of the time, poor pre-cooling (A8) {pct(G2['per_class']['A8']['recall'])}, "
                        f"and slowly weakening cooling (degradasi) only {pct(G2['per_class']['degradasi_bertahap']['recall'])}.", "These faults would go unnoticed.", "High"],
                 ["F7", "Our test data is too small to prove much. Some fault types appear in only 2–4 test trips, and there are no urgent cases for vaccine, frozen meat or fish.", "Some results could be luck, and the vaccine use case is untested.", "Medium"]],
                [1*cm, 9.2*cm, 4.6*cm, 1.6*cm]), PageBreak()]

    # ---------- (a) test suite ----------
    s += [p("1. How we tested", H1),
          p("Idea: test what the <b>user really sees</b> (status, countdown, fault type), not only the AI models inside. "
            "We built 5 groups of tests and 23 pass/fail checks. Each check states a minimum we consider acceptable for a real fleet operator.", B),
          table([["Test group", "What we did", "What we measured", "What this can NOT tell us"],
                 ["1. Temperature forecast", f"Compared the predicted temperature 15, 30 and 60 minutes ahead with what really happened in {R['n_windows']:,} test snapshots. Also compared with a “no change” guess.",
                  "Average error in °C, worst-case error, and error only on snapshots where the temperature really changes.",
                  "Most snapshots are calm, so the average hides performance when it matters. It also says nothing about whether an alarm would ring."],
                 ["2. Fault identification", "Asked which of the 7 conditions each snapshot shows. Repeated the scoring 200 times on random samples of trips to see how uncertain the numbers are.",
                  "How many real faults of each type were found, how many alarms were correct, and a confusion chart.",
                  "A fault type with only 2–3 test trips cannot be judged reliably."],
                 ["3. Urgent-breach warnings", "Took only snapshots where the cargo really was 30 minutes or less from a breach, and checked whether the countdown was shown and how accurate it was.",
                  "Share of urgent cases with a countdown, average countdown error, and why the countdown was missing.",
                  "In qualifying we reported “7 min error” for these cases, but that ignored the cases where no countdown appeared at all."],
                 ["4. Stress tests", "Added sensor noise (0.1 / 0.3 / 0.5 °C), shifted the clock by 7 hours (a time-zone mix-up), and froze the temperature sensor during a real warming.",
                  "Fault-identification score, and how many urgent cases are judged healthy.",
                  "The noise is artificial, so this shows sensitivity, not the exact error on real trucks."],
                 ["5. Whole-system check", f"Sent {G5['n_requests']:,} snapshots through the real server (the same request the app sends) and read the status and countdown like a user.",
                  "Status by how close the breach really is, countdown shown, response time, and match with the raw AI models.",
                  "The “correct answer” comes from our simulator, not from real trucks."]],
                [2.8*cm, 5.5*cm, 4.2*cm, 3.9*cm]),
          Spacer(1, 6),
          p("Existing checks from the qualifying round (run for reference, not graded here): the server tests pass 24/24 and the data-format tests pass 7/7. "
            "Simple comparison models (XGBoost, linear, Isolation Forest) re-run on the same test data score about the same as our AI on the forecast (error 0.19 °C) and better on fault identification (0.67 vs 0.58).", B),
          p("Limits of this evaluation: only 106 test trips (27 with a fault); all data is simulated; the pass marks are our own choices, set after seeing the qualifying numbers, so they are open to challenge. "
            "Technical details of every test are in Appendix A.", S),
          PageBreak()]

    # ---------- (b) baseline findings ----------
    s += [p("2. What we found (where the system fails, with evidence)", H1),
          p("F1 · Urgent cases shown as “safe”", H2),
          Image(str(RES / f"{tag}_fig_status.png"), width=13*cm, height=6.1*cm),
          p("How to read the chart: each bar is a group of snapshots, grouped by how soon the cargo <i>really</i> leaves its safe range. Colors show what the system displayed. "
            "The top bar (breach within 30 minutes) should be almost all red, but a third of it is green.", B),
          p(f"Why: the status mostly follows the temperature forecast, which is roughly “no change” (F5). A rule that raises the status when a countdown exists does not help, "
            f"because the countdown is hidden whenever the system believes the truck is healthy. When the countdown is shown it is accurate "
            f"(average error {G5['api_ttb_mae_when_shown_true_le30']:.1f} minutes), so the problem is <b>missing warnings, not wrong numbers</b>. "
            f"Also, only {pct(G5['true_ttb_30_60']['WASPADA']+G5['true_ttb_30_60']['KRITIS'])} of snapshots 30–60 minutes before a breach get any warning, "
            "so the 60-minute early-warning setting never really triggers.", B),
          p("F2 · The countdown depends on the weakest part", H2),
          table([[f"Urgent cases (breach within 30 min, n={A2['n']})", "Share"],
                 ["Countdown shown by the two AI models", pct(A2["shown_rate"])],
                 ["Hidden because the system judged the truck “healthy”", pct(A2["miss_gate_A0"])],
                 ["Hidden because the system judged “faulty sensor”", pct(A2["miss_gate_sensor_class"])],
                 ["Hidden because the countdown was above the 30-minute display limit", pct(A2["miss_ttb_model_above_cap"])],
                 ["Average countdown error when shown / if a missing countdown counts as “30 min”", f"{A2['mae_when_shown']:.1f} min / {A2['mae_all_incl_missing_as_30']:.1f} min"]],
                [11.4*cm, 5*cm]),
          p("F3 / F4 · Noise and a stuck sensor", H2), Image(str(RES / f"{tag}_fig_noise.png"), width=12.5*cm, height=5.1*cm),
          p("Left: the fault-identification score drops as we add noise. Right: the more noise, the more urgent cases are wrongly judged “healthy”. "
            f"When the temperature sensor freezes during a real warming, {pct(A3['pred_A0_healthy'])} of cases are judged healthy and only {pct(A3['pred_masalah_sensor'])} are flagged as a sensor problem.", B),
          p(f"Two things we checked and found <b>fine</b>: (1) a 7-hour clock shift (time zone) barely changes results (score {G4['hour_shift_utc_vs_wib_+7h']['macro_f1']:.2f} vs {G4['clean']['macro_f1']:.2f}); "
            f"(2) the server gives the same answers as the raw AI models (average difference {G5['parity_forecast_mean_abs_diff_C']:.3f} °C), so nothing is lost between them.", B),
          PageBreak(),
          p("F5 · The forecast score is not a strong proof", H2),
          table([["Average error of the 30-minute forecast (°C, lower is better)", "All snapshots", f"Only snapshots where temperature changes (n={G1['moving_windows_n']})"],
                 ["Our AI (deployed)", f"{G1['mae_t30']:.3f}", f"{G1['moving_windows_gru_mae_t30']:.2f}"],
                 ["Guess “same temperature as now”", f"{G1['naive_persistence_mae_t30']:.3f}", f"{G1['moving_windows_persistence_mae_t30']:.2f}"],
                 ["Continue the trend of the last 5 minutes", f"{G1['naive_linear_extrapolation_mae_t30']:.3f}", f"{G1['moving_windows_extrapolation_mae_t30']:.2f}"]],
                [8*cm, 3.6*cm, 4.8*cm]),
          p("Our target (error below 0.8 °C) was met, but the “no change” guess meets it too. The honest result is on the few snapshots where the temperature really moves: there our AI is about 20% better than the “no change” guess.", B),
          p("F6 · Which faults are found", H2), Image(str(RES / f"{tag}_fig_confusion.png"), width=10.5*cm, height=8.0*cm),
          p("How to read the chart: each row is the real condition, each column is what the system said. A perfect system has 1.00 on the diagonal. "
            "Rows for A7, A8 and degradasi are mostly spread into the “A0” (healthy) column, meaning these faults are called healthy.", B),
          table([["Fault type", "Test snapshots", "Test trips", "Alarms that were correct", "Real faults found"]] +
                [[{"A0": "A0 · healthy", "A1": "A1 · door open", "A3": "A3 · cooling unit off", "A7": "A7 · sudden outside heat", "A8": "A8 · poor pre-cooling",
                   "degradasi_bertahap": "degradasi · weakening cooling", "masalah_sensor": "masalah_sensor · faulty sensor"}[k],
                  v["support"], {"A0": 95, "A1": 4, "A3": 7, "A7": 5, "A8": 6, "degradasi_bertahap": "5", "masalah_sensor": "11"}[k],
                  pct(v["precision"]), pct(v["recall"])] for k, v in G2["per_class"].items()],
                [5.2*cm, 2.6*cm, 2.2*cm, 3.4*cm, 3*cm]),
          p("An odd pattern: after a fault starts, the system finds it best 30–120 minutes later (about " +
            pct(G2["recall_by_minutes_since_onset"]["30-60"]["recall_non_A0"]) + ") and worst after 2 hours (" + pct(G2["recall_by_minutes_since_onset"]["120-inf"]["recall_non_A0"]) +
            "). So “the fault is too new to see” does not explain the misses. We do not yet know the reason (see section 4).", B),
          p("F7 · The test data is too thin", H2),
          p("Urgent cases (breach within 30 minutes) exist in the test data only for vegetables/fruit (%d snapshots) and dairy (%d). There are none for vaccine, frozen meat or fish, "
            "so the main vaccine use case has no evidence for urgent cases. The uncertainty of the overall fault-identification score is large: somewhere between %.2f and %.2f (95%% range)."
            % (G3["by_cargo_true_le30"]["sayur_buah"]["n"], G3["by_cargo_true_le30"]["produk_susu"]["n"], *G2["macro_f1_ci95"]), B),
          PageBreak()]

    # ---------- (c) before/after ----------
    s += [p("3. Before and after improvement", H1),
          p("Status: <b>baseline only</b>. The “After” column stays empty until an improvement is built and measured with the same tests.", B),
          p("<b>Planned improvement 1 (in progress, not yet measured)</b>", H2),
          p("• <b>Use real inputs instead of made-up ones.</b> Real outside temperature and humidity for Indonesia (BMKG, 2010–2020); "
            "real product heat tables (fish, meat, vegetables, fruit) with the payload weight entered by the user; and real faulty-sensor recordings (Intel Berkeley Lab) to copy real sensor errors. "
            "This lets the product handle a wider range of goods.", B),
          p("• <b>Simulate the truck with physics.</b> Heat enters from the outside air, and a heavier load warms up more slowly.", B),
          p("• <b>Focus on 4 situations:</b> healthy, door open, sudden extreme outside heat, and faulty sensor. "
            "Cooling unit fully off (A3) and weakening cooling (degradasi) are postponed to a later version. Poor pre-cooling (A8) becomes a simple check before the truck leaves.", B),
          p("Because of this, the “After” results cover only 4 situations, and the fault-identification score over 4 situations cannot be compared directly with the 7-situation baseline.", S),
          table([["What we measure (test data)", "Before (baseline)", "After", "Comment"],
                 ["Checks passed", f"{n_pass} of {len(checks)}", "—", "—"],
                 ["Urgent cases shown as “safe” (whole system)", pct(A1["AMAN"]), "—", "Goal: 5% or less"],
                 ["Urgent cases with a countdown (whole system)", pct(A1["ttb_shown"]), "—", "Goal: 80% or more"],
                 ["Urgent cases judged “healthy” by the AI", pct(A2["miss_gate_A0"]), "—", "Goal: 10% or less"],
                 ["Fault-identification score", f"{G2['macro_f1']:.2f} (7 situations)", "—", "After: 4 situations, not directly comparable"],
                 ["Faults found: weakening cooling / poor pre-cooling / outside heat", f"{pct(G2['per_class']['degradasi_bertahap']['recall'])} / {pct(G2['per_class']['A8']['recall'])} / {pct(G2['per_class']['A7']['recall'])}", "—",
                  "First two postponed or moved to a rule; only outside heat is compared"],
                 ["Fault-identification score with 0.3 °C sensor noise", f"{N3['macro_f1']:.2f}", "—", "Goal: drop of 0.05 or less"],
                 ["Frozen sensor flagged as sensor problem", pct(A3["pred_masalah_sensor"]), "—", "Goal: 50% or more"],
                 ["Forecast error where temperature really changes", f"{G1['moving_windows_gru_mae_t30']:.2f} °C", "—", "—"]],
                [6.6*cm, 3.2*cm, 2*cm, 4.6*cm]),
          Spacer(1, 8),
          p("4. Findings not yet fixed — causes and plan", H1),
          p("Causes below are <b>hypotheses</b> unless marked measured; each will be confirmed or rejected with the suite before any change.", S),
          table([["Finding", "Suspected cause (status)", "Planned fix and how we will judge it"],
                 ["F1/F2 green status & silent TTB", "TTB and status floors are gated on the classifier / forecast; both are weak on slow faults (measured: 68% of imminent windows → A0).",
                  "Adjust TTB guard to apply regardless of class. Judge: F1 AMAN-rate ≤ 5% without raising healthy WASPADA+KRITIS above 10%."], 
                 ["F3 noise fragility", "Trained only on σ=0.05 °C simulator noise (dataset card, measured). Aggregate features (std, trend) are noise-sensitive (hypothesis).",
                  "Retrain on the physics-simulated trips driven by real BMKG outside-air data, with sensor errors from real Intel Berkeley Lab traces instead of σ=0.05 °C noise; re-run G4. Judge: F1 drop ≤ 0.05 at σ=0.3 (metrics)."],
                 ["F4 stuck sensor", "Frozen temp looks like a stable healthy trace (hypothesis). masalah_sensor recall only 67% even in-distribution (measured).",
                  "Train masalah_sensor on real faulty-sensor traces (Intel Berkeley Lab), plus an explicit flat-line detector in preprocessing (less than X variance over last N minutes while ambient/reefer state changes) as a rule, independent of the network. May remain unresolved or removed, will be reported."],
                 ["F5 forecast metric", "Metric choice, not a model defect (measured).", "Report the moving-window MAE and skill vs persistence as the primary forecast metrics."],
                 ["F6 A7/A8/degradasi", "Label taken at window end; slow faults look healthy early (partly measured: recall is low even 120+ min in, so not only onset latency). Class overlap A0↔A8/A7/degradasi in confusion matrix (measured).",
                  "Scope change: A8 (poor pre-cooling) leaves the classifier and becomes a pre-departure rule; degradasi_bertahap and A3 (total reefer failure) are deferred as a later feature. "
                  "A7 (extreme ambient) stays: re-simulate it from real BMKG extremes, inspect misclassified windows, consider longer context. May remain unresolved, will be reported."],
                 ["F7 test validity", "700 simulated trips; 106 in test (measured).",
                  "Regenerate a larger test set from the physics simulator, stratified by cargo (fish, meat, vegetables, fruit, from the product thermal tables) and payload mass; report CIs. "
                  "Vaccine and dairy are not in the planned thermal tables, so claims for them stay unclear. Real inputs make the simulation more realistic but still cannot substitute for field data."]],
                [3.2*cm, 6.2*cm, 7*cm]),
          PageBreak()]

    # ---------- appendix ----------
    s += [p("Appendix A — technical detail of the test groups", H1),
          p("System under test: <font face='Courier'>coldtrack.onnx</font> (GRU) + <font face='Courier'>coldtrack_ttb.onnx</font> (XGBoost) + backend rule engine, evaluated as deployed on the held-out test split of dataset v4 (split by trip). "
            "Reproduce: <font face='Courier'>python -m eval.run_eval --tag baseline; pytest eval/test_baseline.py</font>.", B),
          table([["Group", "Test cases", "Metric(s)", "Why this metric / what it does NOT capture"],
                 ["G1 Forecast", "sliced by fault mode and cargo; compared to naive persistence and linear extrapolation", "MAE t+15/30/60, p95 and max error, MAE on windows that really move",
                  "MAE is dominated by the ~99% of windows where nothing changes; hence the persistence comparison and the moving-windows slice."],
                 ["G2 Classification", "7 classes; bootstrap over trips (200×) for CIs; recall vs minutes since fault onset", "per-class P/R/F1, macro-F1, PR-AUC, confusion matrix",
                  "Macro-F1 hides which fault is missed; windows of one trip are highly correlated, so window-level CIs would be far too narrow."],
                 ["G3 Imminent breach", "windows with true TTB ≤ 10 / ≤ 30 min, gated exactly like backend/app/inference.py", "TTB shown-rate, MAE when shown, miss reasons",
                  "The qualifying-round 'MAE 7.08 min for TTB ≤ 30' conditions on the true answer and ignores silent misses."],
                 ["G4 Robustness", "sensor noise σ∈{0.1,0.3,0.5} °C; +7 h hour shift; stuck sensor injected into imminent-breach windows", "macro-F1, forecast MAE, imminent-breach A0 rate",
                  "Training data is a clean simulator (σ=0.05 °C); perturbations are synthetic, so they show sensitivity, not real-world error."],
                 ["G5 End-to-end API", "every 2nd test window POSTed to /api/v1/analyze via FastAPI TestClient", "status × true-TTB bucket, TTB shown, latency, parity with raw ONNX",
                  "Ground truth = simulator time_to_breach (threshold = cargo max limit; equals config.yaml)."]],
                [2.3*cm, 5.3*cm, 3.8*cm, 5*cm]),
          Spacer(1, 6),
          p("Also: XGBoost/Linear/IsolationForest baselines (ml/baselines.py) re-run on the test split: forecast MAE@30 linear 0.192 / XGB 0.190; macro-F1 XGB 0.667; PR-AUC XGB 0.749, IsolationForest 0.352. "
            "The committed baseline_metrics.json is from the v3 validation split and is stale.", B),
          PageBreak(),
          p("Appendix B — acceptance checks (baseline)", H1),
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
