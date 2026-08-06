from __future__ import annotations

import numpy as np

from aegis_aml.modeling.threshold import select_threshold


def test_threshold_selection_returns_operating_metrics() -> None:
    y_true = np.array([0, 0, 0, 0, 1, 1])
    probabilities = np.array([0.01, 0.1, 0.2, 0.4, 0.75, 0.95])
    result = select_threshold(
        y_true,
        probabilities,
        false_positive_cost=1,
        false_negative_cost=20,
        max_alert_rate=0.5,
        min_recall=1.0,
    )
    assert 0 <= result.threshold <= 1
    assert result.recall == 1.0
    assert result.alert_rate <= 0.5
