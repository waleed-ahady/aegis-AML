from __future__ import annotations

import copy
import threading
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from aegis_aml.features.transaction import FeatureState
from aegis_aml.modeling.bundle import ModelBundle
from aegis_aml.modeling.reasons import build_reason_codes


class ScoringService:
    """Thread-safe model and online-feature state wrapper."""

    def __init__(self, model_path: str | Path, update_state: bool = True) -> None:
        self.bundle = ModelBundle.load(model_path)
        self.state: FeatureState = copy.deepcopy(self.bundle.feature_state)
        self.update_state = update_state
        self._lock = threading.Lock()

    def score(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            features = self.state.make_features(payload)
            probability = float(self.bundle.pipeline.predict_proba(pd.DataFrame([features]))[0, 1])
            decision = probability >= self.bundle.threshold
            if self.update_state:
                self.state.update(
                    from_account=str(payload["from_account"]),
                    to_account=str(payload["to_account"]),
                    amount=float(payload["amount_paid"]),
                    timestamp=pd.Timestamp(payload["timestamp"]),
                )
        reason_codes = build_reason_codes(features, probability)
        return {
            "transaction_id": str(payload["transaction_id"]),
            "alert_id": f"ALT-{uuid.uuid4().hex[:16]}" if decision else None,
            "risk_score": probability,
            "threshold": float(self.bundle.threshold),
            "decision": "alert" if decision else "allow",
            "reason_codes": reason_codes,
            "model_version": self.bundle.model_version,
            "features": features,
        }
