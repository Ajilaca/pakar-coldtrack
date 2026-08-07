"""Demo scenario loader and manager module."""

import json
import logging
from pathlib import Path
from typing import Any

from app.schemas import ScenarioMetadata

logger = logging.getLogger("coldtrack.scenarios")

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "data" / "scenarios"


class ScenarioManager:
    """Manages static demo scenarios stored in backend/data/scenarios/."""

    def __init__(self, data_dir: Path = SCENARIOS_DIR):
        self.data_dir = data_dir
        self.scenarios: dict[str, dict[str, Any]] = {}
        self.reload_scenarios()

    def reload_scenarios(self) -> None:
        """Scan directory and load all scenario JSON files."""
        self.scenarios.clear()
        if not self.data_dir.exists():
            logger.warning(f"Scenario directory {self.data_dir} does not exist.")
            return

        for json_file in sorted(self.data_dir.glob("*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    scenario_id = data.get("id") or json_file.stem
                    self.scenarios[scenario_id] = data
            except Exception as e:  # noqa: BLE001
                logger.error(f"Failed to parse scenario file {json_file}: {e}")

    def list_scenarios(self) -> list[ScenarioMetadata]:
        """Return list of scenario metadata objects for GET /api/v1/scenarios."""
        result = []
        for s_id, data in self.scenarios.items():
            readings = data.get("readings", [])
            result.append(
                ScenarioMetadata(
                    id=s_id,
                    title=data.get("title", s_id),
                    description=data.get("description", ""),
                    cargo_profile=data.get("cargo_profile", "vaksin_2_8C"),
                    expected_status=data.get("expected_status", "AMAN"),
                    reading_count=len(readings),
                )
            )
        return result

    def get_scenario(self, scenario_id: str) -> dict[str, Any] | None:
        """Get full payload of a single scenario."""
        return self.scenarios.get(scenario_id)


# Global scenario manager singleton instance
scenario_manager = ScenarioManager()
