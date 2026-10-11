"""Estimasi kerugian per insiden (CONTEXT_FLEET_SCALEUP.md Fase 3). Nilai muatan = massa x harga per kg [ASUMSI]
(config.yaml fleet.harga_per_kg_idr, docs/fleet_assumptions.md); angka ini ESTIMASI, bukan kerugian tercatat.

  nilai berisiko      = nilai muatan x risk_index saat ini        (insiden terbuka tanpa breach)
  kerugian terjadi    = nilai muatan penuh bila breach            (asumsi muatan hilang seluruhnya [ASUMSI])
  berhasil diatasi    = nilai muatan bila tanpa breach DAN (SELESAI atau kembali AMAN)
  lead time (menit)   = breach_at - detected_at
"""

import statistics
from typing import Any


def per_insiden(ins: dict[str, Any], risk_index: float | None = None) -> dict[str, Any]:
    """Insiden jenis 'data' (putus data) tidak punya nilai kerugian; ringkas() sebaiknya hanya diberi 'kondisi'."""
    nilai = ins.get("cargo_value_idr") if ins.get("jenis", "kondisi") == "kondisi" else None
    breach = ins.get("breach_at") is not None
    terbuka = ins.get("phase") in ("TERDETEKSI", "DITUGASKAN", "DITANGANI")
    diatasi = not breach and (ins.get("phase") == "SELESAI" or ins.get("recovered_at") is not None)
    lead = None
    if breach and ins.get("detected_at") is not None:
        lead = round((ins["breach_at"] - ins["detected_at"]).total_seconds() / 60.0, 1)
    return {
        "nilai_muatan_idr": nilai,
        "nilai_berisiko_idr": int(nilai * risk_index) if nilai and terbuka and not breach and risk_index else 0,
        "kerugian_terjadi_idr": int(nilai) if nilai and breach else 0,
        "berhasil_diatasi_idr": int(nilai) if nilai and diatasi else 0,
        "lead_time_min": lead,
        "hasil": "breach" if breach else "diatasi" if diatasi else "terbuka" if terbuka else "ditutup",
    }


def ringkas(baris: list[dict[str, Any]]) -> dict[str, Any]:
    leads = [b["lead_time_min"] for b in baris if b["lead_time_min"] is not None]
    return {
        "nilai_berisiko_idr": sum(b["nilai_berisiko_idr"] for b in baris),
        "kerugian_terjadi_idr": sum(b["kerugian_terjadi_idr"] for b in baris),
        "berhasil_diatasi_idr": sum(b["berhasil_diatasi_idr"] for b in baris),
        "n_insiden": len(baris),
        "n_breach": sum(b["hasil"] == "breach" for b in baris),
        "n_diatasi": sum(b["hasil"] == "diatasi" for b in baris),
        "lead_time_median_min": statistics.median(leads) if leads else None,
        "catatan": "Estimasi dari harga per kg [ASUMSI]; bukan kerugian tercatat.",
    }
