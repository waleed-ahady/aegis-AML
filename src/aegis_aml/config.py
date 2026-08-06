from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("configs/development.yaml")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load YAML configuration, resolving a single `extends` reference."""
    selected = Path(path or os.getenv("AEGIS_CONFIG", DEFAULT_CONFIG_PATH))
    with selected.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    parent_name = config.pop("extends", None)
    if parent_name:
        parent_path = selected.parent / parent_name
        with parent_path.open("r", encoding="utf-8") as handle:
            parent = yaml.safe_load(handle) or {}
        config = _deep_merge(parent, config)

    return config


def env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)
