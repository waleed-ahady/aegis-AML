# Production hardening roadmap

AegisAML is complete as a runnable reference platform, but regulated production requires additional controls.

## Priority 0: correctness and security

- Replace joblib trust with signed artifacts and controlled registry download.
- Add OAuth2/service identity, role-based authorization, and network policies.
- Add Alembic migrations and explicit database schemas.
- Add idempotency keys for transaction scoring and alert inserts.
- Introduce dead-letter handling, bounded retries, and poison-message quarantine.
- Redact/tokenize account identifiers and encrypt sensitive fields.
- Add immutable audit events for scoring, threshold, model, and feedback changes.

## Priority 1: distributed online features

- Move account and pair state out of the API process.
- Use event-time windows, watermarks, and late-event policy.
- Define offline/online feature parity tests and feature freshness SLOs.
- Add backfill and state-reconstruction procedures.
- Track point-in-time-correct feature lineage.

## Priority 2: model development

- Calibrate probabilities on a separate temporal range.
- Add rules-plus-model ensembles and case-level aggregation.
- Evaluate LightGBM/CatBoost and graph models against the baseline.
- Add hard-negative mining based on analyst feedback.
- Add segment-level performance and fairness/impact analysis.
- Add challenger shadow scoring and sequential testing.

## Priority 3: case management and governance

- Integrate alerts with a real case-management workflow.
- Add alert deduplication, entity resolution, and case grouping.
- Add reviewer assignment, service-level timers, dispositions, and evidence attachments.
- Formalize model inventory, approvals, periodic review, and regulatory documentation.

## Priority 4: observability and resilience

- Add OpenTelemetry traces and correlation IDs.
- Create Grafana dashboards and SLO alerts.
- Add load, soak, chaos, recovery, and disaster-recovery tests.
- Store reference distributions and performance history centrally.
- Automate rollback based on reviewed deployment gates, not raw drift alone.
