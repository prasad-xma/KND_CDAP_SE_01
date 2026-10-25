"""Load Component 1's fixed developer configuration (configs/component1.yaml)."""

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]  # parkinson-speech-ai/
DEFAULT_CONFIG_PATH = REPO_ROOT / "configs" / "component1.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Read the YAML config and return it as a dict.

    Uses configs/component1.yaml when no path is given.
    """
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        raise ValueError(f"Config {config_path} must be a YAML mapping, got {type(config).__name__}")
    return config


def resolve_path(config: dict[str, Any], key: str) -> Path:
    """Absolute path for config["paths"][key]; relative entries are taken from the repo root."""
    return REPO_ROOT / config["paths"][key]  # an absolute entry overrides REPO_ROOT
