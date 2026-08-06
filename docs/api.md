# API reference

Interactive OpenAPI documentation is available at `/docs` while the service is running.

## Authentication

Development configuration disables API-key enforcement. Production configuration enables it. Set `AEGIS_API_KEY` and send:

```text
X-API-Key: <secret>
```

Replace this reference mechanism with service identity or OAuth2/JWT and role-based authorization in a real deployment.

## `GET /health`

Reports process health and whether a model is loaded. It returns 200 even when the model is absent so infrastructure can distinguish liveness from readiness.

```json
{
  "status": "ok",
  "model_ready": true,
  "model_version": "20260801012000"
}
```

## `GET /ready`

Returns 200 only when the model is loaded. Returns 503 otherwise.

## `POST /v1/score`

Request:

```json
{
  "transaction_id": "tx-10001",
  "timestamp": "2026-08-01T01:20:00Z",
  "from_bank": "B001",
  "from_account": "A0000100",
  "to_bank": "B019",
  "to_account": "A0000900",
  "amount_received": 9900.0,
  "receiving_currency": "USD",
  "amount_paid": 9900.0,
  "payment_currency": "USD",
  "payment_format": "Wire"
}
```

Response:

```json
{
  "transaction_id": "tx-10001",
  "alert_id": "ALT-63e8b9289c10405b",
  "risk_score": 0.9872,
  "threshold": 0.941,
  "decision": "alert",
  "reason_codes": [
    "AMOUNT_ABOVE_SENDER_BASELINE",
    "RAPID_REPEAT_SENDER_ACTIVITY"
  ],
  "model_version": "20260801012000"
}
```

An `allow` decision has a null `alert_id`. Only alerts are persisted by the reference implementation.

## `GET /v1/alerts?limit=100`

Returns recent persisted alerts. The limit is constrained to 1–500.

## `POST /v1/alerts/{alert_id}/feedback`

Request:

```json
{
  "outcome": "false_positive",
  "notes": "Known treasury sweep between related accounts."
}
```

Allowed outcomes:

- `confirmed_laundering`
- `false_positive`
- `needs_review`

Returns 404 when the alert does not exist.

## `GET /metrics`

Prometheus exposition endpoint. It is intentionally excluded from OpenAPI. Protect it at the network layer in production.

## Error semantics

| Status | Meaning |
|---|---|
| 401 | API key missing or invalid when enforcement is enabled |
| 404 | Alert not found |
| 422 | Request failed Pydantic validation |
| 503 | Model bundle is not loaded |
| 500 | Unexpected internal failure; transaction details are not returned |
