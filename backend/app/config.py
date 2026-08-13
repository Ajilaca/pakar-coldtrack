"""Configuration loader module for ColdTrack AI Backend."""

import os
from pathlib import Path
from typing import Any

import yaml

CONFIG_FILE_PATH = os.getenv(
    "CONFIG_PATH",
    str(Path(__file__).resolve().parent.parent / "config.yaml"),
)


def load_config(config_path: str = CONFIG_FILE_PATH) -> dict[str, Any]:
    """Load and parse YAML configuration file."""
    path = Path(config_path)
    if not path.exists():
        # Fallback search relative to root or module
        alt_path = Path(__file__).resolve().parent.parent / "config.yaml"
        if alt_path.exists():
            path = alt_path
        else:
            raise FileNotFoundError(f"Configuration file not found at {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config or {}


settings = load_config()
