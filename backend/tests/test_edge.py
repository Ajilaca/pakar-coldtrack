"""Hasil chip edge di cloud (app/edge.py): format paket, verifikasi rantai + HMAC, dan keluaran kondisi.

Vektor: backend/tests/fixtures/edge_vectors.json, dibangkitkan dari chip golden (identik bit per bit dengan RTL)
oleh hw/scripts/export_edge_vectors.py atas 140 menit trip A1 (pintu terbuka mulai menit 69).
"""

import json
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from app import edge
from app.fleet.window import KOLOM, bangun_jendela
from app.ingest.store import validate_readings

V = json.loads((Path(__file__).parent / "fixtures" / "edge_vectors.json").read_text(encoding="utf-8"))
KUNCI = bytes.fromhex(V["kunci"])
MENIT = V["menit"]


def bahan(i: int):
    raw = MENIT[i]["bacaan"]
    (rd,), err = validate_readings([raw])
    assert not err
    return raw, rd, edge.urai(raw)


def rantai_sebelum(i: int) -> bytes:
    return edge.NOL if i == 0 else bytes.fromhex(MENIT[i - 1]["bacaan"]["edge"]["rantai"])


def jendela_sampai(i: int):
    df = pd.DataFrame([{k: v for k, v in m["bacaan"].items() if k != "edge"} for m in MENIT[:i + 1]])
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df["lat"], df["lon"] = None, None
    return bangun_jendela(df[["ts", *KOLOM]], df.ts.iloc[-1].to_pydatetime() + timedelta(seconds=30))


def test_semua_menit_sah_dan_rantai_bersambung():
    for i in range(len(MENIT)):
        _, rd, e = bahan(i)
        assert edge.periksa(KUNCI, e["rek"], e["rantai"], e["paket"], e["mac"], rantai_sebelum(i), rd) == "OK", i


def test_paket_sesuai_harapan_chip():
    for m in MENIT:
        p = edge.baca_paket(bytes.fromhex(m["bacaan"]["edge"]["paket"]))
        h = m["harapan"]
        assert (p["status"], p["diag_valid"]) == (h["status"], h["diag_valid"])
        if h["diag_valid"]:
            assert p["kelas"] == h["kelas"]


@pytest.mark.parametrize("ubah,harapan", [
    (lambda raw, e: raw.__setitem__("temp_c", raw["temp_c"] + 0.5), "REKAMAN_BEDA"),
    (lambda raw, e: raw.__setitem__("door_open", not raw["door_open"]), "REKAMAN_BEDA"),
    (lambda raw, e: e.__setitem__("paket", bytes([e["paket"][0] ^ 1]) + e["paket"][1:]), "MAC_SALAH"),
    (lambda raw, e: e.__setitem__("rantai", bytes(32)), "MAC_SALAH"),
])
def test_manipulasi_terdeteksi(ubah, harapan):
    raw, _, e = bahan(100)
    raw = dict(raw)
    ubah(raw, e)
    (rd,), _ = validate_readings([{k: v for k, v in raw.items() if k != "edge"}])
    assert edge.periksa(KUNCI, e["rek"], e["rantai"], e["paket"], e["mac"], rantai_sebelum(100), rd) == harapan


def test_rantai_putus_kunci_salah_dan_tanpa_pendahulu():
    _, rd, e = bahan(100)
    assert edge.periksa(KUNCI, e["rek"], e["rantai"], e["paket"], e["mac"], rantai_sebelum(50), rd) == "RANTAI_PUTUS"
    assert edge.periksa(KUNCI, e["rek"], e["rantai"], e["paket"], e["mac"], None, rd) == "OK_RANTAI_BARU"
    assert edge.periksa(bytes(32), e["rek"], e["rantai"], e["paket"], e["mac"], rantai_sebelum(100), rd) == "MAC_SALAH"
    assert edge.periksa(None, e["rek"], e["rantai"], e["paket"], e["mac"], rantai_sebelum(100), rd) == "TANPA_KUNCI"


def test_urai_menolak_format_salah():
    raw = MENIT[0]["bacaan"]
    assert edge.urai({**raw, "edge": {**raw["edge"], "mac": "zz"}}) is None
    assert edge.urai({**raw, "edge": {**raw["edge"], "rek": raw["edge"]["rek"][:-2]}}) is None
    assert edge.urai({k: v for k, v in raw.items() if k != "edge"}) is None
    assert edge.urai({**raw, "edge": {**raw["edge"], "skor": [1, 2]}})["skor"] is None


def test_kunci_perangkat_dari_env():
    assert edge.kunci_perangkat(f"DEV-015={KUNCI.hex()}, DEV-2=" + "00" * 32) == {"DEV-015": KUNCI, "DEV-2": bytes(32)}
    assert edge.kunci_perangkat("") == {}


def test_kondisi_dari_paket_chip():
    for i in (40, 75, 120):
        _, _, e = bahan(i)
        hasil = {"paket": e["paket"], "skor": e["skor"], "verifikasi": "OK", "rantai": e["rantai"]}
        c = edge.kondisi(hasil, V["cargo_profile"], V["mass_kg"], jendela_sampai(i))
        h = MENIT[i]["harapan"]
        assert c["provider"] == edge.PROVIDER and c["forecast"] is None and c["edge"]["verifikasi"] == "OK"
        assert c["status"] == {0: "AMAN", 1: "WASPADA", 2: "KRITIS"}[h["status"]] or c["status"] == "DATA_TIDAK_LENGKAP"
        if not h["diag_valid"]:
            assert c["failure_mode"] is None
        else:
            prob = c["failure_mode"]["probabilities"]
            assert prob is not None and abs(sum(prob.values()) - 1) < 1e-3
            assert max(prob, key=prob.get) == edge.V3_API_LABEL[edge.KELAS_CHIP[h["kelas"]]]


