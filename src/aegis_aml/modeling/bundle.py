from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib

from aegis_aml.features.transaction import FeatureState


@dataclass
class ModelBundle:
    pipeline: Any
    threshold: float
    model_version: str
    trained_at: str
    metrics: dict[str, Any]
    feature_state: FeatureState
    feature_names: list[str]
    dataset_summary: dict[str, Any]

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, destination)
        return destination

    @classmethod
    def load(cls, path: str | Path) -> "ModelBundle":
        bundle = joblib.load(Path(path))
        if not isinstance(bundle, cls):
            raise TypeError(f"Expected ModelBundle, received {type(bundle)!r}")
        return bundle
