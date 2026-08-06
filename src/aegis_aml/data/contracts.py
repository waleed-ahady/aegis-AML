from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import pandas as pd


CANONICAL_COLUMNS: Final[list[str]] = [
    "timestamp",
    "from_bank",
    "from_account",
    "to_bank",
    "to_account",
    "amount_received",
    "receiving_currency",
    "amount_paid",
    "payment_currency",
    "payment_format",
    "is_laundering",
]

ALIASES: Final[dict[str, str]] = {
    "Timestamp": "timestamp",
    "From Bank": "from_bank",
    "Account": "from_account",
    "To Bank": "to_bank",
    "Account.1": "to_account",
    "Amount Received": "amount_received",
    "Receiving Currency": "receiving_currency",
    "Amount Paid": "amount_paid",
    "Payment Currency": "payment_currency",
    "Payment Format": "payment_format",
    "Is Laundering": "is_laundering",
    "is_laundering": "is_laundering",
    "from_account": "from_account",
    "to_account": "to_account",
}


@dataclass(frozen=True)
class DataQualityReport:
    rows: int
    duplicate_rows: int
    invalid_timestamps: int
    negative_amounts: int
    missing_accounts: int
    label_rate: float


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize the IBM AML CSV schema and common variants to internal names."""
    renamed = frame.rename(columns={column: ALIASES.get(column, column) for column in frame.columns})
    missing = [column for column in CANONICAL_COLUMNS if column not in renamed.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return renamed[CANONICAL_COLUMNS].copy()


def coerce_types(frame: pd.DataFrame) -> pd.DataFrame:
    result = normalize_columns(frame)
    result["timestamp"] = pd.to_datetime(result["timestamp"], errors="coerce", utc=True)
    for column in ("amount_received", "amount_paid"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    for column in ("from_bank", "to_bank", "from_account", "to_account"):
        result[column] = result[column].astype("string")
    for column in ("receiving_currency", "payment_currency", "payment_format"):
        result[column] = result[column].fillna("UNKNOWN").astype("string")
    result["is_laundering"] = pd.to_numeric(result["is_laundering"], errors="coerce").fillna(0).astype("int8")
    return result


def validate(frame: pd.DataFrame) -> DataQualityReport:
    invalid_timestamps = int(frame["timestamp"].isna().sum())
    negative_amounts = int(
        ((frame["amount_paid"] < 0) | (frame["amount_received"] < 0)).fillna(False).sum()
    )
    missing_accounts = int(
        (frame["from_account"].isna() | frame["to_account"].isna()).sum()
    )
    return DataQualityReport(
        rows=len(frame),
        duplicate_rows=int(frame.duplicated().sum()),
        invalid_timestamps=invalid_timestamps,
        negative_amounts=negative_amounts,
        missing_accounts=missing_accounts,
        label_rate=float(frame["is_laundering"].mean()) if len(frame) else 0.0,
    )


def clean(frame: pd.DataFrame) -> tuple[pd.DataFrame, DataQualityReport]:
    typed = coerce_types(frame)
    report = validate(typed)
    cleaned = typed.dropna(
        subset=["timestamp", "from_account", "to_account", "amount_paid", "amount_received"]
    )
    cleaned = cleaned[(cleaned["amount_paid"] >= 0) & (cleaned["amount_received"] >= 0)]
    cleaned = cleaned.drop_duplicates().sort_values("timestamp", kind="stable").reset_index(drop=True)
    return cleaned, report
