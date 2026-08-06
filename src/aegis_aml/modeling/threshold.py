from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import precision_score, recall_score


@dataclass(frozen=True)
class ThresholdResult:
    threshold: float
    expected_cost: float
    precision: float
    recall: float
    alert_rate: float


def select_threshold(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    false_positive_cost: float = 1.0,
    false_negative_cost: float = 25.0,
    max_alert_rate: float = 0.05,
    min_recall: float = 0.5,
) -> ThresholdResult:
    """Choose a validation threshold by minimizing operational cost under constraints."""
    candidates = np.unique(np.quantile(probabilities, np.linspace(0.0, 1.0, 401)))
    best: ThresholdResult | None = None
    fallback: ThresholdResult | None = None

    for threshold in candidates:
        predictions = (probabilities >= threshold).astype(int)
        fp = int(((predictions == 1) & (y_true == 0)).sum())
        fn = int(((predictions == 0) & (y_true == 1)).sum())
        cost = fp * false_positive_cost + fn * false_negative_cost
        precision = float(precision_score(y_true, predictions, zero_division=0))
        recall = float(recall_score(y_true, predictions, zero_division=0))
        alert_rate = float(predictions.mean())
        result = ThresholdResult(float(threshold), float(cost), precision, recall, alert_rate)

        if fallback is None or result.expected_cost < fallback.expected_cost:
            fallback = result
        if alert_rate <= max_alert_rate and recall >= min_recall:
            if best is None or result.expected_cost < best.expected_cost:
                best = result

    if best is not None:
        return best
    if fallback is None:
        return ThresholdResult(0.5, 0.0, 0.0, 0.0, 0.0)
    return fallback
