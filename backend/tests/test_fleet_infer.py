"""Fase 3 armada tanpa DB: jendela, paritas worker vs POST /analyze, predict_last, sensor health, insiden, kerugian."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import main
from app.fleet import incidents as inc
from app.fleet.devices import perlu_diperbarui
from app.fleet.loss import per_insiden, ringkas
from app.fleet.window import KOLOM, bangun_jendela
from app.inference import (
    PROVIDERS,
    HybridInferenceEngine,
    cargo_params,
    readings_to_trip,
)
from app.models.base import Konteks
from app.models.condition import HybridCondition
from app.models.orchestrator import Orchestrator
from app.models.sensor_health_rules import nilai
from app.preprocess import features_per_minute

FLEET = Path(__file__).resolve().parents[1] / "data" / "fleet"
T0 = datetime(2026, 10, 11, 1, 0, tzinfo=UTC)      # 08:00 WIB
SEED = pd.read_parquet(FLEET / "telemetry.parquet")
TRIPS = {t["truck_id"]: t for t in json.loads((FLEET / "trips.json").read_text(encoding="utf-8"))}


def baris(n=90, temp=5.0, mulai=T0, buang=(), **kol) -> pd.DataFrame:
    df = pd.DataFrame({"ts": [mulai + timedelta(minutes=i) for i in range(n)], "temp_c": temp, "humidity": 70.0,
                       "ambient_c": 31.0, "door_open": False, "reefer_on": True, "speed_kmh": 40.0, "harsh_events": 0,
                       "solar_radiation": 300.0, "lat": -6.2, "lon": 106.8, **kol})
    return df.drop(index=list(buang)).reset_index(drop=True)


def seed_truk(truck_id: str, n: int) -> pd.DataFrame:
    """n menit pertama trip seed tanpa paket hilang (paritas butuh masukan identik)."""
    g = SEED[SEED.truck_id == truck_id].dropna(subset=["temp_c"]).head(n).reset_index(drop=True)
    g["ts"] = [T0 + timedelta(minutes=i) for i in range(len(g))]
    g["harsh_events"] = g["harsh_events"].fillna(0).astype(int)
    g["solar_radiation"] = g["solar_radiation"].fillna(0.0)
    return g[["ts", *KOLOM]]


# --- jendela -----------------------------------------------------------------------------------------

def test_jendela_kurang_60_menit_menunggu_data():
    j = bangun_jendela(baris(45), T0 + timedelta(minutes=45))
    assert j.keadaan == "MENUNGGU_DATA" and j.n_menit == 45 and not j.readings


def test_jendela_offline_tidak_ada_data():
    j = bangun_jendela(baris(90), T0 + timedelta(minutes=89 + 11), offline_setelah_menit=10)
    assert j.keadaan == "TIDAK_ADA_DATA" and j.last_ts == T0 + timedelta(minutes=89)
    assert bangun_jendela(pd.DataFrame(), T0).keadaan == "TIDAK_ADA_DATA"


def test_celah_pendek_diisi_celah_panjang_tidak():
    j = bangun_jendela(baris(90, buang=range(70, 74)), T0 + timedelta(minutes=90))   # celah 4 menit
    assert j.keadaan == "OK" and j.data_lengkap and j.menit_diisi == 4 and len(j.readings) == 90
    j = bangun_jendela(baris(90, buang=range(70, 78)), T0 + timedelta(minutes=90))   # celah 8 menit
    assert j.keadaan == "OK" and not j.data_lengkap and j.menit_hilang == 8 and len(j.readings) == 82
    assert "8 menit data hilang" in j.catatan()


def test_duplikat_dalam_satu_menit_ambil_terakhir():
    df = baris(61)
    extra = df.iloc[[60]].copy()
    extra["ts"] = extra["ts"] + timedelta(seconds=30)
    extra["temp_c"] = 6.5
    j = bangun_jendela(pd.concat([df, extra]), T0 + timedelta(minutes=61))
    assert len(j.readings) == 61 and j.readings[-1].temp_c == 6.5


def test_jam_fitur_dalam_wib():
    j = bangun_jendela(baris(60), T0 + timedelta(minutes=60))
    assert j.readings[0].ts.hour == 8                      # 01:00 UTC = 08:00 WIB
    assert features_per_minute(j.readings)["hour_of_day"].iloc[0] == 8


# --- paritas worker vs POST /analyze --------------------------------------------------------------

client = TestClient(main.app)


@pytest.mark.parametrize("truck_id", ["B 3036 WN", "AB 1448 NN", "E 8659 FR", "H 3072 XS", "D 8839 XT"])
def test_paritas_worker_vs_analyze(truck_id):
    """Masukan tanpa celah: keluaran provider kondisi worker == POST /analyze (status, risiko, TTB, forecast,
    diagnosis). Bacaan /analyze dikirim dengan offset WIB, sama dengan yang dilihat model di worker."""
    trip = TRIPS[truck_id]
    rows = seed_truk(truck_id, 150)
    for n in (60, 100, 150):
        j = bangun_jendela(rows.head(n), T0 + timedelta(minutes=n))
        w = HybridCondition().run(Konteks(truck_id, T0, j, trip["cargo_profile"], trip["mass_kg"]))
        body = {"shipment_id": truck_id, "cargo_profile": trip["cargo_profile"], "mass_kg": trip["mass_kg"],
                "readings": [json.loads(r.model_dump_json()) for r in j.readings]}
        a = client.post("/api/v1/analyze", json=body).json()
        assert w["status"] == a["status"]
        assert w["risk_index"] == a["risk_index"]
        assert w["time_to_breach_min"] == a["time_to_breach_min"]
        assert w["ttb_model_min"] == pytest.approx(a["ttb_model_min"], abs=1e-6)
        assert w["forecast"] == pytest.approx(a["forecast"], abs=1e-6)
        assert w["failure_mode"]["label"] == a["failure_mode"]["label"]
        assert w["failure_mode"]["confidence"] == pytest.approx(a["failure_mode"]["confidence"], abs=1e-6)
        assert w["failure_mode"]["probabilities"] == a["failure_mode"]["probabilities"]
        assert w["data_lengkap"] is a["data_lengkap"] is True
        assert w["model_version"] == a["model_version"]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_predict_last_sama_dengan_semua_jendela(provider):
    eng = HybridInferenceEngine(provider)
    for truck_id in ("B 3036 WN", "H 3072 XS"):
        trip = TRIPS[truck_id]
        j = bangun_jendela(seed_truk(truck_id, 120), T0 + timedelta(minutes=120))
        prod = cargo_params(trip["cargo_profile"], trip["mass_kg"])
        t, f = readings_to_trip(j.readings, prod), features_per_minute(j.readings)
        penuh = eng.analyze_trip(t, prod, f).iloc[-1]
        akhir = eng.analyze_trip(t, prod, f, last_only=True).iloc[-1]
        for k in penuh.index:
            if isinstance(penuh[k], float | np.floating):   # float32: batch 1 vs n beda ~1e-8 (GEMM)
                assert akhir[k] == pytest.approx(penuh[k], abs=1e-5, nan_ok=True), k
            else:
                assert akhir[k] == penuh[k], k


def test_data_tidak_lengkap_hanya_menggantikan_aman():
    rows = seed_truk("B 3036 WN", 120).drop(index=range(100, 110)).reset_index(drop=True)
    j = bangun_jendela(rows, T0 + timedelta(minutes=120))
    trip = TRIPS["B 3036 WN"]
    w = HybridCondition().run(Konteks("B 3036 WN", T0, j, trip["cargo_profile"], trip["mass_kg"]))
    assert not w["data_lengkap"]
    assert w["status"] in ("DATA_TIDAK_LENGKAP", "WASPADA", "KRITIS")
    assert w["status"] != "AMAN"
    assert w["failure_mode"]["confidence"] <= 0.5
    # truk panas: WASPADA/KRITIS tidak disembunyikan oleh catatan data
    panas = baris(120, temp=9.5, buang=range(100, 110))
    w = HybridCondition().run(Konteks("X", T0, bangun_jendela(panas, T0 + timedelta(minutes=120)), "vaksin_2_8C", 800))
    assert w["status"] in ("WASPADA", "KRITIS") and not w["data_lengkap"]


def test_menunggu_data_tanpa_model():
    j = bangun_jendela(baris(30), T0 + timedelta(minutes=30))
    w = HybridCondition().run(Konteks("X", T0, j, "vaksin_2_8C", 800))
    assert w["status"] == "MENUNGGU_DATA" and w["forecast"] is None and w["failure_mode"] is None


def test_orkestrator_registry():
    o = Orchestrator({"condition": "hybrid", "sensor_health": "rules_v0"})
    assert {c["kind"] for c in o.cards()} == {"condition", "sensor_health"}
    with pytest.raises(ValueError):
        Orchestrator({"sensor_health": "berkeley_v1"})


# --- sensor health v0 -------------------------------------------------------------------------------

def _sh(df, batt=2.9):
    return nilai(df.temp_c.to_numpy(float), df.door_open.to_numpy(float), df.ambient_c.to_numpy(float),
                 df.speed_kmh.to_numpy(float), batt)


@pytest.mark.parametrize("truck_id", [t for t, v in TRIPS.items() if v["failure_mode_v4"] == "A0"])
def test_sensor_sehat_pada_trip_normal_seed(truck_id):
    r = _sh(seed_truk(truck_id, 180))
    assert r["grade"] == "Sehat", r


def test_sensor_datar_lama_dan_baterai_kritis():
    datar = baris(180, temp=4.0)
    r = _sh(datar, batt=2.35)
    assert r["grade"] == "Ganti" and r["score"] < 50
    assert any("datar" in a for a in r["alasan"]) and any("Baterai kritis" in a for a in r["alasan"])
    assert _sh(baris(10))["grade"] == "Data kurang"


def test_sensor_lompatan_dan_derau():
    rng = np.random.default_rng(0)
    df = baris(180, temp=4.0 + rng.normal(0, 0.5, 180))
    df.loc[[50, 120], "temp_c"] += 9.0
    r = _sh(df)
    assert r["komponen"]["lompatan"] >= 2 and r["komponen"]["derau_c"] > 4 * 0.073
    assert r["grade"] in ("Perlu cek", "Ganti")


# --- insiden ----------------------------------------------------------------------------------------

def _terbuka(**kol):
    return {"id": 1, "phase": "TERDETEKSI", "status_puncak": "WASPADA", "breach_at": None, "recovered_at": None, **kol}


def test_insiden_kondisi_dibuka_di_awal_episode_dan_eskalasi():
    r = inc.langkah("kondisi", "B 1 A", "AMAN", "WASPADA", None, T0, label="pintu_terbuka", trip_id=1,
                    cargo_value_idr=1000)
    assert r.buka["phase"] == "TERDETEKSI" and r.buka["status_puncak"] == "WASPADA" and r.buka["jenis"] == "kondisi"
    assert r.buka["cargo_value_idr"] == 1000
    assert r.notifikasi[0]["level"] == "waspada" and r.events[0]["actor"] == "Sistem"
    r = inc.langkah("kondisi", "B 1 A", "WASPADA", "KRITIS", _terbuka(), T0)
    assert r.buka is None and r.ubah == {"status_puncak": "KRITIS"} and r.notifikasi[0]["level"] == "kritis"


def test_insiden_tidak_dibuka_ulang_dalam_episode_yang_sama():
    assert inc.langkah("kondisi", "B 1 A", "KRITIS", "KRITIS", None, T0).kosong
    assert inc.langkah("kondisi", "B 1 A", "MENUNGGU_DATA", "DATA_TIDAK_LENGKAP", None, T0).kosong
    assert inc.langkah("data", "B 1 A", "MENUNGGU_DATA", "DATA_TIDAK_LENGKAP", None, T0).kosong


def test_putus_data_terpisah_dari_kondisi():
    # offline membuka insiden data (tanpa nilai muatan), bukan insiden kondisi
    r = inc.langkah("data", "B 1 A", "AMAN", "TIDAK_ADA_DATA", None, T0, trip_id=1, cargo_value_idr=1000)
    assert r.buka["jenis"] == "data" and r.buka["cargo_value_idr"] is None and r.notifikasi[0]["level"] == "info"
    assert inc.langkah("kondisi", "B 1 A", "AMAN", "TIDAK_ADA_DATA", None, T0).kosong
    # data kembali dengan status WASPADA: insiden data pulih (tanpa notifikasi), insiden kondisi baru dibuka
    d = inc.langkah("data", "B 1 A", "TIDAK_ADA_DATA", "WASPADA", _terbuka(status_puncak="TIDAK_ADA_DATA"), T0)
    assert d.ubah == {"recovered_at": T0} and not d.notifikasi
    k = inc.langkah("kondisi", "B 1 A", "TIDAK_ADA_DATA", "WASPADA", None, T0)
    assert k.buka is not None and k.buka["detected_at"] == T0
    # putus lagi: tanpa notifikasi baru
    d = inc.langkah("data", "B 1 A", "AMAN", "TIDAK_ADA_DATA",
                    _terbuka(status_puncak="TIDAK_ADA_DATA", recovered_at=T0), T0)
    assert d.ubah == {"recovered_at": None} and not d.notifikasi


def test_breach_otomatis_gagal():
    r = inc.langkah("kondisi", "B 1 A", "KRITIS", "KRITIS", _terbuka(phase="DITUGASKAN", status_puncak="KRITIS"), T0,
                    breach=True)
    assert r.ubah["phase"] == "GAGAL" and r.ubah["breach_at"] == T0 and r.events[0]["from_phase"] == "DITUGASKAN"
    r = inc.langkah("kondisi", "B 1 A", "AMAN", "KRITIS", None, T0, breach=True)   # deteksi dan breach bersamaan
    assert r.buka["phase"] == "GAGAL" and r.buka["breach_at"] == T0


def test_pulih_lalu_kambuh_dinotifikasi():
    r = inc.langkah("kondisi", "B 1 A", "WASPADA", "AMAN", _terbuka(), T0)
    assert r.ubah == {"recovered_at": T0} and r.notifikasi[0]["title"].startswith("Kembali AMAN")
    r = inc.langkah("kondisi", "B 1 A", "AMAN", "WASPADA", _terbuka(recovered_at=T0), T0)
    assert r.buka is None and r.ubah == {"recovered_at": None} and r.notifikasi[0]["title"].startswith("Kambuh")


# --- kerugian dan perangkat ---------------------------------------------------------------------------

def test_kerugian_per_insiden_dan_ringkasan():
    breach = per_insiden({"cargo_value_idr": 1_000_000, "phase": "GAGAL", "breach_at": T0 + timedelta(minutes=40),
                          "detected_at": T0, "recovered_at": None})
    diatasi = per_insiden({"cargo_value_idr": 500_000, "phase": "DITANGANI", "breach_at": None, "detected_at": T0,
                           "recovered_at": T0})
    terbuka = per_insiden({"cargo_value_idr": 200_000, "phase": "TERDETEKSI", "breach_at": None, "detected_at": T0,
                           "recovered_at": None}, risk_index=0.5)
    assert breach["kerugian_terjadi_idr"] == 1_000_000 and breach["lead_time_min"] == 40.0
    assert diatasi["berhasil_diatasi_idr"] == 500_000 and diatasi["hasil"] == "diatasi"
    assert terbuka["nilai_berisiko_idr"] == 100_000
    data = per_insiden({"jenis": "data", "cargo_value_idr": 900_000, "phase": "TERDETEKSI", "breach_at": None,
                        "detected_at": T0, "recovered_at": T0}, risk_index=0.9)
    assert data["berhasil_diatasi_idr"] == data["nilai_berisiko_idr"] == 0      # putus data: tanpa nilai kerugian
    s = ringkas([breach, diatasi, terbuka])
    assert (s["n_breach"], s["n_diatasi"], s["lead_time_median_min"]) == (1, 1, 40.0)


def test_perlu_diperbarui():
    dev = {"firmware": "1.4.2", "gateway_version": "0.9.3", "calibrated_at": "2025-09-01", "battery_v": 2.35,
           "online": False, "last_status_at": T0 - timedelta(hours=30)}
    cfg = {"firmware_terbaru": "1.5.0", "gateway_terbaru": "0.9.3", "kalibrasi_maks_hari": 180,
           "offline_lama_jam": 24, "skor_sensor_min": 50}
    kode = {t["kode"]: t for t in perlu_diperbarui(dev, {"score": 40, "grade": "Ganti"}, T0, cfg)}
    assert set(kode) == {"firmware_usang", "kalibrasi", "baterai", "sensor", "offline_lama"}
    assert kode["firmware_usang"]["jenis"] == "software" and kode["baterai"]["tingkat"] == "kritis"
    assert perlu_diperbarui({"firmware": "1.5.0", "battery_v": 2.9, "online": True}, None, T0, cfg) == []
