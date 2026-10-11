"""Diagnosis providers (config.yaml: model.diagnosis_provider): both load, both serve /analyze,
and the v3 ONNX matches its PyTorch reference.

Parity tolerance (documented in tests/fixtures/v3_parity.json, same as ml/export_onnx.TOLERANCE):
an output passes if max|onnx - torch| < 1e-4 OR max|onnx - torch| / max|torch| < 1e-4. The reference
was produced by bench/b7_fixture_paritas.py, which retrained v3 (seed 1000) and verified it matches
the G3-tested ONNX before writing the fixture. No torch is needed to run these tests.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import onnxruntime as ort
import pytest
from fastapi.testclient import TestClient

from app import main
from app.inference import BACKEND_DIR, PROVIDERS, HybridInferenceEngine
from app.schemas import AnalyzeRequest

FIXTURE = Path(__file__).parent / "fixtures" / "v3_parity.npz"
RULE_LABELS = {"pintu_terbuka", "suhu_muatan_mendekati_batas"}
LABELS = {
    "v3": {"normal_sehat", "pintu_terbuka_lama", "reefer_mati_total", "kejutan_ambien_ekstrem",
           "prapendinginan_buruk", "degradasi_bertahap", "masalah_sensor"} | RULE_LABELS,
    "checkpoint2": {"normal_sehat", "pintu_terbuka_lama", "kejutan_ambien_ekstrem", "masalah_sensor"} | RULE_LABELS,
}
TZ = timezone(timedelta(hours=7))


def readings(n=90, temp=5.0, slope=0.0, door_at=None):
    t0 = datetime(2026, 10, 1, 8, 0, tzinfo=TZ)
    return [{"ts": (t0 + timedelta(minutes=i)).isoformat(), "temp_c": temp + slope * i, "humidity": 70.0,
             "ambient_c": 31.0, "door_open": door_at is not None and i >= door_at, "reefer_on": True,
             "speed_kmh": 40.0, "harsh_events": 0, "solar_radiation": 300.0} for i in range(n)]


@pytest.mark.parametrize("name", PROVIDERS)
def test_provider_loads_and_predicts(name):
    eng = HybridInferenceEngine(provider=name)
    assert eng.is_ready, f"provider {name} gagal memuat model ONNX"
    req = AnalyzeRequest(shipment_id="T", cargo_profile="vaksin_2_8C", readings=readings())
    out = eng.predict(req.readings, req.cargo_profile)
    assert set(out["forecast"]) == {"t15", "t30", "t60"}
    assert out["failure_mode"]["label"] in LABELS[name]
    assert 0.0 <= out["failure_mode"]["confidence"] <= 1.0
    probs = out["failure_mode"]["probabilities"]
    if name == "v3" and probs is not None:
        # dikirim hanya bila label = kelas teratas model (bukan label aturan / penyaringan sensor)
        assert set(probs) == LABELS["v3"] - RULE_LABELS
        assert abs(sum(probs.values()) - 1.0) < 1e-3
        assert out["failure_mode"]["label"] == max(probs, key=probs.get)
    elif name == "checkpoint2":
        assert probs is None


def test_unknown_provider_fails_loudly():
    with pytest.raises(ValueError):
        HybridInferenceEngine(provider="v99")


def test_v3_onnx_matches_pytorch_reference():
    ref = np.load(FIXTURE)
    tol = json.loads(FIXTURE.with_suffix(".json").read_text(encoding="utf-8"))["toleransi"]
    sess = ort.InferenceSession(str(BACKEND_DIR / "models" / "coldtrack_v3.onnx"), providers=["CPUExecutionProvider"])
    got = sess.run(None, {"window": ref["window"]})
    for name, g in zip(["forecast_c", "failure_prob", "time_to_breach_min"], got):
        diff = float(np.abs(g - ref[name]).max())
        rel = diff / max(float(np.abs(ref[name]).max()), 1e-9)
        assert diff < tol["abs"] or rel < tol["rel"], f"{name}: maxabs {diff:.3g}, rel {rel:.3g}"


@pytest.mark.parametrize("name", PROVIDERS)
def test_analyze_end_to_end_both_providers(name, monkeypatch):
    eng = HybridInferenceEngine(provider=name)
    monkeypatch.setattr(main, "inference_engine", eng)
    client = TestClient(main.app)
    for payload_readings in (readings(), readings(slope=0.08), readings(door_at=50)):
        res = client.post("/api/v1/analyze", json={"shipment_id": "TRK-E2E", "cargo_profile": "vaksin_2_8C",
                                                    "readings": payload_readings})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["diagnosis_provider"] == name
        assert body["model_version"] == eng.version
        assert body["status"] in {"AMAN", "WASPADA", "KRITIS"}
        assert body["failure_mode"]["label"] in LABELS[name]
        assert (body["failure_mode"]["label"] == "normal_sehat") <= (body["status"] == "AMAN")
        assert len(body["actions"]) == 3


@pytest.mark.parametrize("name", PROVIDERS)
def test_data_gap_flags_diagnosis_and_caps_confidence(name, monkeypatch):
    """Jendela berlubang (bacaan hilang) = di luar distribusi latih: ditandai, keyakinan <= 0,5,
    status tetap dihitung mesin fisika. Data lengkap tidak terpengaruh."""
    monkeypatch.setattr(main, "inference_engine", HybridInferenceEngine(provider=name))
    client = TestClient(main.app)
    lengkap = readings()
    berlubang = lengkap[:60] + lengkap[66:]          # 6 menit hilang di 60 bacaan terakhir
    r1 = client.post("/api/v1/analyze", json={"shipment_id": "T", "readings": lengkap}).json()
    r2 = client.post("/api/v1/analyze", json={"shipment_id": "T", "readings": berlubang}).json()
    assert r1["data_lengkap"] is True and r1["catatan_data"] is None
    assert r2["data_lengkap"] is False and "6 menit" in r2["catatan_data"]
    assert r2["failure_mode"]["confidence"] <= 0.5
    assert r2["status"] in {"AMAN", "WASPADA", "KRITIS"}


def test_v3_sensor_fault_only_from_rule_layer():
    """masalah_sensor dari model v3 tidak dipakai sebagai label; kelas non-sensor teratas yang dipilih."""
    from app.inference import pilih_label_v3

    labels = ["normal_sehat", "pintu_terbuka_lama", "masalah_sensor"]
    # sensor teratas dibuang; gangguan lain < 0,5 -> normal_sehat, keyakinan 1 - 0,16 (aturan checkpoint-2)
    label, conf = pilih_label_v3(np.array([0.06, 0.16, 0.78]), labels)
    assert label == "normal_sehat" and abs(conf - 0.84) < 1e-9
    # sensor teratas dibuang; gangguan lain >= 0,5 -> dipakai
    assert pilih_label_v3(np.array([0.0, 0.55, 0.45]), labels)[0] == "pintu_terbuka_lama"
    # kelas teratas bukan sensor -> argmax biasa
    assert pilih_label_v3(np.array([0.70, 0.10, 0.20]), labels)[0] == "normal_sehat"
