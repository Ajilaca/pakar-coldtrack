"""Provider kondisi: mesin fisika (status, TTB) + model diagnosis (app/inference.py, model.diagnosis_provider).

Keluaran untuk satu truk pada menit terakhir. Status armada:
  TIDAK_ADA_DATA / MENUNGGU_DATA   dari app/fleet/window.py; model tidak dijalankan.
  AMAN / WASPADA / KRITIS          dari mesin fisika (sama persis dengan POST /analyze).
  DATA_TIDAK_LENGKAP               [DESAIN] menggantikan AMAN saja bila 60 menit terakhir berlubang:
                                   data tidak lengkap tidak boleh tampil AMAN, tetapi WASPADA/KRITIS
                                   tidak boleh disembunyikan oleh catatan kualitas data.
"""

from typing import Any, ClassVar

from app.inference import inference_engine
from app.models.base import Konteks, Provider


class HybridCondition(Provider):
    name: ClassVar[str] = "hybrid"
    kind: ClassVar[str] = "condition"

    def __init__(self, engine=None) -> None:
        self.engine = engine or inference_engine
        self.version = self.engine.version

    def run(self, ctx: Konteks) -> dict[str, Any]:
        j = ctx.jendela
        base = {"status": j.keadaan, "data_lengkap": j.keadaan == "OK" and j.data_lengkap,
                "catatan_data": j.catatan(), "model_version": self.engine.version,
                "provider": self.engine.provider_name, "forecast": None, "failure_mode": None,
                "risk_index": None, "time_to_breach_min": None, "ttb_model_min": None, "reason": None,
                "t_cargo_est": None, "t_hi": None, "series": None}
        if j.keadaan != "OK" or not ctx.cargo_profile:
            return base
        result, series = self.engine.predict_last(j.readings, ctx.cargo_profile, ctx.mass_kg)
        if result["forecast"] is None:                     # model gagal dimuat: hanya mesin fisika
            base["model_version"], base["provider"] = "coldtrack-engine-only", "engine-only"
        out = {**base, **result, "series": series, "catatan_data": j.catatan() or result.get("catatan_data")}
        out["model_version"], out["provider"] = base["model_version"], base["provider"]
        out["data_lengkap"] = j.data_lengkap and result["data_lengkap"]
        if not out["data_lengkap"] and result["status"] == "AMAN":
            out["status"] = "DATA_TIDAK_LENGKAP"
        return out

    def card(self) -> dict[str, Any]:
        return {**super().card(), "version": self.engine.version, "diagnosis_provider": self.engine.provider_name,
                "sumber_status": "mesin fisika (app/core/engine.py)", "model_card": "docs/model_card.md"}
