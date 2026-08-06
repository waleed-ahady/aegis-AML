from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


PAYMENT_FORMATS = np.array(["ACH", "Wire", "Cheque", "Credit Card", "Cash", "Reinvestment"])
CURRENCIES = np.array(["USD", "EUR", "GBP", "JPY", "CHF", "CAD"])


def generate_demo_transactions(rows: int = 10_000, seed: int = 42) -> pd.DataFrame:
    """Generate an IBM-schema-compatible demo dataset with embedded AML patterns."""
    rng = np.random.default_rng(seed)
    account_count = max(400, rows // 8)
    accounts = np.array([f"A{index:07d}" for index in range(account_count)])
    banks = np.array([f"B{index:03d}" for index in range(30)])
    account_bank = {account: rng.choice(banks) for account in accounts}

    start = datetime(2025, 1, 1, tzinfo=UTC)
    seconds = np.sort(rng.integers(0, 120 * 24 * 3600, size=rows))
    sender = rng.choice(accounts, rows)
    receiver = rng.choice(accounts, rows)
    same_mask = sender == receiver
    while same_mask.any():
        receiver[same_mask] = rng.choice(accounts, int(same_mask.sum()))
        same_mask = sender == receiver

    base_amount = np.exp(rng.normal(5.2, 1.1, rows)).clip(1, 250_000)
    payment_format = rng.choice(PAYMENT_FORMATS, rows, p=[0.37, 0.24, 0.08, 0.20, 0.05, 0.06])
    payment_currency = rng.choice(CURRENCIES, rows, p=[0.49, 0.24, 0.11, 0.06, 0.05, 0.05])
    receiving_currency = payment_currency.copy()
    fx_mask = rng.random(rows) < 0.08
    receiving_currency[fx_mask] = rng.choice(CURRENCIES, int(fx_mask.sum()))

    labels = np.zeros(rows, dtype=np.int8)

    # Layering cycles: a small group transfers large round amounts in short bursts.
    ring_size = max(12, min(60, rows // 400))
    ring_accounts = rng.choice(accounts, ring_size, replace=False)
    ring_rows = rng.choice(rows, max(20, rows // 180), replace=False)
    ring_rows.sort()
    for offset, row in enumerate(ring_rows):
        sender[row] = ring_accounts[offset % ring_size]
        receiver[row] = ring_accounts[(offset + 1) % ring_size]
        base_amount[row] = rng.choice([9_500, 9_900, 19_800, 49_500, 99_000]) * rng.uniform(0.98, 1.02)
        payment_format[row] = rng.choice(["Wire", "Cash"])
        labels[row] = 1

    # Fan-out structuring: one source sends repeated sub-threshold payments.
    hub = rng.choice(accounts)
    fan_rows = rng.choice(np.setdiff1d(np.arange(rows), ring_rows), max(15, rows // 240), replace=False)
    for row in fan_rows:
        sender[row] = hub
        receiver[row] = rng.choice(accounts)
        base_amount[row] = rng.uniform(7_500, 9_999)
        payment_format[row] = "ACH"
        labels[row] = 1

    # Add a small amount of label noise to avoid perfectly rule-separable data.
    noise_rows = rng.choice(np.where(labels == 0)[0], max(3, rows // 2500), replace=False)
    labels[noise_rows] = 1

    received = base_amount.copy()
    received[fx_mask] *= rng.uniform(0.75, 1.25, int(fx_mask.sum()))

    frame = pd.DataFrame(
        {
            "Timestamp": [(start + timedelta(seconds=int(value))).strftime("%Y/%m/%d %H:%M") for value in seconds],
            "From Bank": [account_bank[value] for value in sender],
            "Account": sender,
            "To Bank": [account_bank[value] for value in receiver],
            "Account.1": receiver,
            "Amount Received": np.round(received, 2),
            "Receiving Currency": receiving_currency,
            "Amount Paid": np.round(base_amount, 2),
            "Payment Currency": payment_currency,
            "Payment Format": payment_format,
            "Is Laundering": labels,
        }
    )
    return frame.sort_values("Timestamp", kind="stable").reset_index(drop=True)


def write_demo(path: str | Path, rows: int = 10_000, seed: int = 42) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    generate_demo_transactions(rows=rows, seed=seed).to_csv(destination, index=False)
    return destination
