from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _kafka_clients(bootstrap_servers: str, group_id: str) -> tuple[Any, Any]:
    try:
        from confluent_kafka import Consumer, Producer
    except ImportError as exc:
        raise RuntimeError(
            "Install streaming support with `pip install -e '.[streaming]'`"
        ) from exc
    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    producer = Producer(
        {"bootstrap.servers": bootstrap_servers, "client.id": "aegis-alert-producer"}
    )
    return consumer, producer


def consume_and_score(
    bootstrap_servers: str,
    input_topic: str,
    alert_topic: str,
    api_url: str,
    api_key: str | None = None,
    group_id: str = "aegis-scorers",
) -> None:
    consumer, producer = _kafka_clients(bootstrap_servers, group_id)
    consumer.subscribe([input_topic])
    headers = {"X-API-Key": api_key} if api_key else {}

    with httpx.Client(base_url=api_url, timeout=10.0, headers=headers) as client:
        try:
            while True:
                message = consumer.poll(1.0)
                if message is None:
                    continue
                if message.error():
                    logger.error("Kafka consumer error: %s", message.error())
                    continue

                payload = json.loads(message.value())
                response = client.post("/v1/score", json=payload)
                if response.status_code != 200:
                    print("FAILED TRANSACTION:")
                    print(payload)
                    print("API RESPONSE:")
                    print(response.status_code, response.text)
                    continue
                result = response.json()

                response.raise_for_status()
                result = response.json()
                if result["decision"] == "alert":
                    producer.produce(
                        alert_topic,
                        key=result["alert_id"],
                        value=json.dumps({"transaction": payload, "score": result}),
                    )
                    producer.poll(0)
                consumer.commit(message=message, asynchronous=False)
        except KeyboardInterrupt:
            logger.info("Consumer stopped")
        finally:
            producer.flush(10)
            consumer.close()
