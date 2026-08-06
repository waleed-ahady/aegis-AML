from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


CATEGORICAL_FEATURES = ["payment_format", "payment_currency", "receiving_currency"]
NUMERIC_FEATURES = [
    "amount_paid",
    "amount_received",
    "amount_log1p",
    "amount_ratio",
    "hour",
    "day_of_week",
    "is_weekend",
    "is_night",
    "cross_bank",
    "cross_currency",
    "is_round_amount",
    "sender_prev_tx_count",
    "receiver_prev_tx_count",
    "sender_prev_avg_amount",
    "receiver_prev_avg_amount",
    "sender_amount_to_avg",
    "receiver_amount_to_avg",
    "sender_minutes_since_last",
    "receiver_minutes_since_last",
    "pair_prev_count",
    "sender_unique_counterparties",
    "receiver_unique_counterparties",
]
MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0, np.nan)


def build_causal_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Build time-causal transaction and local graph features without label leakage.

    The input must use canonical columns. Rows are sorted by time. Every historical
    feature is computed from transactions strictly preceding the current row.
    """
    ordered = frame.sort_values("timestamp", kind="stable").reset_index(drop=True).copy()
    amount = ordered["amount_paid"].astype(float)

    ordered["amount_log1p"] = np.log1p(amount.clip(lower=0))
    ordered["amount_ratio"] = _safe_ratio(
        ordered["amount_received"].astype(float), amount.clip(lower=1e-9)
    ).fillna(1.0)
    ordered["hour"] = ordered["timestamp"].dt.hour.astype("int16")
    ordered["day_of_week"] = ordered["timestamp"].dt.dayofweek.astype("int8")
    ordered["is_weekend"] = (ordered["day_of_week"] >= 5).astype("int8")
    ordered["is_night"] = ordered["hour"].isin([0, 1, 2, 3, 4, 5]).astype("int8")
    ordered["cross_bank"] = (ordered["from_bank"] != ordered["to_bank"]).astype("int8")
    ordered["cross_currency"] = (
        ordered["payment_currency"] != ordered["receiving_currency"]
    ).astype("int8")
    ordered["is_round_amount"] = (np.isclose(amount % 1000, 0, atol=1.0)).astype("int8")

    sender_group = ordered.groupby("from_account", sort=False, observed=True)
    receiver_group = ordered.groupby("to_account", sort=False, observed=True)

    sender_count = sender_group.cumcount().astype("int32")
    receiver_count = receiver_group.cumcount().astype("int32")
    sender_prior_sum = sender_group["amount_paid"].cumsum() - amount
    receiver_prior_sum = receiver_group["amount_paid"].cumsum() - amount

    ordered["sender_prev_tx_count"] = sender_count
    ordered["receiver_prev_tx_count"] = receiver_count
    ordered["sender_prev_avg_amount"] = (sender_prior_sum / sender_count.replace(0, np.nan)).fillna(0.0)
    ordered["receiver_prev_avg_amount"] = (
        receiver_prior_sum / receiver_count.replace(0, np.nan)
    ).fillna(0.0)
    ordered["sender_amount_to_avg"] = (
        amount / ordered["sender_prev_avg_amount"].replace(0, np.nan)
    ).fillna(1.0).clip(upper=1000)
    ordered["receiver_amount_to_avg"] = (
        amount / ordered["receiver_prev_avg_amount"].replace(0, np.nan)
    ).fillna(1.0).clip(upper=1000)

    sender_delta = sender_group["timestamp"].diff().dt.total_seconds().div(60)
    receiver_delta = receiver_group["timestamp"].diff().dt.total_seconds().div(60)
    ordered["sender_minutes_since_last"] = sender_delta.fillna(1_000_000).clip(0, 1_000_000)
    ordered["receiver_minutes_since_last"] = receiver_delta.fillna(1_000_000).clip(0, 1_000_000)

    pair_group = ordered.groupby(["from_account", "to_account"], sort=False, observed=True)
    pair_previous = pair_group.cumcount().astype("int32")
    ordered["pair_prev_count"] = pair_previous
    first_pair = (pair_previous == 0).astype("int8")
    ordered["sender_unique_counterparties"] = (
        first_pair.groupby(ordered["from_account"], sort=False).cumsum() - first_pair
    ).astype("int32")
    ordered["receiver_unique_counterparties"] = (
        first_pair.groupby(ordered["to_account"], sort=False).cumsum() - first_pair
    ).astype("int32")

    return ordered


@dataclass
class AccountProfile:
    sent_count: int = 0
    received_count: int = 0
    sent_total: float = 0.0
    received_total: float = 0.0
    last_sent_timestamp: pd.Timestamp | None = None
    last_received_timestamp: pd.Timestamp | None = None
    sent_counterparties: set[str] = field(default_factory=set)
    received_counterparties: set[str] = field(default_factory=set)


@dataclass
class FeatureState:
    """Small in-memory online feature store used by the reference API."""

    accounts: dict[str, AccountProfile] = field(default_factory=dict)
    pair_counts: dict[tuple[str, str], int] = field(default_factory=dict)

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> "FeatureState":
        state = cls()
        for row in frame.sort_values("timestamp", kind="stable").itertuples(index=False):
            state.update(
                from_account=str(row.from_account),
                to_account=str(row.to_account),
                amount=float(row.amount_paid),
                timestamp=pd.Timestamp(row.timestamp),
            )
        return state

    def _profile(self, account: str) -> AccountProfile:
        return self.accounts.setdefault(account, AccountProfile())

    def make_features(self, transaction: dict[str, Any]) -> dict[str, Any]:
        timestamp = pd.Timestamp(transaction["timestamp"])
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        else:
            timestamp = timestamp.tz_convert("UTC")

        sender_id = str(transaction["from_account"])
        receiver_id = str(transaction["to_account"])
        sender = self._profile(sender_id)
        receiver = self._profile(receiver_id)
        amount_paid = float(transaction["amount_paid"])
        amount_received = float(transaction.get("amount_received", amount_paid))
        sender_avg = sender.sent_total / sender.sent_count if sender.sent_count else 0.0
        receiver_avg = (
            receiver.received_total / receiver.received_count if receiver.received_count else 0.0
        )

        def minutes_since(last: pd.Timestamp | None) -> float:
            if last is None:
                return 1_000_000.0
            return float(max(0.0, min((timestamp - last).total_seconds() / 60, 1_000_000)))

        return {
            "amount_paid": amount_paid,
            "amount_received": amount_received,
            "amount_log1p": float(np.log1p(max(amount_paid, 0.0))),
            "amount_ratio": amount_received / amount_paid if amount_paid else 1.0,
            "hour": timestamp.hour,
            "day_of_week": timestamp.dayofweek,
            "is_weekend": int(timestamp.dayofweek >= 5),
            "is_night": int(timestamp.hour <= 5),
            "cross_bank": int(str(transaction["from_bank"]) != str(transaction["to_bank"])),
            "cross_currency": int(
                str(transaction["payment_currency"]) != str(transaction["receiving_currency"])
            ),
            "is_round_amount": int(np.isclose(amount_paid % 1000, 0, atol=1.0)),
            "sender_prev_tx_count": sender.sent_count,
            "receiver_prev_tx_count": receiver.received_count,
            "sender_prev_avg_amount": sender_avg,
            "receiver_prev_avg_amount": receiver_avg,
            "sender_amount_to_avg": min(amount_paid / sender_avg, 1000) if sender_avg else 1.0,
            "receiver_amount_to_avg": min(amount_paid / receiver_avg, 1000) if receiver_avg else 1.0,
            "sender_minutes_since_last": minutes_since(sender.last_sent_timestamp),
            "receiver_minutes_since_last": minutes_since(receiver.last_received_timestamp),
            "pair_prev_count": self.pair_counts.get((sender_id, receiver_id), 0),
            "sender_unique_counterparties": len(sender.sent_counterparties),
            "receiver_unique_counterparties": len(receiver.received_counterparties),
            "payment_format": str(transaction["payment_format"]),
            "payment_currency": str(transaction["payment_currency"]),
            "receiving_currency": str(transaction["receiving_currency"]),
        }

    def update(self, from_account: str, to_account: str, amount: float, timestamp: pd.Timestamp) -> None:
        timestamp = pd.Timestamp(timestamp)
        sender = self._profile(from_account)
        receiver = self._profile(to_account)
        sender.sent_count += 1
        sender.sent_total += amount
        sender.last_sent_timestamp = timestamp
        sender.sent_counterparties.add(to_account)
        receiver.received_count += 1
        receiver.received_total += amount
        receiver.last_received_timestamp = timestamp
        receiver.received_counterparties.add(from_account)
        pair = (from_account, to_account)
        self.pair_counts[pair] = self.pair_counts.get(pair, 0) + 1
