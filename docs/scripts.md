# Script guide

Every file in `scripts/` is a thin wrapper around the package CLI. Keeping logic in `src/aegis_aml` makes it importable, testable, and reusable from orchestration systems.

## `generate_demo_data.py`

Creates an IBM-schema-compatible CSV with normal transactions and embedded synthetic AML patterns.

```bash
python scripts/generate_demo_data.py --rows 12000 --seed 42 --output data/raw/demo_transactions.csv
```

Output: raw CSV. Use only for system verification.

## `download_ibm_data.py`

Calls the Kaggle CLI for the IBM AML dataset. Kaggle credentials and the `data` dependency extra are required.

```bash
python scripts/download_ibm_data.py --output data/raw/ibm
```

Output: publisher files under the selected directory. Data remains ignored by Git.

## `ingest_data.py`

Normalizes IBM column names, coerces types, records data-quality findings, removes invalid rows, deduplicates, sorts by time, and writes CSV or Parquet.

```bash
python scripts/ingest_data.py \
  --input data/raw/demo_transactions.csv \
  --output data/processed/transactions.csv \
  --quality-report reports/data_quality.json \
  --max-rows 100000
```

## `train_model.py`

Builds time-causal features, creates temporal splits, trains the model, chooses the validation threshold, evaluates the test period, and serializes a model bundle.

```bash
python scripts/train_model.py \
  --data data/processed/transactions.csv \
  --output models/model_bundle.joblib \
  --report reports/evaluation.json \
  --config configs/development.yaml \
  --max-rows 500000
```

Outputs: joblib model bundle and JSON evaluation report.

## `build_graph_report.py`

Aggregates transactions into a directed account network and ranks nodes using flow, degree, PageRank, and reciprocity indicators.

```bash
python scripts/build_graph_report.py \
  --data data/processed/transactions.csv \
  --output reports/graph_risk.csv
```

The `known_laundering_edges` field is for offline analysis only.

## `check_drift.py`

Compares a reference dataset with a later transaction window. Numeric features use PSI; categorical values use total-variation distance.

```bash
python scripts/check_drift.py \
  --reference data/processed/reference.csv \
  --current data/processed/current.csv \
  --output reports/drift.json
```

## `stream_producer.py`

Replays canonical or IBM-style CSV rows into Kafka/Redpanda.

```bash
python scripts/stream_producer.py \
  --data data/processed/transactions.csv \
  --bootstrap localhost:19092 \
  --topic transactions \
  --rate 25 \
  --limit 10000
```

A rate of zero sends as quickly as possible.

## `stream_consumer.py`

Consumes transactions, calls the scoring API, publishes alert decisions, and commits offsets after successful scoring.

```bash
python scripts/stream_consumer.py \
  --bootstrap localhost:19092 \
  --input-topic transactions \
  --alert-topic aml-alerts \
  --api-url http://localhost:8000
```

Stop with Ctrl+C. Failed messages are retried because their offsets are not committed; add a retry policy and dead-letter topic before production use.
