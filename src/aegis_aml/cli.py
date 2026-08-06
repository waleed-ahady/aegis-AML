from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from aegis_aml.data.generate import write_demo
from aegis_aml.data.ingest import ingest_csv, read_transactions
from aegis_aml.features.graph import build_graph_risk_report
from aegis_aml.modeling.train import train_model
from aegis_aml.monitoring.drift import drift_report
from aegis_aml.streaming.consumer import consume_and_score
from aegis_aml.streaming.producer import stream_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aegis-aml", description="AegisAML command-line interface")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate-demo", help="Generate IBM-schema-compatible demo data")
    generate.add_argument("--rows", type=int, default=10_000)
    generate.add_argument("--seed", type=int, default=42)
    generate.add_argument("--output", default="data/raw/demo_transactions.csv")

    ingest = subparsers.add_parser("ingest", help="Validate and normalize a transaction CSV")
    ingest.add_argument("--input", required=True)
    ingest.add_argument("--output", required=True)
    ingest.add_argument("--quality-report")
    ingest.add_argument("--max-rows", type=int)

    train = subparsers.add_parser("train", help="Train and evaluate the temporal AML model")
    train.add_argument("--data", required=True)
    train.add_argument("--output", default="models/model_bundle.joblib")
    train.add_argument("--report", default="reports/evaluation.json")
    train.add_argument("--config")
    train.add_argument("--max-rows", type=int)

    graph = subparsers.add_parser("graph-report", help="Build an offline account-network risk report")
    graph.add_argument("--data", required=True)
    graph.add_argument("--output", default="reports/graph_risk.csv")

    drift = subparsers.add_parser("drift", help="Compare a reference and current transaction window")
    drift.add_argument("--reference", required=True)
    drift.add_argument("--current", required=True)
    drift.add_argument("--output", default="reports/drift.json")

    producer = subparsers.add_parser("produce", help="Replay a CSV into Kafka/Redpanda")
    producer.add_argument("--data", required=True)
    producer.add_argument("--bootstrap", default=os.getenv("AEGIS_KAFKA_BOOTSTRAP_SERVERS", "localhost:19092"))
    producer.add_argument("--topic", default=os.getenv("AEGIS_KAFKA_INPUT_TOPIC", "transactions"))
    producer.add_argument("--rate", type=float, default=10.0)
    producer.add_argument("--limit", type=int)

    consumer = subparsers.add_parser("consume", help="Consume, score, and emit AML alerts")
    consumer.add_argument("--bootstrap", default=os.getenv("AEGIS_KAFKA_BOOTSTRAP_SERVERS", "localhost:19092"))
    consumer.add_argument("--input-topic", default=os.getenv("AEGIS_KAFKA_INPUT_TOPIC", "transactions"))
    consumer.add_argument("--alert-topic", default=os.getenv("AEGIS_KAFKA_ALERT_TOPIC", "aml-alerts"))
    consumer.add_argument("--api-url", default=os.getenv("AEGIS_API_URL", "http://localhost:8000"))
    consumer.add_argument("--api-key", default=os.getenv("AEGIS_API_KEY"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "generate-demo":
        path = write_demo(args.output, rows=args.rows, seed=args.seed)
        print(path)
    elif args.command == "ingest":
        path = ingest_csv(args.input, args.output, args.quality_report, args.max_rows)
        print(path)
    elif args.command == "train":
        bundle = train_model(args.data, args.output, args.report, args.config, args.max_rows)
        print(json.dumps(bundle.metrics, indent=2))
    elif args.command == "graph-report":
        report = build_graph_risk_report(read_transactions(args.data), args.output)
        print(f"Wrote {len(report)} account rows to {args.output}")
    elif args.command == "drift":
        print(json.dumps(drift_report(args.reference, args.current, args.output), indent=2))
    elif args.command == "produce":
        count = stream_csv(args.data, args.bootstrap, args.topic, args.rate, args.limit)
        print(f"Produced {count} transactions")
    elif args.command == "consume":
        consume_and_score(
            args.bootstrap,
            args.input_topic,
            args.alert_topic,
            args.api_url,
            args.api_key,
        )


if __name__ == "__main__":
    main()
