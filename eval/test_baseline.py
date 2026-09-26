"""Acceptance checks over eval/results/<tag>_results.json.

Every check is a failure condition WE chose, with the reason next to it.
Run:  python -m eval.run_eval --tag baseline && pytest eval/test_baseline.py -q
Failing checks are the documented weaknesses (see eval/README.md), not bugs in the suite.
"""

import json
import os
from pathlib import Path

import pytest

TAG = os.getenv("EVAL_TAG", "baseline")
PATH = Path(__file__).parent / "results" / f"{TAG}_results.json"
R = json.loads(PATH.read_text()) if PATH.exists() else None
pytestmark = pytest.mark.skipif(R is None, reason=f"run `python -m eval.run_eval --tag {TAG}` first")

API = lambda: R["G5_end_to_end_api"]
G2 = lambda: R["G2_classification"]
G3 = lambda: R["G3_imminent_breach"]
G4 = lambda: R["G4_robustness"]


# --- G1 forecast -----------------------------------------------------------
def test_forecast_mae_t30_under_0_8C():
    assert R["G1_forecast"]["mae_t30"] < 0.8

def test_forecast_worst_case_error_bounded():
    # a few large misses matter more than the mean for cold chain
    assert R["G1_forecast"]["max_abs_err_t30"] < 2.0


# --- G2 classification -----------------------------------------------------
def test_macro_f1_at_least_0_80():
    assert G2()["macro_f1"] >= 0.80

@pytest.mark.parametrize("cls", ["A1", "A3", "A7", "A8", "degradasi_bertahap", "masalah_sensor"])
def test_recall_per_fault_class_at_least_0_5(cls):
    # macro F1 hides which fault is missed; a fleet operator needs each one caught
    assert G2()["per_class"][cls]["recall"] >= 0.5

def test_anomaly_recall_at_least_0_8():
    assert G2()["anomaly_recall_at_argmax"] >= 0.8


# --- G3 deployed TTB on imminent breaches ----------------------------------
def test_imminent_breach_ttb_shown_directly_by_models_at_least_80pct():
    assert G3()["true_ttb_le30"]["shown_rate"] >= 0.80

def test_imminent_breach_not_gated_as_healthy():
    # TTB is hidden when the classifier says A0 -> a missed classification silences the alarm
    assert G3()["true_ttb_le30"]["miss_gate_A0"] <= 0.10

def test_test_split_covers_every_cargo_profile_for_imminent_breach():
    covered = [c for c, v in G3()["by_cargo_true_le30"].items() if v["n"] > 0]
    assert len(covered) == 5, f"only {covered} have imminent-breach test windows"


# --- G4 robustness ---------------------------------------------------------
def test_sensor_noise_0_3C_macro_f1_drop_at_most_0_05():
    assert G4()["clean"]["macro_f1"] - G4()["sensor_noise_sigma_0.3C"]["macro_f1"] <= 0.05

def test_sensor_noise_0_3C_does_not_hide_imminent_breach():
    assert G4()["sensor_noise_sigma_0.3C"]["imminent_pred_A0_rate"] <= 0.5

def test_timezone_shift_does_not_change_macro_f1_much():
    assert abs(G4()["clean"]["macro_f1"] - G4()["hour_shift_utc_vs_wib_+7h"]["macro_f1"]) <= 0.05

def test_stuck_sensor_during_breach_is_flagged_not_healthy():
    s = G4()["stuck_sensor_on_imminent_breach"]
    assert s["pred_masalah_sensor"] >= 0.5 and s["pred_A0_healthy"] <= 0.2


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

def test_api_matches_raw_onnx_forecast():
    assert API()["parity_forecast_mean_abs_diff_C"] < 0.05


# --- test-set power --------------------------------------------------------
def test_every_fault_mode_has_at_least_5_test_trips():
    few = {k: v for k, v in G2()["trips_per_true_mode"].items() if v < 5}
    assert not few, f"too few test trips to trust per-class metrics: {few}"
