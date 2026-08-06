# Model card: AegisAML baseline

## Model details

- Task: transaction-level binary ranking and alerting for synthetic AML labels
- Model family: histogram gradient boosting
- Preprocessing: numeric median imputation and categorical ordinal encoding with unknown-value handling
- Decision policy: validation-selected threshold with false-positive cost, false-negative cost, maximum alert rate, and minimum recall
- Artifact: joblib `ModelBundle` containing model, threshold, metadata, and online feature-state snapshot

## Intended use

The model is intended for education, portfolio demonstration, architecture prototyping, synthetic-data benchmarking, and experimentation with transaction-monitoring workflows.

It may support prioritization for human review after independent validation, policy rules, governance, and controls are added.

## Out-of-scope use

Do not use the baseline as the sole mechanism to:

- accuse a person or organization of criminal activity;
- close or freeze an account;
- file regulatory reports;
- satisfy jurisdiction-specific AML obligations;
- transfer performance claims from synthetic data to real customers;
- infer protected or sensitive attributes.

## Inputs

Transaction amount, currencies, payment format, time, bank relationship, sender/receiver prior activity, amount relative to prior averages, time since prior activity, previous pair count, and prior unique counterparties.

The model does not include KYC, customer demographics, sanctions, adverse media, geographic risk, business type, beneficial ownership, or case outcomes beyond the synthetic label.

## Evaluation design

Data is sorted by event time. The earliest range trains the classifier, the next range selects the threshold, and the latest range is held out for evaluation. This approximates future deployment and is preferable to random splitting for evolving financial behavior.

Report:

- positive and alert rates;
- precision, recall, and F1 at the operating threshold;
- average precision and ROC AUC;
- confusion matrix;
- expected operational cost.

## Limitations

- Synthetic ground truth is complete but cannot reproduce every real laundering behavior or institutional detection bias.
- A transaction-level label may not represent case-level investigation logic.
- The model may learn artifacts of the simulator, data variant, or demo generator.
- Historical state in the reference service is process-local.
- Reason codes are heuristic indicators, not faithful model attribution.
- Probability calibration is not explicitly optimized.
- Threshold cost values are illustrative and must be supplied by operations and compliance stakeholders.
- Fairness cannot be established without a defined population, relevant attributes, legal basis, and impact analysis.

## Monitoring

Track input drift, score distribution, alert rate, latency, API failures, model version, analyst outcomes, precision proxies, and delayed confirmed-case recall. Investigate changes before retraining.

## Governance requirements for production

- Independent model validation and documented approval
- Data lineage and reproducible training snapshots
- Artifact signing and controlled promotion
- Four-eyes approval for threshold changes
- Champion/challenger rollout and rollback
- Audit trail containing model version and feature snapshot
- Bias and impact assessment
- Regulatory and legal review
- Periodic performance review based on mature case outcomes
