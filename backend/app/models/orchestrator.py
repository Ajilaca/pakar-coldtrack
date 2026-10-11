"""Orkestrator model armada: satu provider per jenis, dipilih lewat config.yaml `models.*`.

    from app.models.orchestrator import orchestrator
    hasil = orchestrator.analyze(ctx)   # {"condition": {...}, "sensor_health": {...}}

Provider dimuat malas (model ONNX baru dibuka saat pertama dipakai).
"""

from typing import Any

from app.config import settings
from app.models.base import Konteks, Provider


def _condition_hybrid() -> Provider:
    from app.models.condition import HybridCondition

    return HybridCondition()


def _sensor_rules_v0() -> Provider:
    from app.models.sensor_health_rules import SensorHealthRulesV0

    return SensorHealthRulesV0()


REGISTRY: dict[str, dict[str, Any]] = {
    "condition": {"hybrid": _condition_hybrid},
    "sensor_health": {"rules_v0": _sensor_rules_v0},
}
DEFAULT = {"condition": "hybrid", "sensor_health": "rules_v0"}


class Orchestrator:
    def __init__(self, pilihan: dict[str, str] | None = None) -> None:
        cfg = {**DEFAULT, **(pilihan if pilihan is not None else settings.get("models", {}) or {})}
        for kind, name in cfg.items():
            if kind not in REGISTRY or name not in REGISTRY[kind]:
                raise ValueError(f"models.{kind}: provider tidak dikenal {name!r}; pilihan: "
                                 f"{sorted(REGISTRY.get(kind, {}))}")
        self.pilihan = cfg
        self._providers: dict[str, Provider] = {}

    def provider(self, kind: str) -> Provider:
        if kind not in self._providers:
            self._providers[kind] = REGISTRY[kind][self.pilihan[kind]]()
        return self._providers[kind]

    def analyze(self, ctx: Konteks) -> dict[str, dict[str, Any]]:
        return {kind: self.provider(kind).run(ctx) for kind in self.pilihan}

    def cards(self) -> list[dict[str, Any]]:
        return [self.provider(kind).card() for kind in self.pilihan]


orchestrator = Orchestrator()
