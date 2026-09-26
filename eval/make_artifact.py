"""Build the iteration Evaluation Artifact (before/after) from eval/results/<tag>_results.json.

Usage: python -m eval.make_artifact [--tag iter1]
Output: eval/results/Evaluation_Artifact_Iteration.pdf and iteration_fig_*.png.
"Before" numbers come from results/baseline_results.json (old contract, archived).
The baseline PDF itself is archived and can no longer be rebuilt (its models were removed).
"""

import argparse
import json
import os
import subprocess
import sys
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
OUT_PDF = RES / "Evaluation_Artifact_Iteration.pdf"
FIG = "iteration_fig_{}.png"
GREY, BEFORE, AFTER = "#555555", "#9E9E9E", "#1565C0"
STATUS_COL = [("AMAN", "#4CAF50"), ("WASPADA", "#FFB300"), ("KRITIS", "#D32F2F")]
BUCKETS = [("true_ttb_le30", "≤30 min"), ("true_ttb_30_60", "30–60 min"), ("true_ttb_gt60", ">60 min"), ("no_breach", "no breach")]


def figs(B, R):
    b5, r5 = B["G5_end_to_end_api"], R["G5_end_to_end_api"]
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 2.9), sharey=True)
    for ax, G, title in [(axes[0], b5, "Before (baseline)"), (axes[1], r5, "After (iteration 1)")]:
        left = np.zeros(len(BUCKETS))
        for st, col in STATUS_COL:
            v = np.array([G[k][st] for k, _ in BUCKETS])
            ax.barh([n for _, n in BUCKETS], v, left=left, color=col, label=st); left += v
        ax.set_xlim(0, 1); ax.set_title(title, fontsize=9); ax.tick_params(labelsize=8)
        ax.set_xlabel("share of snapshots (server status)", fontsize=8)
    axes[0].invert_yaxis(); axes[0].set_ylabel("breach really happens in", fontsize=8)
    axes[1].legend(ncol=3, fontsize=7, loc="lower center", bbox_to_anchor=(0, 1.08))
    fig.tight_layout(); fig.savefig(RES / FIG.format("status"), dpi=170); plt.close(fig)

    pc, ev = B["G2_classification"]["per_class"], R["G2_events"]["per_event"]
    names = ["door open", "outside heat", "faulty sensor"]
    before = [pc["A1"]["recall"], pc["A7"]["recall"], pc["masalah_sensor"]["recall"]]
    after = [ev["door"]["recall"], ev["shock"]["recall"], ev["sensor"]["recall"]]
    x = np.arange(3)
    fig, ax = plt.subplots(figsize=(5.6, 2.6))
    ax.bar(x - .18, before, .36, color=BEFORE, label="before"); ax.bar(x + .18, after, .36, color=AFTER, label="after")
    ax.axhline(.5, color=GREY, lw=.8, ls=":"); ax.set_xticks(x); ax.set_xticklabels(names, fontsize=8)
    ax.set_ylim(0, 1); ax.set_ylabel("real faults named correctly", fontsize=8); ax.legend(fontsize=7); ax.tick_params(labelsize=8)
    fig.tight_layout(); fig.savefig(RES / FIG.format("events"), dpi=170); plt.close(fig)

    keys = ["clean", "sensor_noise_sigma_0.1C", "sensor_noise_sigma_0.3C", "sensor_noise_sigma_0.5C"]
    lab = ["clean", "σ 0.1", "σ 0.3", "σ 0.5"]
    b4, r4 = B["G4_robustness"], R["G4_robustness"]
    fig, ax = plt.subplots(1, 2, figsize=(6.8, 2.6))
    ax[0].plot(lab, [b4[k]["imminent_pred_A0_rate"] for k in keys], "o-", color=BEFORE, label="before: judged healthy")
    ax[0].plot(lab, [r4[k]["imminent_aman_rate"] for k in keys], "o-", color=AFTER, label="after: status AMAN")
    ax[0].set_title("Urgent cases treated as safe", fontsize=9); ax[0].legend(fontsize=7)
    ax[1].plot(lab, [r4[k]["mean_event_recall"] for k in keys], "o-", color=AFTER)
    ax[1].set_title("After: faults named correctly (mean)", fontsize=9)
    for a in ax: a.set_ylim(0, 1); a.tick_params(labelsize=8)
    fig.tight_layout(); fig.savefig(RES / FIG.format("noise"), dpi=170); plt.close(fig)


