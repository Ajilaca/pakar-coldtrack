"""Kontrak provider model armada (CONTEXT_FLEET_SCALEUP.md Fase 3).

Satu provider per jenis (`kind`): condition, sensor_health, ... Dipilih lewat config.yaml `models.*`
(app/models/orchestrator.py). `card()` dipakai GET /api/v1/models (Fase 4) dan harus jujur soal sumber
dan keterbatasan.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

import pandas as pd

from app.fleet.window import Jendela


@dataclass
class Konteks:
    truck_id: str
    now: datetime
    jendela: Jendela
    cargo_profile: str | None = None
    mass_kg: float | None = None
    device: dict[str, Any] | None = None
    raw: pd.DataFrame = field(default_factory=pd.DataFrame)   # bacaan asli 3 jam terakhir (sensor health)


class Provider:
    name: ClassVar[str] = "base"
    version: ClassVar[str] = "0"
    kind: ClassVar[str] = "base"

    def run(self, ctx: Konteks) -> dict[str, Any]:
        raise NotImplementedError

    def card(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version, "kind": self.kind}
