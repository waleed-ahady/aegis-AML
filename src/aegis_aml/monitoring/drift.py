from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from aegis_aml.data.ingest import read_transactions
from aegis_aml.features.transaction import build_causal_features


def population_stability_index(reference: pd.Series, current: pd.Series, bins: int = 10) -> float:
    """Calculate PSI with quantile bins derived only from the reference sample."""
    reference_values = pd.to_numeric(reference, errors="coerce").dropna().to_numpy()
    current_values = pd.to_numeric(current, errors="coerce").dropna().to_numpy()
    if len(reference_values) == 0 or len(current_values) == 0:
        return 0.0
    edges = np.unique(np.quantile(reference_values, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0] = -np.inf
    edges[-1] = np.inf
    reference_hist, _ = np.histogram(reference_values, bins=edges)
    current_hist, _ = np.histogram(current_values, bins=edges)
    reference_pct = np.clip(reference_hist / reference_hist.sum(), 1e-6, None)
    current_pct = np.clip(current_hist / current_hist.sum(), 1e-6, None)
    return float(np.sum((current_pct - reference_pct) * np.log(current_pct / reference_pct)))


def categorical_distance(reference: pd.Series, current: pd.Series) -> float:
    reference_dist = reference.astype(str).value_counts(normalize=True)
    current_dist = current.astype(str).value_counts(normalize=True)
    categories = reference_dist.index.union(current_dist.index)
    return float(0.5 * np.abs(reference_dist.reindex(categories, fill_value=0) - current_dist.reindex(categories, fill_value=0)).sum())


def drift_report(
    reference_path: str | Path,
    current_path: str | Path,
    output_path: str | Path | None = None,
    warning_threshold: float = 0.10,
    critical_threshold: float = 0.25,
) -> dict[str, Any]:
    reference = build_causal_features(read_transactions(reference_path))
    current = build_causal_features(read_transactions(current_path))
    numeric_columns = [
        "amount_paid",
        "amount_log1p",
        "sender_amount_to_avg",
        "sender_minutes_since_last",
        "pair_prev_count",
    ]
    categorical_columns = ["payment_format", "payment_currency", "receiving_currency"]
    numeric = {column: population_stability_index(reference[column], current[column]) for column in numeric_columns}
    categorical = {column: categorical_distance(reference[column], current[column]) for column in categorical_columns}
    maximum = max([*numeric.values(), *categorical.values()], default=0.0)
    status = "critical" if maximum >= critical_threshold else "warning" if maximum >= warning_threshold else "healthy"
    report: dict[str, Any] = {
        "status": status,
        "max_drift": maximum,
        "numeric_psi": numeric,
        "categorical_total_variation": categorical,
        "reference_rows": len(reference),
        "current_rows": len(current),
    }
    if output_path:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
