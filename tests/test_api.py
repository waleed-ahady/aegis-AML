from __future__ import annotations

from fastapi.testclient import TestClient


def test_api_health_and_scoring(monkeypatch, tmp_path, trained_artifacts: tuple) -> None:
    model_path, _ = trained_artifacts
    monkeypatch.setenv("AEGIS_MODEL_PATH", str(model_path))
    monkeypatch.setenv("AEGIS_DATABASE_URL", f"sqlite:///{tmp_path / 'alerts.db'}")
    monkeypatch.setenv("AEGIS_CONFIG", "configs/development.yaml")

    from aegis_aml.api.main import app

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["model_ready"] is True

        response = client.post(
            "/v1/score",
            json={
                "transaction_id": "api-test-1",
                "timestamp": "2026-01-01T02:00:00Z",
                "from_bank": "B001",
                "from_account": "API-SENDER",
                "to_bank": "B002",
                "to_account": "API-RECEIVER",
                "amount_received": 19000.0,
                "receiving_currency": "usd",
                "amount_paid": 19000.0,
                "payment_currency": "usd",
                "payment_format": "Wire",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["transaction_id"] == "api-test-1"
        assert body["decision"] in {"allow", "alert"}
        assert 0 <= body["risk_score"] <= 1
