from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd


def _kafka_producer(bootstrap_servers: str) -> Any:
    try:
        from confluent_kafka import Producer
    except ImportError as exc:
        raise RuntimeError("Install streaming support with `pip install -e '.[streaming]'`") from exc
    return Producer({"bootstrap.servers": bootstrap_servers, "client.id": "aegis-producer"})


def stream_csv(
    data_path: str | Path,
    bootstrap_servers: str,
    topic: str,
    events_per_second: float = 10.0,
    limit: int | None = None,
) -> int:
    producer = _kafka_producer(bootstrap_servers)
    frame = pd.read_csv(data_path, nrows=limit, low_memory=False)
    delay = 0.0 if events_per_second <= 0 else 1.0 / events_per_second
    delivered = 0

    for index, row in frame.iterrows():
        payload = {
            "transaction_id": f"stream-{index}",
            "timestamp": row.get("timestamp", row.get("Timestamp")),
            "from_bank": str(row.get("from_bank", row.get("From Bank"))),
            "from_account": str(row.get("from_account", row.get("Account"))),
            "to_bank": str(row.get("to_bank", row.get("To Bank"))),
            "to_account": str(row.get("to_account", row.get("Account.1"))),
            "amount_received": float(row.get("amount_received", row.get("Amount Received"))),
            "receiving_currency": str(row.get("receiving_currency", row.get("Receiving Currency"))),
            "amount_paid": float(row.get("amount_paid", row.get("Amount Paid"))),
            "payment_currency": str(row.get("payment_currency", row.get("Payment Currency"))),
            "payment_format": str(row.get("payment_format", row.get("Payment Format"))),
        }
        producer.produce(topic, key=payload["transaction_id"], value=json.dumps(payload))
        producer.poll(0)
        delivered += 1
        if delay:
            time.sleep(delay)

    producer.flush(30)
    return delivered
