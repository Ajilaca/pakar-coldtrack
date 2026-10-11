"""B7 -- tes end-to-end /analyze lewat HTTP ke backend yang BERJALAN (bukan TestClient).

  python -m bench.b7_e2e_api [--url http://localhost:8000]

5 skenario demo backend (data lengkap) + 1 skenario dengan bacaan hilang. Memeriksa kontrak
respons v3: diagnosis_provider, model_version, label dikenal, probabilities 7 kelas, data_lengkap,
status valid, 3 aksi. Hasil: bench/results/g16-cpu/B7/e2e_api.json
"""

import argparse
import json

import httpx

from bench.common import RESULTS_DIR, ROOT, git_info, now_iso, rel, write_json

LABEL_V3 = {
    "normal_sehat",
    "pintu_terbuka_lama",
    "reefer_mati_total",
    "kejutan_ambien_ekstrem",
    "prapendinginan_buruk",
    "degradasi_bertahap",
    "masalah_sensor",
    "pintu_terbuka",
    "suhu_muatan_mendekati_batas",
}


def cek(body, harap_lengkap):
    masalah = []
    if body.get("diagnosis_provider") != "v3":
        masalah.append(f"provider {body.get('diagnosis_provider')}")
    if body["failure_mode"]["label"] not in LABEL_V3:
        masalah.append(f"label tak dikenal {body['failure_mode']['label']}")
    probs = body["failure_mode"].get("probabilities")
    if probs is not None and (
        len(probs) != 7
        or abs(sum(probs.values()) - 1) > 1e-3
        or body["failure_mode"]["label"] != max(probs, key=probs.get)
    ):
        masalah.append("probabilities bukan 7 kelas berjumlah 1 atau tidak cocok dengan label")
    if body.get("data_lengkap") is not harap_lengkap:
        masalah.append(f"data_lengkap {body.get('data_lengkap')} (harap {harap_lengkap})")
    if body["status"] not in {"AMAN", "WASPADA", "KRITIS"} or len(body["actions"]) != 3:
        masalah.append("status/aksi tidak valid")
    if body["failure_mode"]["label"] == "normal_sehat" and body["status"] != "AMAN":
        masalah.append("label normal saat status bukan AMAN")
    return masalah


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    a = ap.parse_args(argv)
    hasil = {"waktu_utc": now_iso(), "git": git_info(), "url": a.url, "kasus": []}
    for p in sorted((ROOT / "backend" / "data" / "scenarios").glob("*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        r = s["readings"]
        while len(r) < 60:
            r = [r[0]] + r
        kasus = [(s["id"], r, True)]
        if s["id"] == "scenario_1_normal":
            kasus.append((s["id"] + "_bacaan_hilang", r[:-20] + r[-14:], False))  # 6 bacaan hilang
        for nama, rd, lengkap in kasus:
            if len(rd) < 60:
                rd = [rd[0]] * (60 - len(rd)) + rd
            res = httpx.post(
                f"{a.url}/api/v1/analyze",
                timeout=30,
                json={"shipment_id": nama, "cargo_profile": s.get("cargo_profile", "vaksin_2_8C"), "readings": rd},
            )
            body = res.json()
            m = [f"HTTP {res.status_code}"] if res.status_code != 200 else cek(body, lengkap)
            hasil["kasus"].append(
                {
                    "kasus": nama,
                    "status_http": res.status_code,
                    "status_harapan": s.get("expected_status"),
                    "status": body.get("status"),
                    "label": body.get("failure_mode", {}).get("label"),
                    "keyakinan": body.get("failure_mode", {}).get("confidence"),
                    "data_lengkap": body.get("data_lengkap"),
                    "model_version": body.get("model_version"),
                    "inference_ms": body.get("inference_ms"),
                    "masalah": m,
                }
            )
            print(
                f"{nama:38s} {res.status_code} {body.get('status'):8s} {body.get('failure_mode', {}).get('label'):28s} "
                f"{body.get('failure_mode', {}).get('confidence')} lengkap={body.get('data_lengkap')} "
                f"{'OK' if not m else 'MASALAH: ' + '; '.join(m)}"
            )
    hasil["semua_ok"] = all(not k["masalah"] for k in hasil["kasus"])
    print(
        "semua OK" if hasil["semua_ok"] else "ADA MASALAH",
        "->",
        rel(write_json(RESULTS_DIR / "g16-cpu" / "B7" / "e2e_api.json", hasil)),
    )


if __name__ == "__main__":
    main()
