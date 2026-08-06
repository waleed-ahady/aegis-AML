from __future__ import annotations

import pandas as pd

from aegis_aml.monitoring.drift import categorical_distance, population_stability_index


def test_identical_distributions_have_zero_drift() -> None:
    numeric = pd.Series(range(100))
    categorical = pd.Series(["ACH", "Wire"] * 50)
    assert population_stability_index(numeric, numeric) == 0
    assert categorical_distance(categorical, categorical) == 0


def test_shifted_numeric_distribution_has_positive_psi() -> None:
    reference = pd.Series(range(100))
    current = pd.Series(range(1000, 1100))
    assert population_stability_index(reference, current) > 0.1
