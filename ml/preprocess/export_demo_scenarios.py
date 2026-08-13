"""Ekspor 5 skenario demo dari dataset v4 ke format yang diminta backend.

Latar belakang. Berkas skenario lama hanya berisi 3-5 bacaan, sedangkan backend kini
menolak permintaan di bawah 60 bacaan -- model menghitung statistik ringkasan
(simpangan baku, tren) di dalam dirinya, sehingga jendela hasil padding menghasilkan
nilai yang salah dan model tidak pernah dilatih pada bentuk seperti itu.

Skrip ini memilih perjalanan sungguhan dari dataset v4, memotong jendela berisi
minimal 60 menit berturut-turut, lalu menuliskannya sesuai skema `TelemetryReading`
di `backend/app/schemas.py`.

Menjalankan: python -m ml.preprocess.export_demo_scenarios
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import onnxruntime as ort
import pandas as pd

from ml.preprocess.build_windows import (FAILURE_CLASSES, MODE_MAPPING,
                                         WINDOW_SIZE,
                                         hitung_ulang_reefer_duration)
from ml.tests.test_data_contract import FEATURE_COLUMNS

ONNX_PATH = "ml/reports/coldtrack.onnx"

DATA_PATH = "data/processed/v4_seed1000_700trips.parquet"
OUT_DIR = Path("backend/data/scenarios")

PANJANG_JENDELA = 150     # menit; jauh di atas syarat minimal 60
TTB_SASARAN = 20          # menit; lihat alasannya di pilih_jendela()
MIN_BACAAN = 60           # syarat minimum backend (backend/app/main.py)
WIB = timezone(timedelta(hours=7))
WAKTU_BERANGKAT = datetime(2026, 8, 20, 7, 0, 0, tzinfo=WIB)

# Rute Jakarta -> Bandung sebagai koordinat sintetik. Model tidak memakai lat/lon
# sebagai fitur, tetapi skema backend mewajibkannya.
JAKARTA = (-6.2118, 106.8456)
BANDUNG = (-6.9175, 107.6191)

# Nama profil mengikuti backend/config.yaml (versi R3 setelah disinkronkan dengan R1)
CARGO_KE_PROFIL_BACKEND = {
    "vaksin_2_8C": "vaksin_2_8C",
    "daging_beku": "daging_beku_-18C",
    "sayur_buah": "buah_segar_2_4C",
    "ikan_segar": "ikan_segar_0_5C",
    "produk_susu": "produk_susu_2_4C",
}

SKENARIO = [
    {
        "berkas": "scenario_1_normal.json",
        "id": "scenario_1_normal",
        "mode": "A0",
        "title": "Skenario 1: Perjalanan Normal (Kondisi Aman)",
        "description": "Reefer aktif konsisten sepanjang perjalanan, suhu terkendali di dalam pita aman.",
        "expected_status": "AMAN",
        "shipment_id": "TRK-JKT-0417",
    },
    {
        "berkas": "scenario_2_door_open.json",
        "id": "scenario_2_door_open",
        "mode": "A1",
        "title": "Skenario 2: Pintu Kargo Terbuka Terlalu Lama",
        "description": "Pintu kargo terbuka saat bongkar muat, memicu lonjakan suhu tajam dan pemulihan lambat.",
        "expected_status": "KRITIS",
        "shipment_id": "TRK-JKT-0418",
    },
    {
        "berkas": "scenario_3_compressor_degradation.json",
        "id": "scenario_3_compressor_degradation",
        "mode": "A2",
        "title": "Skenario 3: Kompresor Melemah Bertahap",
        "description": "Kapasitas pendinginan meluruh perlahan. Kenaikan suhu terlalu halus untuk disadari manusia, tetapi terdeteksi model beserta estimasi waktunya.",
        "expected_status": "KRITIS",
        "shipment_id": "TRK-JKT-0419",
    },
    {
        "berkas": "scenario_4_reefer_failure.json",
        "id": "scenario_4_sensor_stuck",
        "mode": "A5",
        "title": "Skenario 4: Sensor Macet (Stuck-at)",
        "description": "Sensor membeku pada satu nilai sementara suhu kargo sesungguhnya terus berubah. Mode paling berbahaya karena tampak normal di layar.",
        "expected_status": "WASPADA",
        "shipment_id": "TRK-JKT-0420",
    },
    {
        "berkas": "scenario_5_extreme_ambient.json",
        "id": "scenario_5_extreme_ambient",
        "mode": "A7",
        "title": "Skenario 5: Kejut Suhu Ambien saat Macet",
        "description": "Kendaraan berhenti lama di bawah radiasi matahari tinggi, beban termal melonjak.",
        "expected_status": "WASPADA",
        "shipment_id": "TRK-JKT-0421",
    },
]


def potong_jendela(g, menit_akhir):
    """Ambil PANJANG_JENDELA menit yang berakhir di posisi menit_akhir."""
    g = g.sort_values("minute").reset_index(drop=True)
    awal = max(0, menit_akhir - PANJANG_JENDELA + 1)
    jendela = g.iloc[awal:menit_akhir + 1]

    # Bacaan kosong akibat packet loss diisi maju-mundur; backend menolak nilai null,
    # dan jendela berlubang tidak dapat dipakai model.
    return jendela.ffill().bfill()


def ke_readings(jendela):
    n = len(jendela)
    lat = np.linspace(JAKARTA[0], BANDUNG[0], n)
    lon = np.linspace(JAKARTA[1], BANDUNG[1], n)

    readings = []
    for i, (_, r) in enumerate(jendela.iterrows()):
        readings.append({
            "ts": (WAKTU_BERANGKAT + timedelta(minutes=i)).isoformat(),
            "temp_c": round(float(r["temp_c"]), 2),
            "humidity": round(float(r["humidity"]), 1),
            "ambient_c": round(float(r["ambient_c"]), 2),
            "door_open": bool(r["door_open"]),
            "reefer_on": bool(r["reefer_on"]),
            "lat": round(float(lat[i]), 6),
            "lon": round(float(lon[i]), 6),
            "speed_kmh": round(float(r["speed_kmh"]), 1),
            "harsh_events": int(r["harsh_events"]),
            "solar_radiation": round(float(r["solar_radiation"]), 1),
        })
    return readings


def cari_jendela_terverifikasi(df, sesi, mode, batas_trip=60):
    """Cari (trip_id, menit_akhir) yang benar-benar dikenali model dengan benar.

    Memilih berdasarkan nilai time_to_breach saja tidak cukup: klasifikasi mode
    kegagalan masih lemah untuk sebagian kelas (lihat model_card.md), sehingga
    jendela yang "secara data benar" belum tentu ditebak benar oleh model.
    Demo harus memakai kasus yang terbukti bekerja -- metrik keseluruhan tetap
    dilaporkan apa adanya di model card.
    """
    target = MODE_MAPPING[mode]
    idx_target = FAILURE_CLASSES.index(target)
    label_akhir = df.groupby("trip_id").last()["failure_mode"]

    terbaik = None      # (trip_id, menit_akhir, ttb, keyakinan)
    for trip_id in label_akhir[label_akhir == mode].index[:batas_trip]:
        g = df[df["trip_id"] == trip_id].sort_values("minute").reset_index(drop=True)
        if len(g) < MIN_BACAAN + 20:
            continue

        feats = g[FEATURE_COLUMNS].values.astype(np.float32)
        ttb = g["time_to_breach"].values

        posisi = [
            e for e in range(MIN_BACAAN - 1, len(g))
            if not np.isnan(feats[e - WINDOW_SIZE + 1:e + 1]).any()
        ]
        if not posisi:
            continue

        batch = np.stack([
            hitung_ulang_reefer_duration(feats[e - WINDOW_SIZE + 1:e + 1]) for e in posisi
        ])
        prob = sesi.run(None, {"window": batch})[1]

        for k, e in enumerate(posisi):
            if int(prob[k].argmax()) != idx_target:
                continue
            nilai_ttb = float(ttb[e])
            if mode == "A0":
                if nilai_ttb != 999:
                    continue
                skor = -float(prob[k][idx_target])          # pilih yang paling yakin
            else:
                if not (0 < nilai_ttb <= 30):
                    continue
                skor = abs(nilai_ttb - TTB_SASARAN)         # pilih yang mendekati sasaran
            if terbaik is None or skor < terbaik[0]:
                terbaik = (skor, int(trip_id), int(e), nilai_ttb, float(prob[k][idx_target]))

    return None if terbaik is None else terbaik[1:]


def main():
    df = pd.read_parquet(DATA_PATH)
    sesi = ort.InferenceSession(ONNX_PATH)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for spek in SKENARIO:
        hasil = cari_jendela_terverifikasi(df, sesi, spek["mode"])
        if hasil is None:
            print(f"  LEWAT  {spek['berkas']}: tidak ada jendela {spek['mode']} "
                  f"yang dikenali model dengan benar")
            continue
        trip_id, menit_akhir, ttb_akhir, keyakinan = hasil

        g = df[df["trip_id"] == trip_id]
        jendela = potong_jendela(g, menit_akhir)
        readings = ke_readings(jendela)

        cargo = jendela["cargo_type"].iloc[0]

        isi = {
            "id": spek["id"],
            "title": spek["title"],
            "description": spek["description"],
            "cargo_profile": CARGO_KE_PROFIL_BACKEND[cargo],
            "expected_status": spek["expected_status"],
            "shipment_id": spek["shipment_id"],
            "sumber": {
                "dataset": Path(DATA_PATH).name,
                "trip_id": int(trip_id),
                "menit_akhir": int(menit_akhir),
                "failure_mode": spek["mode"],
                "kelas_model": MODE_MAPPING[spek["mode"]],
                "keyakinan_model": round(keyakinan, 3),
                "time_to_breach_menit_terakhir": None if ttb_akhir == 999 else ttb_akhir,
                "catatan": "Jendela dipilih setelah diverifikasi dikenali benar oleh coldtrack.onnx.",
            },
            "readings": readings,
        }

        path = OUT_DIR / spek["berkas"]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(isi, f, indent=2, ensure_ascii=False)

        ttb_txt = "tidak breach" if ttb_akhir == 999 else f"TTB {ttb_akhir:.0f} mnt"
        print(f"  {spek['berkas']:42s} {len(readings):3d} bacaan | trip {trip_id:3d} "
              f"| {cargo:12s} | {ttb_txt:14s} | yakin {keyakinan*100:.0f}%")

    print(f"\nTersimpan di {OUT_DIR}/")


if __name__ == "__main__":
    main()