def checks(tag):
    pt = subprocess.run([sys.executable, "-m", "pytest", "eval/test_baseline.py", "-q", "-p", "no:cacheprovider", "-rA"],
                        capture_output=True, text=True, env={**os.environ, "EVAL_TAG": tag}).stdout
    return [(ln.split()[0], ln.split()[1].split("::")[1]) for ln in pt.splitlines() if ln.startswith(("PASSED", "FAILED"))]


def build(tag):
    R = json.loads((RES / f"{tag}_results.json").read_text())
    B = json.loads((RES / "baseline_results.json").read_text())
    figs(B, R)
    ck = checks(tag)
    n_pass = sum(c == "PASSED" for c, _ in ck)

    G1, G2, G3, G4, G5 = (R[k] for k in ["G1_forecast", "G2_events", "G3_imminent_breach", "G4_robustness", "G5_end_to_end_api"])
    b1, b2, b3, b4, b5 = (B[k] for k in ["G1_forecast", "G2_classification", "G3_imminent_breach", "G4_robustness", "G5_end_to_end_api"])
    ev, pc = G2["per_event"], b2["per_class"]
    I30, bI30 = G5["true_ttb_le30"], b5["true_ttb_le30"]
    stuck, bstuck = G4["stuck_sensor_on_imminent_breach"], b4["stuck_sensor_on_imminent_breach"]
    a0, ba0 = G5["by_true_mode_status"]["A0"], b5["by_true_mode_status"]["A0"]
    bias = G1["mae_t30_by_cargo"]

    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=15, spaceAfter=6)
    H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=11.5, spaceBefore=8, spaceAfter=3)
    Bd = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=12)
    S = ParagraphStyle("s", parent=Bd, fontSize=7.5, leading=9.5, textColor=colors.HexColor(GREY))
    C = ParagraphStyle("c", parent=Bd, fontSize=8, leading=10)
    p = lambda t, st=Bd: Paragraph(t, st)
    pct = lambda x: f"{100 * x:.0f}%"

    def table(rows, widths, fs=8):
        t = Table([[p(str(c), C) for c in r] for r in rows], colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#BBBBBB")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EAF0"))]))
        return t

    s = []
    # ---------- intro + summary ----------
    s += [p("ColdTrack AI: Evaluation Artifact (Iteration 1)", H1),
          p(f"AIC COMPFEST 18 Final · Smart Logistics · results tag: {tag} · compared with the baseline artifact", S),
          Spacer(1, 4), p("What is this document?", H2),
          p("ColdTrack AI watches the sensors of a refrigerated truck and warns the operator before the cargo gets too warm. "
            "The baseline artifact measured the prototype from the qualifying round. This document measures the rebuilt system "
            "with the same test trips, so the two can be compared.", Bd),
          p("The rebuilt system has three parts. A physics engine estimates the cargo temperature from the cabin sensor, "
            "counts down to a breach, and sets the status (AMAN = safe, WASPADA = warning, KRITIS = critical). "
            "A set of rules checks whether the temperature sensor itself is faulty. A learned model (GRU) names three events "
            "(door left open for 20 minutes or more, sudden outside heat, faulty sensor) and forecasts the cargo temperature. "
            "The countdown no longer depends on the fault classifier, which was the main failure of the baseline.", Bd),
          p(f"Test data: {R['n_trips']} simulated trips ({R['n_windows']:,} one-minute snapshots, each with the trip history up to that minute), "
            "the same held-out trips as the baseline. The rebuilt model was trained on a new physics simulator, not on these trips, "
            "so for it this is data from a different generator. The baseline was trained on data from the same generator as the test trips.", Bd),
          p("Summary", H2),
          p(f"The rebuilt system passed {n_pass} of {len(ck)} checks (the baseline passed 8 of 23 older checks; the lists differ because the outputs changed). "
            f"The most dangerous baseline failure is fixed: when a breach was less than 30 minutes away, the baseline showed green in {pct(bI30['AMAN'])} of cases; "
            f"the rebuilt system shows green in {pct(I30['AMAN'])}. On these test trips, the rebuilt system still fails in other ways:", Bd),
          table([["#", "What we found", "Why it matters", "Severity"],
                 ["N1", f"Urgent cases are never shown as green, but they are never shown as critical either: {pct(I30['WASPADA'])} warning, {pct(I30['KRITIS'])} critical. "
                        f"The countdown is shown in {pct(I30['ttb_shown'])} of urgent cases (baseline {pct(bI30['ttb_shown'])}).",
                  "The operator is warned but not told how much time is left.", "Critical"],
                 ["N2", f"Healthy trucks get a warning in {pct(a0['WASPADA'] + a0['KRITIS'])} of snapshots (baseline {pct(ba0['WASPADA'] + ba0['KRITIS'])}).",
                  "Too many false warnings teach operators to ignore them.", "High"],
                 ["N3", f"The temperature forecast is off by {G1['mae_t30']:.2f} °C on average (baseline {b1['mae_t30']:.2f} °C). Guessing “no change” gives {G1['naive_persistence_mae_t30']:.2f} °C.",
                  "The forecast chart would mislead the operator.", "High"],
                 ["N4", f"Door open and sudden outside heat are rarely named: {pct(ev['door']['recall'])} and {pct(ev['shock']['recall'])} (baseline {pct(pc['A1']['recall'])} and {pct(pc['A7']['recall'])}).",
                  "The operator is not told what to fix.", "High"],
                 ["N5", f"Small sensor noise (0.1 °C) drops correct fault names from {pct(G4['clean']['mean_event_recall'])} to {pct(G4['sensor_noise_sigma_0.1C']['mean_event_recall'])}.",
                  "Real sensors are noisier than the simulator.", "High"],
                 ["N6", f"A sensor that freezes 30 minutes before a real breach is not flagged ({pct(stuck['flagged_sensor'])}, baseline {pct(bstuck['pred_masalah_sensor'])}), "
                        f"but the status is green in only {pct(stuck['status_aman'])} of those cases (baseline {pct(bstuck['pred_A0_healthy'])} judged healthy).",
                  "A stuck sensor still hides the fault type.", "Medium"],
                 ["N7", "The test trips come from the old generator and have no cargo mass; urgent cases exist only for dairy and vegetables/fruit (plus one vaccine snapshot).",
                  "Several results above may reflect the gap between the two simulators, not the truck.", "Medium"]],
                [1*cm, 9.2*cm, 4.6*cm, 1.6*cm]),
          PageBreak()]

    # ---------- before / after ----------
    s += [p("1. Before and after", H1),
          p("Same test trips and, where the measurement still exists, the same pass mark. Server numbers come from real requests to the API; "
            f"the rebuilt system was sent {G5['n_requests']:,} requests (every 10th snapshot), the baseline {b5['n_requests']:,}.", Bd),
          table([["What we measure", "Before (baseline)", "After (iteration 1)", "Goal"],
                 ["Checks passed", "8 of 23", f"{n_pass} of {len(ck)}", "lists differ"],
                 ["Urgent cases (breach within 30 min) shown as green", pct(bI30["AMAN"]), pct(I30["AMAN"]), "5% or less"],
                 ["Urgent cases shown as critical", pct(bI30["KRITIS"]), pct(I30["KRITIS"]), "no goal set"],
                 ["Urgent cases with a countdown", pct(bI30["ttb_shown"]), pct(I30["ttb_shown"]), "80% or more"],
                 ["Healthy snapshots with a warning or critical status", pct(ba0["WASPADA"] + ba0["KRITIS"]), pct(a0["WASPADA"] + a0["KRITIS"]), "10% or less"],
                 ["Door open named correctly", pct(pc["A1"]["recall"]), pct(ev["door"]["recall"]), "50% or more"],
                 ["Sudden outside heat named correctly", pct(pc["A7"]["recall"]), pct(ev["shock"]["recall"]), "50% or more"],
                 ["Faulty sensor named correctly", pct(pc["masalah_sensor"]["recall"]), pct(ev["sensor"]["recall"]), "50% or more"],
                 ["Forecast error at 30 min", f"{b1['mae_t30']:.2f} °C", f"{G1['mae_t30']:.2f} °C", "below 0.8 °C"],
                 ["Urgent cases treated as safe with 0.3 °C sensor noise", pct(b4["sensor_noise_sigma_0.3C"]["imminent_pred_A0_rate"]),
                  pct(G4["sensor_noise_sigma_0.3C"]["imminent_aman_rate"]), "50% or less"],
                 ["Sensor frozen during a real breach: flagged as sensor fault", pct(bstuck["pred_masalah_sensor"]), pct(stuck["flagged_sensor"]), "50% or more"],
                 ["Server response time (95th percentile)", f"{b5['latency_ms_p95']:.0f} ms", f"{G5['latency_ms_p95']:.0f} ms", "below 300 ms"]],
                [7*cm, 3*cm, 3*cm, 3.4*cm]),
          p("Before, “urgent treated as safe” meant the classifier said healthy, which hid the countdown. After, it means the status is AMAN. "
            "Fault names before came from 7 classes; after, from 3 events. The after-forecast predicts the cargo temperature, the baseline predicted the sensor reading; "
            "in the test trips the two are the same value.", S),
          Spacer(1, 4),
          Image(str(RES / FIG.format("status")), width=15*cm, height=5.9*cm),
          p("Each bar groups snapshots by how soon the cargo really leaves its safe range. The top bars should be red. "
            "Before, a third of the top bar was green; after, it is almost all amber.", Bd),
          PageBreak()]

    # ---------- findings ----------
    s += [p("2. What we found, with evidence", H1),
          p("N1 · Warning without a countdown", H2),
          p(f"In the {G3['true_ttb_le30']['n']} urgent snapshots, the physics countdown was above its 60-minute display limit in "
            f"{pct(G3['true_ttb_le30']['hidden_physics_ttb_above_60'])} of cases, so nothing was shown. Its error on these cases is "
            f"{G3['physics_ttb_mae_true_le30_ungated']:.0f} minutes. The countdown projects a breach only when the cabin air is already above the limit. "
            "In the test trips the urgent cases are slow drifts: the sensor sits at the limit (median 4.0 °C for 2 to 4 °C cargo) and creeps upward, "
            "so the projection says the cargo never crosses. The warning that does appear comes from a second rule (cargo within 1 °C of the limit). "
            f"The learned countdown (XGBoost) does no better here: error {G3['xgb_ttb_mae_true_le30']:.0f} minutes.", Bd),
          p("N2 · False warnings on healthy trucks", H2),
          p(f"Every warning on a healthy truck comes from the same rule: estimated cargo within 1 °C of the upper limit. "
            "Dairy and vegetables/fruit allow only 2 to 4 °C, and in the test trips healthy cargo runs around 3.3 °C, inside that last degree. "
            "The new simulator keeps the same cargo at its 2.8 °C setpoint, and in the developers' 600-trip test on that simulator "
            "healthy trips got no warnings at all (ml/CHECKPOINT2_CONTEXT.md).", Bd),
          p("N3 · Forecast pulled toward the new simulator's settings", H2),
          p(f"Average forecast error by cargo: vaccine {bias['vaksin_2_8C']:.2f} °C, frozen meat {bias['daging_beku']:.2f} °C, fish {bias['ikan_segar']:.2f} °C, "
            f"dairy {bias['produk_susu']:.2f} °C, vegetables/fruit {bias['sayur_buah']:.2f} °C. "
            "The forecast leans toward the cooling setpoint of the new simulator (for example it predicts frozen meat about 2 °C warmer than it is), "
            f"so it is worse than guessing “no change” ({G1['naive_persistence_mae_t30']:.2f} °C).", Bd),
          p("N4 · Door and outside heat not recognised", H2),
          Image(str(RES / FIG.format("events")), width=11*cm, height=5.1*cm),
          p("Door: even while the door is actually open, the model gives the door event a median probability of 0.04. "
            "In the test trips an open door barely changes the sensor reading; in the new simulator the cabin reading jumps 14 to 36 °C per minute, "
            "a known flaw of that simulator (no heat stored in walls and racks). The physics engine still raises the status to critical in 20 of the 58 snapshots with the door open.", Bd),
          p("Outside heat: the test trips model it as the truck standing still in the sun while the outside air does not warm "
            "(trip 43: 27.9 °C during the event against 30.1 °C before). The rebuilt model has no sunlight input and defines the event as the outside air rising "
            "to the hottest BMKG day, so the two definitions do not match.", Bd),
          p(f"Faulty sensor: {pct(ev['sensor']['recall'])} are named, all by the rules, with no false sensor alarms on other snapshots. "
            f"The learned sensor score is weak (ranking quality {ev['sensor']['gru_auc_vs_healthy']:.2f}, where 0.5 is chance), which is why the server uses the rules for this event.", Bd),
          p("N5 · Noise", H2),
          Image(str(RES / FIG.format("noise")), width=12.5*cm, height=4.8*cm),
          p(f"With 0.3 °C noise, urgent cases shown as green rise from {pct(G4['clean']['imminent_aman_rate'])} to "
            f"{pct(G4['sensor_noise_sigma_0.3C']['imminent_aman_rate'])} (baseline: {pct(b4['sensor_noise_sigma_0.3C']['imminent_pred_A0_rate'])} judged healthy). "
            f"At 0.5 °C the rate is {pct(G4['sensor_noise_sigma_0.5C']['imminent_aman_rate'])}; we have not yet found why it is lower than at 0.3 °C. "
            "Fault naming collapses already at 0.1 °C. A 7-hour clock shift changes almost nothing "
            f"(fault naming {pct(G4['hour_shift_utc_vs_wib_+7h']['mean_event_recall'])} against {pct(G4['clean']['mean_event_recall'])}).", Bd),
          p("N6 · Stuck sensor during a real breach", H2),
          p(f"We froze the sensor for the last 30 minutes of {stuck['n']} urgent snapshots. None were flagged as a sensor fault: "
            "the flat-reading rule needs 15 minutes of identical readings plus a sign that the temperature should have moved (door opened, outside air rising 3 °C), "
            f"or 60 minutes without one. The status still stayed amber in {pct(1 - stuck['status_aman'] - stuck['status_kritis'])} of these cases.", Bd),
          p("Checked and fine", H2),
          p(f"The server returns exactly what the batch scoring computes (status agreement {pct(G5['parity_status_agreement'])}, "
            f"forecast difference {G5['parity_forecast_max_abs_diff_C']:.2f} °C), with no errors in {G5['n_requests']:,} requests. "
            f"Response time is {G5['latency_ms_p50']:.0f} ms typical and {G5['latency_ms_p95']:.0f} ms at the 95th percentile, slower than the baseline "
            "because every request now carries the trip history.", Bd),
          PageBreak()]

    # ---------- next steps ----------
    s += [p("3. Causes and plan", H1),
          p("Causes marked (measured) were confirmed in this evaluation; the others are hypotheses to test with this suite before changing anything.", S),
          table([["Finding", "Cause", "Planned change and how we will judge it"],
                 ["N1 no countdown", "Countdown projects only when the cabin is above the limit; slow drifts never qualify (measured).",
                  "Add the recent sensor trend to the projection, or fall back to the learned countdown when physics cannot project. Judge: countdown shown in 80% of urgent cases."],
                 ["N2 false warnings", "1 °C margin rule on 2 °C wide cargo ranges (measured).",
                  "Scale the margin to the width of the cargo range. Judge: healthy warnings 10% or less while urgent cases stay 5% or less green."],
                 ["N3 forecast", "Forecast learned the new simulator's cooling setpoints (measured bias per cargo); cause of the bias itself is a hypothesis.",
                  "Include the observed recent temperature level more strongly (for example predict the change, not the level). Judge: error below 0.8 °C and better than “no change”."],
                 ["N4 door / heat", "New simulator: door jumps too fast, no sunlight (measured difference with test trips).",
                  "Add wall and rack heat storage and a sunlight term to the simulator, retrain. Judge: door and heat named in 50% or more."],
                 ["N5 noise", "Training noise 0.073 °C from lab sensors (known); event head sensitive to it (measured).",
                  "Train with noise from 0.05 to 0.5 °C. Judge: fault naming drops 0.05 or less at 0.3 °C."],
                 ["N6 stuck sensor", "Flat-reading rule needs context or 60 minutes (measured).",
                  "Flag a flat reading after 15 minutes when the estimated cargo should be warming. Judge: 50% flagged, 20% or less green."],
                 ["N7 test validity", "Test trips from a different generator; no mass; 2 cargo types with urgent cases (measured).",
                  "Build a second test set from the new simulator with real product and mass mixes, and keep this one as the out-of-distribution check."]],
                [3*cm, 5.8*cm, 7.6*cm]),
          PageBreak()]

    # ---------- appendix ----------
    s += [p("Appendix A: technical detail of the test groups", H1),
          p("System under test: backend/app/inference.py (core engine + coldtrack_gru.onnx + coldtrack_ttb.onnx) as served by /api/v1/analyze, "
            "on the held-out test split of dataset v4, split by trip, with the same window selection as the baseline. "
            f"Reproduce: python -m eval.run_eval --tag {tag}; pytest eval/test_baseline.py.", Bd),
          table([["Group", "Test cases", "Metric(s)", "What it does not capture"],
                 ["G1 Forecast", "every snapshot; compared with “no change” and 5-minute trend", "error at 15/30/60 min, worst case, error where temperature moves",
                  "Most snapshots are calm, hence the “no change” comparison."],
                 ["G2 Events", "v4 modes mapped A1 → door, A7 → heat, A5/A6 → sensor; A2/A3/A4/A8 have no event", "share named correctly, precision, ranking quality of the learned score",
                  "Uncovered faults are judged only through status and countdown."],
                 ["G3 Urgent breach", "snapshots with a true breach within 10 / 30 min", "countdown shown, status mix, why the countdown was hidden",
                  "Truth is the old simulator's breach time."],
                 ["G4 Robustness", "sensor noise 0.1/0.3/0.5 °C on whole trips; +7 h clock shift; sensor frozen for 30 min in urgent snapshots (every 3rd)",
                  "fault naming, urgent cases shown green, healthy warnings", "Perturbations are synthetic; they show sensitivity, not field error."],
                 ["G5 Server", "every 10th snapshot sent to /api/v1/analyze with the trip history", "status by breach bucket, countdown shown, latency, match with G1 to G3",
                  "Runs in-process (TestClient), so network time is excluded."]],
                [2.3*cm, 5.3*cm, 4.3*cm, 4.5*cm]),
          PageBreak(),
          p("Appendix B: acceptance checks (iteration 1)", H1),
          table([["Result", "Check"]] + [["PASS" if c == "PASSED" else "FAIL", n] for c, n in ck], [2*cm, 14.4*cm]),
          Spacer(1, 6),
          p("Code commit: " + subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() +
            " (plus uncommitted eval/ changes at generation time). Dataset: data/processed/v4_seed1000_700trips.parquet, split=test. "
            "Cargo mass: profile default (1,000 kg). Seeds fixed at 42.", S)]

    SimpleDocTemplate(str(OUT_PDF), pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=1.8*cm, bottomMargin=1.6*cm,
                      title="ColdTrack AI - Evaluation Artifact (Iteration 1)").build(s)
    print("wrote", OUT_PDF)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--tag", default="iter1")
    build(ap.parse_args().tag)
