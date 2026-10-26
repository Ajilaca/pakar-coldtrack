"""Aturan diagnosis A3/A8 (app/inference.aturan_diagnosis, B12): kelas yang model kenali hanya dari satu sinyal."""

import numpy as np
import pandas as pd
import pytest

from app.inference import (
    REEFER_MATI_MENIT,
    aturan_diagnosis,
    inference_engine,
    pilih_label_v3,
)
from app.schemas import TelemetryReading

T0 = pd.Timestamp("2026-10-20T01:00:00Z")


def trip(temp, reefer=None, door=None) -> list[TelemetryReading]:
    n = len(temp)
    reefer = np.ones(n, bool) if reefer is None else reefer
    door = np.zeros(n, bool) if door is None else door
    return [TelemetryReading.model_validate({
        "ts": (T0 + pd.Timedelta(minutes=k)).isoformat(), "temp_c": round(float(temp[k]), 2), "humidity": 80.0,
        "ambient_c": 31.0, "door_open": bool(door[k]), "reefer_on": bool(reefer[k]), "speed_kmh": 40.0,
        "harsh_events": 0, "solar_radiation": 300.0}) for k in range(n)]


def satu_baris(temp, reefer, label="normal_sehat", sensor=0):
    feats = pd.DataFrame({"temp_c": temp, "reefer_on": reefer.astype(float)})
    out = pd.DataFrame({"label": [label], "confidence": [0.9], "sensor_status": [sensor]})
    return out, feats


def test_reefer_mati_dan_suhu_naik():
    n = 120
    reefer = np.r_[np.ones(90), np.zeros(n - 90)]
    temp = np.r_[np.full(90, 5.0), 5.0 + 0.05 * np.arange(1, n - 89)]
    out, feats = satu_baris(temp, reefer)
    aturan_diagnosis(out, feats, t_hi=8.0)
    assert out.label.iat[0] == "reefer_mati_total" and out.confidence.iat[0] == 1.0


@pytest.mark.parametrize("menit_mati,naik", [(REEFER_MATI_MENIT - 1, 0.05), (30, 0.0)])
def test_reefer_mati_singkat_atau_suhu_datar_bukan_aturan_a3(menit_mati, naik):
    n = 120
    reefer = np.r_[np.ones(n - menit_mati), np.zeros(menit_mati)]
    temp = np.r_[np.full(n - menit_mati, 5.0), 5.0 + naik * np.arange(1, menit_mati + 1)]
    out, feats = satu_baris(temp, reefer)
    aturan_diagnosis(out, feats, t_hi=8.0)
    assert out.label.iat[0] == "normal_sehat"


def test_sensor_dari_aturan_tidak_ditimpa():
    reefer = np.r_[np.ones(60), np.zeros(60)]
    temp = np.r_[np.full(60, 5.0), 5.0 + 0.05 * np.arange(1, 61)]
    out, feats = satu_baris(temp, reefer, label="masalah_sensor", sensor=2)
    aturan_diagnosis(out, feats, t_hi=8.0)
    assert out.label.iat[0] == "masalah_sensor"


def test_model_tidak_memberi_prapendinginan_buruk():
    labels = ["normal_sehat", "prapendinginan_buruk", "pintu_terbuka_lama", "masalah_sensor"]
    assert pilih_label_v3(np.array([0.1, 0.8, 0.05, 0.05]), labels) == ("normal_sehat", pytest.approx(0.95))
    assert pilih_label_v3(np.array([0.0, 0.4, 0.6, 0.0]), labels)[0] == "pintu_terbuka_lama"


def test_prapendinginan_buruk_sepanjang_trip():
    """Vaksin 2-8 C dimuat 10 C lalu turun ke 4 C: fakta tingkat trip, tetap A8 setelah masuk rentang."""
    rng = np.random.default_rng(5)
    temp = np.maximum(10.0 - 0.05 * np.arange(240), 4.0) + rng.normal(0, 0.05, 240)
    rs = trip(temp)
    for sampai in (80, 200):
        hasil, _ = inference_engine.predict_last(rs[:sampai], "vaksin_2_8C", 1000.0)
        assert hasil["failure_mode"]["label"] == "prapendinginan_buruk"
    sehat, _ = inference_engine.predict_last(trip(4.0 + rng.normal(0, 0.05, 200)), "vaksin_2_8C", 1000.0)
    assert sehat["failure_mode"]["label"] != "prapendinginan_buruk"


def test_riwayat_dipotong_memakai_suhu_awal_trip():
    """worker-infer: riwayat 240 menit terakhir masih di atas batas, suhu awal dari bacaan pertama trip."""
    rs = trip(9.0 + np.random.default_rng(3).normal(0, 0.05, 400))     # derau sensor, bukan garis datar
    awal = (pd.Timestamp(rs[0].ts), 10.0)
    hasil, _ = inference_engine.predict_last(rs[-240:], "vaksin_2_8C", 1000.0, awal=awal)
    assert hasil["failure_mode"]["label"] == "prapendinginan_buruk"
    normal, _ = inference_engine.predict_last(rs[-240:], "vaksin_2_8C", 1000.0, awal=(awal[0], 5.0))
    assert normal["failure_mode"]["label"] != "prapendinginan_buruk"
