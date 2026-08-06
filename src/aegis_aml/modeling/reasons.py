from __future__ import annotations

from typing import Any


def build_reason_codes(features: dict[str, Any], risk_score: float) -> list[str]:
    """Create stable analyst reason codes; these are not SHAP explanations."""
    reasons: list[str] = []
    if features["sender_amount_to_avg"] >= 5:
        reasons.append("AMOUNT_ABOVE_SENDER_BASELINE")
    if features["receiver_amount_to_avg"] >= 5:
        reasons.append("AMOUNT_ABOVE_RECEIVER_BASELINE")
    if features["sender_minutes_since_last"] <= 10:
        reasons.append("RAPID_REPEAT_SENDER_ACTIVITY")
    if features["cross_currency"]:
        reasons.append("CROSS_CURRENCY_TRANSFER")
    if features["is_round_amount"]:
        reasons.append("ROUND_AMOUNT_PATTERN")
    if features["sender_prev_tx_count"] == 0:
        reasons.append("NEW_SENDER")
    if features["payment_format"] in {"Cash", "Wire"}:
        reasons.append("HIGHER_RISK_PAYMENT_FORMAT")
    if not reasons and risk_score >= 0.5:
        reasons.append("MULTIVARIATE_MODEL_PATTERN")
    return reasons[:5]
