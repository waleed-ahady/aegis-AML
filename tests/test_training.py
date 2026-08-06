from __future__ import annotations

import json

from aegis_aml.api.service import ScoringService
from aegis_aml.modeling.bundle import ModelBundle


def test_model_bundle_round_trip_and_score(trained_artifacts: tuple) -> None:
    model_path, report_path = trained_artifacts
    bundle = ModelBundle.load(model_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert 0 <= bundle.threshold <= 1
    assert report["model_version"] == bundle.model_version
    assert report["metrics"]["test"]["average_precision"] >= 0

    service = ScoringService(model_path)
    result = service.score(
        {
            "transaction_id": "test-1",
            "timestamp": "2026-01-01T02:00:00Z",
            "from_bank": "B001",
            "from_account": "NEW-SENDER",
            "to_bank": "B002",
            "to_account": "NEW-RECEIVER",
            "amount_received": 9900.0,
            "receiving_currency": "USD",
            "amount_paid": 9900.0,
            "payment_currency": "USD",
            "payment_format": "Wire",
        }
    )
    assert 0 <= result["risk_score"] <= 1
    assert result["decision"] in {"allow", "alert"}
    assert result["model_version"] == bundle.model_version
