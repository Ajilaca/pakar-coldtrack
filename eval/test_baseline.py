"""Acceptance checks over eval/results/<tag>_results.json (hybrid-v3 contract).

Every check is a failure condition WE chose, with the reason next to it. Thresholds are the
baseline's wherever the metric carries over, so before/after stays comparable.
Run:  python -m eval.run_eval --tag iter1 && pytest eval/test_baseline.py -q
Failing checks are documented weaknesses, not bugs in the suite.

The baseline results (old 7-class contract, models since removed) can't be re-scored by these
checks; their 23 check results are archived in results/Evaluation_Artifact_baseline.pdf, App. B.
"""

import json
import os
from pathlib import Path

import pytest

TAG = os.getenv("EVAL_TAG", "iter1")
PATH = Path(__file__).parent / "results" / f"{TAG}_results.json"
R = json.loads(PATH.read_text()) if PATH.exists() else None
pytestmark = [
    pytest.mark.skipif(R is None, reason=f"run `python -m eval.run_eval --tag {TAG}` first"),
    pytest.mark.skipif(R is not None and R.get("contract") != "hybrid-v3",
                       reason=f"{TAG} uses the old 7-class contract; see Evaluation_Artifact_baseline.pdf"),
]

G1 = lambda: R["G1_forecast"]
G2 = lambda: R["G2_events"]
G3 = lambda: R["G3_imminent_breach"]
G4 = lambda: R["G4_robustness"]
API = lambda: R["G5_end_to_end_api"]


# --- G1 forecast -----------------------------------------------------------
def test_forecast_mae_t30_under_0_8C():
    assert G1()["mae_t30"] < 0.8

def test_forecast_worst_case_error_bounded():
    # a few large misses matter more than the mean for cold chain
    assert G1()["max_abs_err_t30"] < 2.0


# --- G2 events -------------------------------------------------------------
@pytest.mark.parametrize("event", ["door", "shock", "sensor"])
def test_recall_per_event_at_least_0_5(event):
    # a fleet operator needs each covered event named, not just "something is wrong"
    assert G2()["per_event"][event]["recall"] >= 0.5

def test_healthy_windows_not_labelled_as_fault():
    assert G2()["healthy_labelled_fault_rate"] <= 0.10


# --- G3 imminent breach ----------------------------------------------------
def test_imminent_breach_ttb_shown_at_least_80pct():
    assert G3()["true_ttb_le30"]["shown_rate"] >= 0.80

def test_imminent_breach_not_shown_as_safe():
    # replaces the baseline's "classifier gate" check: the new system has no gate, AMAN is the failure
    assert G3()["true_ttb_le30"]["AMAN"] <= 0.05

def test_test_split_covers_every_cargo_profile_for_imminent_breach():
    covered = [c for c, v in G3()["by_cargo_true_le30"].items() if v["n"] > 0]
    assert len(covered) == 5, f"only {covered} have imminent-breach test windows"


# --- G4 robustness ---------------------------------------------------------
def test_sensor_noise_0_3C_event_recall_drop_at_most_0_05():
    assert G4()["clean"]["mean_event_recall"] - G4()["sensor_noise_sigma_0.3C"]["mean_event_recall"] <= 0.05

def test_sensor_noise_0_3C_does_not_hide_imminent_breach():
    assert G4()["sensor_noise_sigma_0.3C"]["imminent_aman_rate"] <= 0.5

def test_timezone_shift_does_not_change_event_recall_much():
    assert abs(G4()["clean"]["mean_event_recall"] - G4()["hour_shift_utc_vs_wib_+7h"]["mean_event_recall"]) <= 0.05

def test_stuck_sensor_during_breach_is_flagged_not_safe():
    s = G4()["stuck_sensor_on_imminent_breach"]
    assert s["flagged_sensor"] >= 0.5 and s["status_aman"] <= 0.2


# --- G5 end-to-end API -----------------------------------------------------
def test_imminent_breach_never_green_more_than_5pct():
    assert API()["true_ttb_le30"]["AMAN"] <= 0.05

def test_imminent_breach_ttb_shown_by_api_at_least_80pct():
    assert API()["true_ttb_le30"]["ttb_shown"] >= 0.80

def test_healthy_windows_not_over_alerted():
    a0 = API()["by_true_mode_status"]["A0"]
    assert a0["WASPADA"] + a0["KRITIS"] <= 0.10

def test_api_no_http_errors_and_latency_p95_under_300ms():
    assert API()["n_http_errors"] == 0 and API()["latency_ms_p95"] < 300

def test_api_matches_batch_scoring():
    # serving path (HTTP, one request per minute) == eval batch path (analyze_trip over the whole trip)
    assert API()["parity_status_agreement"] == 1.0 and API()["parity_forecast_max_abs_diff_C"] < 0.05


# --- test-set power --------------------------------------------------------
def test_every_fault_mode_has_at_least_5_test_trips():
    few = {k: v for k, v in G2()["trips_per_true_mode"].items() if v < 5}
    assert not few, f"too few test trips to trust per-mode metrics: {few}"
