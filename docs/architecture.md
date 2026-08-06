# Architecture

## Design goals

AegisAML is designed to demonstrate the entire transaction-monitoring lifecycle while staying runnable on a developer laptop. It separates data contracts, feature computation, model training, online scoring, persistence, streaming, monitoring, and analyst feedback so each component can later be replaced independently.

## Component boundaries

### Ingestion boundary

`aegis_aml.data.contracts` is the authoritative schema boundary. External IBM-style names are converted to canonical snake-case names. Invalid timestamps, negative amounts, duplicates, and missing accounts are counted before invalid rows are removed. The quality report is persisted next to the processed dataset.

### Feature boundary

`build_causal_features` sorts transactions chronologically and calculates all history-based values before including the current transaction. This preserves training/serving semantics and prevents common future-history leakage.

The reference API uses `FeatureState`, an in-process state store serialized inside the model bundle. It is intentionally small and transparent. A production deployment should replace it with a durable low-latency store or stream processor.

### Model boundary

The model receives only engineered columns listed in `MODEL_FEATURES`. Training uses chronological partitions. Validation selects an operating threshold; test data remains untouched until final evaluation. The model, threshold, metadata, and feature-state snapshot are saved as one `ModelBundle`.

### Serving boundary

FastAPI validates requests, computes online features, predicts a probability, applies the stored threshold, emits analyst reason codes, persists alerts, and exposes Prometheus metrics. Reason codes are deterministic operational indicators, not causal explanations or SHAP values.

### Streaming boundary

The producer replays CSV records into Kafka-compatible infrastructure. The consumer calls the scoring API and emits only alert decisions into a separate topic. Offset commits happen after successful scoring, giving at-least-once processing. Production systems must add idempotency at the persistence boundary.

## End-to-end flow

1. Obtain the IBM AML CSV or generate demo data.
2. Validate and canonicalize the data.
3. Build time-causal behavioral and local graph features.
4. Create chronological train, validation, and test ranges.
5. Fit the classifier on the training range.
6. Select a threshold on validation data using cost and alert-capacity constraints.
7. Evaluate once on test data.
8. Serialize the model bundle and current feature state.
9. Load the bundle into the API.
10. Receive transactions directly or through Kafka/Redpanda.
11. Persist model alerts and accept analyst feedback.
12. Compare later transaction windows against a reference window for drift.

## Consistency and concurrency

The reference scoring service protects the in-memory feature state with a process-local lock. This is correct for one API process. Multiple workers would each maintain different account histories, so the default container runs one process. Before horizontal scaling, move state to a shared system such as Redis, Cassandra, a feature store, or a Kafka Streams/Flink state backend.

## Reliability behavior

- A missing model returns HTTP 503 from readiness and scoring endpoints.
- Database writes are transactional through SQLAlchemy.
- A consumer message is committed only after successful API scoring.
- API metrics expose request status, decision, latency, risk distribution, model readiness, and analyst feedback.
- Model and data artifacts are external to the image and can be rolled back independently.

## Scaling path

The local implementation is intentionally pandas-based. For the largest IBM files or enterprise traffic, preserve the contracts but replace implementations:

| Local component | Scaled replacement |
|---|---|
| pandas ingestion | Spark, DuckDB, Polars streaming, or warehouse SQL |
| `FeatureState` | Flink/Kafka Streams state, Redis, Cassandra, or Feast online store |
| CSV processed data | Partitioned Parquet in object storage or lakehouse tables |
| NetworkX report | Spark GraphFrames, Neo4j Graph Data Science, or a distributed graph engine |
| joblib artifact | Signed object-store artifact plus registry metadata |
| one FastAPI process | Horizontally scaled stateless API using shared online features |
| SQLite | Postgres or an operational case-management database |

## Trust boundaries

Transactions and analyst decisions are sensitive even when the initial dataset is synthetic. In production:

- Authenticate both users and services.
- Authorize scoring, alert read, and feedback actions separately.
- Encrypt transport and storage.
- Do not place full account identifiers in metrics or logs.
- Store secrets in a managed secrets system.
- Maintain immutable audit logs for model version, features, decision, and reviewer actions.
- Establish retention and deletion policies with compliance and legal teams.

## Known architectural limitations

- In-memory online features are not shared across API replicas.
- The demo reason codes are not local feature-attribution values.
- The streaming consumer has no dead-letter topic in the reference implementation.
- Feedback is stored but is not automatically promoted into retraining.
- Graph ranking is an offline investigation report, not a graph neural network.
- No identity/KYC/customer-risk table is included in the IBM transaction-only contract.
