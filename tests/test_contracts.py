from __future__ import annotations

import pandas as pd

from aegis_aml.data.contracts import CANONICAL_COLUMNS, clean
from aegis_aml.data.generate import generate_demo_transactions


def test_ibm_schema_is_normalized() -> None:
    raw = generate_demo_transactions(rows=300, seed=1)
    cleaned, report = clean(raw)
    assert list(cleaned.columns) == CANONICAL_COLUMNS
    assert report.rows == 300
    assert cleaned["timestamp"].is_monotonic_increasing
    assert cleaned["is_laundering"].isin([0, 1]).all()


def test_invalid_required_rows_are_removed() -> None:
    raw = generate_demo_transactions(rows=150, seed=2)
    raw.loc[0, "Timestamp"] = "not-a-date"
    raw.loc[1, "Amount Paid"] = -10
    raw = pd.concat([raw, raw.iloc[[2]]], ignore_index=True)
    cleaned, report = clean(raw)
    assert report.invalid_timestamps == 1
    assert report.negative_amounts == 1
    assert report.duplicate_rows >= 1
    assert len(cleaned) == 148
