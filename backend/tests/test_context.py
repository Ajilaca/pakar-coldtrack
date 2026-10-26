"""Konteks trip GRU v5 (preprocess.konteks_trip): riwayat dipotong + awal trip = riwayat penuh.

worker-infer hanya membaca history_cap_min menit terakhir, jadi menit_trip dan suhu_awal_muat datang dari
bacaan pertama trip (workers/infer.muat). Paritas dengan bench/experiments/b8/b8_lib.konteks_trip diuji
saat ekspor (bench/experiments/b8/b8_export_onnx.py) dan di sini bila repo lengkap tersedia.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.inference import inference_engine
from app.preprocess import KONTEKS_COLUMNS, features_per_minute, konteks_trip
from app.schemas import TelemetryReading

ROOT = Path(__file__).resolve().parents[2]
V = json.loads((Path(__file__).parent / "fixtures" / "edge_vectors.json").read_text(encoding="utf-8"))


def bacaan(sampai: int) -> list[TelemetryReading]:
    return [TelemetryReading.model_validate({k: v for k, v in m["bacaan"].items() if k != "edge"})
            for m in V["menit"][:sampai + 1]]


def awal_dari(rs: list[TelemetryReading]):
    return pd.Timestamp(rs[0].ts), float(np.mean([r.temp_c for r in rs[:5]]))


def test_provider_memakai_konteks():
    assert inference_engine.provider.pakai_konteks
    assert [i.name for i in inference_engine.provider.gru.get_inputs()] == ["window", "konteks"]
    assert len(KONTEKS_COLUMNS) == inference_engine.provider.gru.get_inputs()[1].shape[1]


def trip_sintetis(n: int = 400, seed: int = 7) -> list[TelemetryReading]:
    """Trip lebih panjang dari history_cap_min (240): suhu acak berjalan, pintu terbuka sekali."""
    rng = np.random.default_rng(seed)
    t0 = pd.Timestamp("2026-10-20T01:00:00Z")
    temp = 4.0 + np.cumsum(rng.normal(0, 0.03, n))
    return [TelemetryReading.model_validate({
        "ts": (t0 + pd.Timedelta(minutes=k)).isoformat(), "temp_c": round(float(temp[k]), 2), "humidity": 80.0,
        "ambient_c": 31.0, "door_open": 200 <= k < 215, "reefer_on": True, "speed_kmh": 40.0,
        "harsh_events": 0, "solar_radiation": 300.0}) for k in range(n)]


@pytest.mark.parametrize("akhir", [250, 320, 399])
def test_riwayat_240_menit_sama_dengan_penuh(akhir):
    penuh = trip_sintetis()[:akhir + 1]
    sisa = penuh[-240:]                                           # yang dibaca worker-infer (CAP_MIN)
    awal = awal_dari(penuh)
    f_penuh, f_sisa = features_per_minute(penuh), features_per_minute(sisa)
    k_penuh = konteks_trip(f_penuh, np.array([len(f_penuh) - 1]))
    k_sisa = konteks_trip(f_sisa, np.array([len(f_sisa) - 1]), *awal)
    np.testing.assert_allclose(k_sisa, k_penuh, rtol=1e-6, atol=1e-6)
    assert k_penuh[0, 0] == akhir                                 # menit_trip

    fc_penuh = inference_engine.forecast_last(penuh)
    assert inference_engine.forecast_last(sisa, awal) == pytest.approx(fc_penuh, abs=1e-6)
    assert inference_engine.forecast_last(sisa) != pytest.approx(fc_penuh, abs=1e-6)   # tanpa awal: konteks salah


def test_paritas_dengan_b8_lib():
    sys.path.insert(0, str(ROOT))
    b8 = pytest.importorskip("bench.experiments.b8.b8_lib")
    rs = bacaan(139)
    temp = np.array([r.temp_c for r in rs])
    temp[[20, 21, 22, 90]] = np.nan                               # celah: keduanya mengisi bacaan terakhir
    ok = ~np.isnan(temp)
    feats = features_per_minute([r for r, k in zip(rs, ok, strict=True) if k])
    got = konteks_trip(feats, np.arange(len(feats)))
    np.testing.assert_allclose(got, b8.konteks_trip(temp)[ok], rtol=1e-5, atol=1e-5)
