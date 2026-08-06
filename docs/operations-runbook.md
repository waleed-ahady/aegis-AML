# Operations runbook

## Deployment prerequisites

- Model bundle produced by an approved training run
- Configuration reviewed for environment-specific alert capacity and authentication
- Database reachable and migrated
- API secrets provided through a secrets manager
- Metrics scraping and alert routing configured
- Rollback model version retained

## Local startup

```bash
make demo
make api
```

Container startup:

```bash
docker compose up --build
```

## Health checks

- `/health`: process is responsive; inspect `model_ready`.
- `/ready`: model is loaded and scoring can be attempted.
- `/metrics`: `aegis_model_ready` should equal 1.

## Routine checks

1. Confirm request error rate and p95/p99 latency.
2. Compare alert rate with configured investigation capacity.
3. Inspect risk-score distribution for sudden collapse or saturation.
4. Review analyst feedback volume and outcome mix.
5. Run drift comparison for the latest complete monitoring window.
6. Confirm all instances report the intended model version.

## Incident: model not ready

Symptoms: `/ready` returns 503 and `aegis_model_ready` is zero.

Actions:

1. Confirm `AEGIS_MODEL_PATH` points to a mounted artifact.
2. Verify artifact permissions and checksum.
3. Attempt `ModelBundle.load` in an isolated shell.
4. Roll back to the previous signed artifact if loading fails.
5. Do not bypass readiness by routing traffic to an uninitialized instance.

## Incident: elevated API errors

1. Inspect structured logs and database connectivity.
2. Verify payload contract failures are 422 rather than 500.
3. Check model prediction latency and memory pressure.
4. Check duplicate transaction retries from the consumer.
5. Disable consumer traffic or scale the API only after shared-state semantics are addressed.

## Incident: alert spike

1. Compare source transaction volume and category mix.
2. Check feature and score drift.
3. Confirm threshold and model version did not change unexpectedly.
4. Inspect top reason codes and source systems.
5. Engage fraud operations before changing the threshold.
6. Apply a reviewed temporary capacity control only with documented risk acceptance.

## Incident: alert collapse

1. Confirm transactions are reaching the API.
2. Verify categorical values are not unexpectedly mapped to unknown.
3. Check model readiness and score histogram.
4. Compare current data with the reference window.
5. Verify online history is being updated or supplied by the shared feature system.

## Rollback

1. Stop promotion of the current model.
2. Point `AEGIS_MODEL_PATH` or deployment metadata to the previous artifact.
3. Restart instances and confirm `/ready` plus model version.
4. Compare scores on a fixed replay sample.
5. Record the rollback reason and affected decision interval.

Database schema rollback is separate from model rollback. Keep serving contracts backward-compatible across at least one model version.

## Drift workflow

```bash
python scripts/check_drift.py \
  --reference data/processed/reference.csv \
  --current data/processed/latest_window.csv \
  --output reports/latest_drift.json
```

A warning triggers investigation. A critical result does not automatically trigger deployment. Review label maturity, operational metrics, and challenger evaluation first.

## Retraining checklist

- Freeze a time-bounded and versioned data snapshot.
- Verify label definitions and maturity window.
- Run quality checks and leakage tests.
- Compare candidate with the current champion on the same temporal test protocol.
- Recalculate the operating threshold using current cost assumptions.
- Review alert volume and segment-level behavior.
- Approve, sign, register, and stage the artifact.
- Use a shadow or canary phase before full promotion.
