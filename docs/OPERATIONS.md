
## Rich operations dashboard

Run `make dashboard` after the API starts. The dashboard reads alert operations from the configured SQL database and supplements them with the API health endpoint, Prometheus metrics, the offline evaluation JSON, and optional graph/drift reports.

The dashboard contains six workspaces:

1. **Overview** — alert volume, risk distribution, reason-code frequency, analyst outcomes, and payment-format summaries.
2. **Alerts** — filters by risk, outcome, sender bank, transaction ID, alert ID, and account; filtered results can be downloaded as CSV.
3. **Investigation** — complete transaction payload, route, reason codes, model metadata, and analyst feedback submission through the API.
4. **Model performance** — test/validation metrics, dataset metadata, threshold, and confusion matrix from the training evaluation report.
5. **Operations** — API readiness, model version, health latency, request/error counters, and Prometheus metrics.
6. **Graph & drift** — top account-network risk rows and the most recent drift report when those artifacts exist.

Environment variables:

```text
AEGIS_DATABASE_URL=sqlite:///./aegis_alerts.db
AEGIS_API_URL=http://localhost:8000
AEGIS_EVALUATION_REPORT=reports/ibm_hi_small_evaluation.json
AEGIS_DRIFT_REPORT=reports/drift.json
AEGIS_GRAPH_REPORT=reports/graph_risk.csv
```

The dashboard deliberately separates live operational metrics from offline supervised evaluation. Live alerts alone cannot establish precision or recall until analysts provide reliable outcomes.
