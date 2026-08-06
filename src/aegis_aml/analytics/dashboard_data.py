from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import Engine, inspect, text


ALERT_COLUMNS = [
    "id",
    "alert_id",
    "transaction_id",
    "created_at",
    "risk_score",
    "threshold",
    "decision",
    "model_version",
    "reason_codes",
    "payload",
    "analyst_outcome",
    "analyst_notes",
]


def _decode_json(value: Any, fallback: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def load_alerts(engine: Engine, limit: int = 5000) -> tuple[pd.DataFrame, int]:
    """Load recent alerts and the exact lifetime count from the configured database."""
    if "alerts" not in inspect(engine).get_table_names():
        return pd.DataFrame(columns=ALERT_COLUMNS), 0

    safe_limit = min(max(int(limit), 1), 50_000)
    with engine.connect() as connection:
        total = int(connection.execute(text("SELECT COUNT(*) FROM alerts")).scalar_one())
        frame = pd.read_sql_query(
            text("SELECT * FROM alerts ORDER BY created_at DESC LIMIT :limit"),
            connection,
            params={"limit": safe_limit},
        )

    if frame.empty:
        return pd.DataFrame(columns=ALERT_COLUMNS), total

    frame["created_at"] = pd.to_datetime(frame["created_at"], errors="coerce", utc=True)
    frame["risk_score"] = pd.to_numeric(frame["risk_score"], errors="coerce")
    frame["threshold"] = pd.to_numeric(frame["threshold"], errors="coerce")
    frame["reason_codes"] = frame["reason_codes"].map(lambda value: _decode_json(value, []))
    frame["payload"] = frame["payload"].map(lambda value: _decode_json(value, {}))
    frame["reviewed"] = frame["analyst_outcome"].notna()
    return frame, total


def flatten_alerts(alerts: pd.DataFrame) -> pd.DataFrame:
    """Expose commonly investigated transaction fields from the JSON payload."""
    if alerts.empty:
        return alerts.copy()

    result = alerts.copy()
    payload_fields = [
        "timestamp",
        "from_bank",
        "from_account",
        "to_bank",
        "to_account",
        "amount_paid",
        "payment_currency",
        "amount_received",
        "receiving_currency",
        "payment_format",
    ]
    for field in payload_fields:
        result[field] = result["payload"].map(
            lambda payload: payload.get(field) if isinstance(payload, dict) else None
        )
    result["amount_paid"] = pd.to_numeric(result["amount_paid"], errors="coerce")
    result["amount_received"] = pd.to_numeric(result["amount_received"], errors="coerce")
    result["reason_text"] = result["reason_codes"].map(
        lambda reasons: ", ".join(reasons) if isinstance(reasons, list) else str(reasons)
    )
    return result


def alert_summary(alerts: pd.DataFrame, total_count: int) -> dict[str, float | int | str]:
    """Compute headline alert operations metrics."""
    if alerts.empty:
        return {
            "total_alerts": total_count,
            "loaded_alerts": 0,
            "reviewed": 0,
            "review_rate": 0.0,
            "average_risk": 0.0,
            "median_risk": 0.0,
            "latest_alert": "—",
        }
    reviewed = int(alerts["reviewed"].sum())
    return {
        "total_alerts": total_count,
        "loaded_alerts": len(alerts),
        "reviewed": reviewed,
        "review_rate": reviewed / len(alerts),
        "average_risk": float(alerts["risk_score"].mean()),
        "median_risk": float(alerts["risk_score"].median()),
        "latest_alert": alerts["created_at"].max().isoformat(),
    }


def reason_counts(alerts: pd.DataFrame) -> pd.DataFrame:
    """Count each reason code across loaded alerts."""
    if alerts.empty:
        return pd.DataFrame(columns=["reason_code", "count"])
    exploded = alerts[["reason_codes"]].explode("reason_codes").dropna()
    if exploded.empty:
        return pd.DataFrame(columns=["reason_code", "count"])
    return (
        exploded["reason_codes"]
        .value_counts()
        .rename_axis("reason_code")
        .reset_index(name="count")
    )


def load_json_report(path: str | Path) -> dict[str, Any] | None:
    report_path = Path(path)
    if not report_path.exists():
        return None
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_csv_report(path: str | Path, limit: int = 10_000) -> pd.DataFrame:
    report_path = Path(path)
    if not report_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(report_path, nrows=limit)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError):
        return pd.DataFrame()


def parse_prometheus_metrics(raw: str) -> dict[str, float]:
    """Extract selected scalar metrics from Prometheus exposition text."""
    metrics: dict[str, float] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or " " not in line:
            continue
        key, value = line.rsplit(" ", 1)
        try:
            number = float(value)
        except ValueError:
            continue
        metrics[key] = number
    return metrics
