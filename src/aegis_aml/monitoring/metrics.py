from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

SCORE_REQUESTS = Counter(
    "aegis_score_requests_total", "Total transaction scoring requests", ["decision", "status"]
)
SCORE_LATENCY = Histogram(
    "aegis_score_latency_seconds",
    "Scoring latency in seconds",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)
RISK_SCORE = Histogram(
    "aegis_risk_score",
    "Distribution of predicted AML risk scores",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99),
)
MODEL_READY = Gauge("aegis_model_ready", "Whether a model bundle is loaded")
FEEDBACK_TOTAL = Counter("aegis_feedback_total", "Analyst feedback received", ["outcome"])
