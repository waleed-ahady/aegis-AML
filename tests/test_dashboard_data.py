from __future__ import annotations

import json

from sqlalchemy import create_engine

from aegis_aml.analytics.dashboard_data import (
    alert_summary,
    flatten_alerts,
    load_alerts,
    parse_prometheus_metrics,
    reason_counts,
)


def test_alert_helpers(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'alerts.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE alerts (
                id INTEGER PRIMARY KEY,
                alert_id TEXT,
                transaction_id TEXT,
                created_at TEXT,
                risk_score REAL,
                threshold REAL,
                decision BOOLEAN,
                model_version TEXT,
                reason_codes JSON,
                payload JSON,
                analyst_outcome TEXT,
                analyst_notes TEXT
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO alerts VALUES (
                1, 'ALT-1', 'TX-1', '2026-08-01T12:00:00Z', 0.91, 0.86, 1, 'v1',
                ?, ?, NULL, NULL
            )
            """,
            (
                json.dumps(["NEW_SENDER", "ROUND_AMOUNT_PATTERN"]),
                json.dumps({"from_bank": "B1", "amount_paid": 1000, "payment_format": "Wire"}),
            ),
        )

    alerts, total = load_alerts(engine, 100)
    assert total == 1
    flat = flatten_alerts(alerts)
    assert flat.loc[0, "from_bank"] == "B1"
    assert flat.loc[0, "amount_paid"] == 1000
    assert alert_summary(alerts, total)["review_rate"] == 0
    reasons = reason_counts(alerts)
    assert set(reasons["reason_code"]) == {"NEW_SENDER", "ROUND_AMOUNT_PATTERN"}


def test_empty_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    alerts, total = load_alerts(engine)
    assert alerts.empty
    assert total == 0


def test_parse_prometheus_metrics():
    raw = """
# HELP aegis_score_requests_total Requests
# TYPE aegis_score_requests_total counter
aegis_score_requests_total{decision="alert",status="success"} 12.0
aegis_model_ready 1.0
"""
    metrics = parse_prometheus_metrics(raw)
    assert metrics['aegis_score_requests_total{decision="alert",status="success"}'] == 12.0
    assert metrics["aegis_model_ready"] == 1.0