def test_skor_tidak_konsisten_tidak_dipakai():
    _, _, e = bahan(120)
    skor = list(e["skor"])
    skor[0] = max(skor) + 65536                   # argmax pindah ke kelas lain dari yang di-MAC
    p = edge.baca_paket(e["paket"])
    assert edge._peluang(skor, p) is None and edge._peluang(e["skor"], p) is not None


class CursorPalsu:
    def __init__(self):
        self.insert = []

    def execute(self, sql, params=None):
        if sql.startswith("INSERT"):
            self.insert.append(params)
        self._hasil = None
        return self

    def fetchone(self):
        return self._hasil

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class KoneksiPalsu:
    def __init__(self):
        self.cur = CursorPalsu()

    def cursor(self):
        return self.cur

    def commit(self):
        pass


def test_simpan_batch_terbalik_tetap_bersambung():
    raw = [m["bacaan"] for m in MENIT[:70]][::-1]          # urutan kiriman acak: disusun ulang per seq
    ok, err = validate_readings(raw)
    assert not err
    c = KoneksiPalsu()
    hitung = edge.simpan(c, V["truck_id"], V["device_id"], raw, ok, {V["device_id"]: KUNCI})
    assert hitung == {"OK": 70}
    assert [p[3] for p in c.cur.insert] == list(range(70))


def test_simpan_tanpa_kunci_dan_bacaan_ditolak_dilewati():
    raw = [m["bacaan"] for m in MENIT[:3]]
    rusak = {**raw[1], "temp_c": "rusak"}
    ok, _ = validate_readings([raw[0], rusak, raw[2]])
    c = KoneksiPalsu()
    hitung = edge.simpan(c, V["truck_id"], V["device_id"], [raw[0], rusak, raw[2]], ok, {})
    assert hitung == {"TANPA_KUNCI": 2}


@pytest.mark.parametrize("i", [70, 84, 90, 102, 120])
def test_status_chip_sama_dengan_mesin_fisika_cloud(i):
    """Satu kali hitung di chip cukup: status chip = status mesin fisika cloud atas bacaan yang sama."""
    from app.inference import inference_engine

    j = jendela_sampai(i)
    cloud, _ = inference_engine.predict_last(j.readings, V["cargo_profile"], V["mass_kg"])
    _, _, e = bahan(i)
    c = edge.kondisi({"paket": e["paket"], "skor": e["skor"], "verifikasi": "OK", "rantai": e["rantai"]},
                     V["cargo_profile"], V["mass_kg"], j)
    assert c["status"] == cloud["status"]
    assert c["time_to_breach_min"] == (None if cloud["time_to_breach_min"] is None
                                       else pytest.approx(cloud["time_to_breach_min"], abs=1))


def _segel_ulang(i: int, rek: bytes):
    """Rekaman i diganti `rek` dan disegel ulang dengan kunci uji (meniru chip saat bacaan suhu gagal)."""
    import hashlib
    import hmac

    _, _, e = bahan(i)
    rantai = hashlib.sha256(rantai_sebelum(i) + rek).digest()
    return rek, rantai, e["paket"], hmac.new(KUNCI, rantai + e["paket"], hashlib.sha256).digest()


def test_rekaman_tanpa_bacaan_harus_bertanda_sensor_gagal():
    import struct

    _, _, e = bahan(30)
    f = list(struct.unpack(edge.FORMAT_REKAMAN, e["rek"]))
    asli = _segel_ulang(30, e["rek"])                        # sensor valid tapi bacaan tidak dikirim
    assert edge.periksa(KUNCI, *asli, rantai_sebelum(30), None) == "REKAMAN_BEDA"
    f[2], f[7] = 0, f[7] & ~8                                # suhu 0, bit sensor valid dimatikan
    gagal = _segel_ulang(30, struct.pack(edge.FORMAT_REKAMAN, *f))
    assert edge.periksa(KUNCI, *gagal, rantai_sebelum(30), None) == "OK"


def test_simpan_rekaman_tanpa_bacaan_menyambung_rantai():
    import struct

    _, _, e = bahan(1)
    f = list(struct.unpack(edge.FORMAT_REKAMAN, e["rek"]))
    f[2], f[7] = 0, f[7] & ~8
    rek, rantai, paket, mac = _segel_ulang(1, struct.pack(edge.FORMAT_REKAMAN, *f))
    # menit 2 disegel ulang di atas rantai baru supaya tetap bersambung
    import hashlib
    import hmac

    _, _, e2 = bahan(2)
    rantai2 = hashlib.sha256(rantai + e2["rek"]).digest()
    mac2 = hmac.new(KUNCI, rantai2 + e2["paket"], hashlib.sha256).digest()
    raw = [MENIT[0]["bacaan"], {**MENIT[2]["bacaan"], "edge": {**MENIT[2]["bacaan"]["edge"], "rantai": rantai2.hex(),
                                                                "mac": mac2.hex()}}]
    ok, _ = validate_readings(raw)
    c = KoneksiPalsu()
    tanpa = [{"rek": rek.hex(), "rantai": rantai.hex(), "paket": paket.hex(), "mac": mac.hex()}]
    assert edge.simpan(c, V["truck_id"], V["device_id"], raw, ok, {V["device_id"]: KUNCI}, tanpa) == {"OK": 3}
    assert [p[3] for p in c.cur.insert] == [0, 1, 2]
