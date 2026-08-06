# Source-code and function guide

This guide explains the responsibilities and public extension points under `src/aegis_aml`.

## Root modules

### `config.py`

- `load_config(path=None)`: loads YAML configuration and merges one `extends` parent file recursively by key.
- `env(name, default=None)`: small environment-variable helper.

Configuration controls random seed, temporal split fractions, business costs, alert capacity, model hyperparameters, API behavior, and drift thresholds.

### `logging.py`

- `JsonFormatter`: emits structured JSON logs for container log collectors.
- `configure_logging(level=None)`: installs the formatter on the root logger.

Account identifiers and full transaction payloads are intentionally not logged by default.

## Data package

### `data/contracts.py`

- `CANONICAL_COLUMNS`: authoritative internal transaction schema.
- `normalize_columns(frame)`: maps IBM display names and accepted aliases to canonical names.
- `coerce_types(frame)`: converts timestamps, amounts, identifiers, categories, and labels.
- `validate(frame)`: returns `DataQualityReport` before invalid rows are removed.
- `clean(frame)`: applies type conversion, validation, filtering, deduplication, sorting, and index reset.

Add new source-system adapters before this boundary rather than changing downstream model code.

### `data/generate.py`

- `generate_demo_transactions(rows, seed)`: creates an IBM-compatible DataFrame with normal behavior, cycles, fan-out structuring, and limited label noise.
- `write_demo(path, rows, seed)`: persists generated data.

The generator is deterministic for a given seed.

### `data/ingest.py`

- `ingest_csv(source, destination, quality_report=None, max_rows=None)`: reads, cleans, writes, and records quality metadata.
- `read_transactions(path, max_rows=None)`: loads canonical CSV or Parquet for downstream jobs.

## Feature package

### `features/transaction.py`

- `NUMERIC_FEATURES`, `CATEGORICAL_FEATURES`, `MODEL_FEATURES`: explicit serving contract for model input.
- `build_causal_features(frame)`: vectorized offline feature calculation. It creates transaction, temporal, behavioral, and local graph features from prior rows only.
- `AccountProfile`: sender and receiver activity state for one account.
- `FeatureState`: reference online feature store.
- `FeatureState.from_frame(frame)`: creates a deployment snapshot from historical transactions.
- `FeatureState.make_features(transaction)`: calculates one feature row before state mutation.
- `FeatureState.update(...)`: incorporates a completed transaction into account and pair history.

When adding a feature, implement it in both `build_causal_features` and `FeatureState.make_features`, then add a parity test.

### `features/graph.py`

- `build_graph_risk_report(frame, output=None)`: builds a directed NetworkX graph, calculates account-level flow and centrality indicators, and writes a sorted investigation report.

This module may use labels for retrospective investigation. Do not copy label-derived fields into model features.

## Modeling package

### `modeling/train.py`

- `temporal_slices(rows, validation_fraction, test_fraction)`: returns non-overlapping chronological slices.
- `make_pipeline(model_config, random_seed)`: creates preprocessing and histogram gradient boosting steps.
- `train_model(...)`: orchestrates loading, feature engineering, fitting, threshold selection, evaluation, state snapshotting, and artifact writing.

The model pipeline owns category encoding so the API does not need separate category mappings.

### `modeling/threshold.py`

- `ThresholdResult`: selected operating-point metadata.
- `select_threshold(...)`: evaluates probability quantiles and minimizes expected cost while attempting to satisfy recall and alert-rate constraints.

If no candidate satisfies both constraints, the minimum-cost candidate is returned and the evaluation report reveals the achieved operating point.

### `modeling/evaluate.py`

- `evaluate_predictions(...)`: computes precision, recall, F1, average precision, ROC AUC, confusion counts, alert rate, and expected cost.

Average precision is the primary ranking metric because laundering labels are rare.

### `modeling/bundle.py`

- `ModelBundle`: serializable object containing the fitted pipeline, threshold, version, timestamp, metrics, feature state, feature names, and dataset summary.
- `save(path)` and `load(path)`: joblib persistence with a type check.

For production, sign artifacts and store them in a registry rather than accepting arbitrary joblib files.

### `modeling/reasons.py`

- `build_reason_codes(features, risk_score)`: produces stable analyst indicators such as rapid activity, unusual amount ratio, cross-currency transfer, or round amount.

These codes explain observed risk indicators; they are not model feature attribution.

## API package

### `api/schemas.py`

Pydantic request and response models enforce identifiers, nonnegative amounts, valid timestamps, currency normalization, feedback outcomes, and response bounds.

### `api/service.py`

- `ScoringService(model_path, update_state=True)`: loads a bundle and deep-copies its state.
- `score(payload)`: locks feature state, calculates features, predicts, applies threshold, optionally updates history, and returns a decision plus reason codes.

A process-local lock prevents races inside one worker. Shared state is required before multi-worker deployment.

### `api/main.py`

FastAPI lifecycle and routes:

- loads configuration, database, and model;
- enforces optional API-key authentication;
- exposes health, readiness, scoring, alert listing, analyst feedback, and metrics;
- persists alert decisions;
- records Prometheus counters and histograms.

## Persistence package

### `persistence/database.py`

- `AlertRecord`: SQLAlchemy table for alert payload, score, threshold, reason codes, model version, and feedback.
- `create_session_factory(database_url=None)`: configures SQLite or another SQLAlchemy URL and creates tables.
- `save_alert(...)`: transactional insert.
- `add_feedback(...)`: transactional analyst outcome update.
- `recent_alerts(...)`: dashboard/API read model.

Replace direct table creation with Alembic migrations before production use.

## Monitoring package

### `monitoring/metrics.py`

Defines scoring count, status, latency, score distribution, readiness, and feedback metrics. Labels are intentionally low-cardinality.

### `monitoring/drift.py`

- `population_stability_index(reference, current, bins=10)`: numeric distribution shift with reference quantile bins.
- `categorical_distance(reference, current)`: total-variation distance across category frequencies.
- `drift_report(...)`: calculates selected feature shifts and assigns healthy, warning, or critical status.

Drift is a diagnostic signal, not an automatic proof that retraining is beneficial.

## Streaming package

### `streaming/producer.py`

- `stream_csv(...)`: converts canonical or IBM-style rows to scoring payloads and sends them at a configurable rate.

### `streaming/consumer.py`

- `consume_and_score(...)`: consumes input records, calls the API, publishes alert payloads, and commits successful messages.

## CLI

`cli.py` exposes package functions through `aegis-aml` subcommands. The files in `scripts/` prepend the correct subcommand, keeping workflow commands discoverable while preserving one implementation.
