from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from aegis_aml.config import load_config
from aegis_aml.data.ingest import read_transactions
from aegis_aml.features.transaction import (
    CATEGORICAL_FEATURES,
    MODEL_FEATURES,
    NUMERIC_FEATURES,
    FeatureState,
    build_causal_features,
)
from aegis_aml.modeling.bundle import ModelBundle
from aegis_aml.modeling.evaluate import evaluate_predictions
from aegis_aml.modeling.threshold import select_threshold


def temporal_slices(
    rows: int, validation_fraction: float, test_fraction: float
) -> tuple[slice, slice, slice]:
    if rows < 100:
        raise ValueError("At least 100 rows are required for temporal train/validation/test splits")
    train_end = int(rows * (1.0 - validation_fraction - test_fraction))
    validation_end = int(rows * (1.0 - test_fraction))
    if train_end <= 0 or validation_end <= train_end or validation_end >= rows:
        raise ValueError("Invalid validation/test fractions")
    return slice(0, train_end), slice(train_end, validation_end), slice(validation_end, rows)


def make_pipeline(model_config: dict[str, Any], random_seed: int) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", SimpleImputer(strategy="median"), NUMERIC_FEATURES),
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "encoder",
                            OrdinalEncoder(
                                handle_unknown="use_encoded_value",
                                unknown_value=-1,
                                encoded_missing_value=-1,
                            ),
                        ),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    classifier = HistGradientBoostingClassifier(
        learning_rate=float(model_config.get("learning_rate", 0.08)),
        max_iter=int(model_config.get("max_iter", 250)),
        max_leaf_nodes=int(model_config.get("max_leaf_nodes", 31)),
        min_samples_leaf=int(model_config.get("min_samples_leaf", 30)),
        l2_regularization=float(model_config.get("l2_regularization", 1.0)),
        class_weight="balanced",
        random_state=random_seed,
    )
    return Pipeline([("preprocess", preprocessor), ("classifier", classifier)])


def train_model(
    data_path: str | Path,
    output_path: str | Path,
    report_path: str | Path,
    config_path: str | Path | None = None,
    max_rows: int | None = None,
) -> ModelBundle:
    config = load_config(config_path)
    training = config["training"]
    random_seed = int(config["project"]["random_seed"])

    raw = read_transactions(data_path, max_rows=max_rows)
    featured = build_causal_features(raw)
    train_slice, validation_slice, test_slice = temporal_slices(
        len(featured),
        float(training["validation_fraction"]),
        float(training["test_fraction"]),
    )
    x = featured[MODEL_FEATURES]
    y = featured["is_laundering"].astype(int).to_numpy()
    pipeline = make_pipeline(training["model"], random_seed=random_seed)
    pipeline.fit(x.iloc[train_slice], y[train_slice])

    validation_probabilities = pipeline.predict_proba(x.iloc[validation_slice])[:, 1]
    threshold_result = select_threshold(
        y[validation_slice],
        validation_probabilities,
        false_positive_cost=float(training["false_positive_cost"]),
        false_negative_cost=float(training["false_negative_cost"]),
        max_alert_rate=float(training["max_alert_rate"]),
        min_recall=float(training["min_recall"]),
    )
    test_probabilities = pipeline.predict_proba(x.iloc[test_slice])[:, 1]
    validation_metrics = evaluate_predictions(
        y[validation_slice],
        validation_probabilities,
        threshold_result.threshold,
        float(training["false_positive_cost"]),
        float(training["false_negative_cost"]),
    )
    test_metrics = evaluate_predictions(
        y[test_slice],
        test_probabilities,
        threshold_result.threshold,
        float(training["false_positive_cost"]),
        float(training["false_negative_cost"]),
    )

    trained_at = datetime.now(UTC).isoformat()
    model_version = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    dataset_summary = {
        "rows": len(featured),
        "train_rows": train_slice.stop,
        "validation_rows": validation_slice.stop - validation_slice.start,
        "test_rows": test_slice.stop - test_slice.start,
        "start_timestamp": str(featured["timestamp"].min()),
        "end_timestamp": str(featured["timestamp"].max()),
        "laundering_rate": float(featured["is_laundering"].mean()),
    }
    metrics = {
        "validation": validation_metrics,
        "test": test_metrics,
        "threshold_selection": threshold_result.__dict__,
    }
    bundle = ModelBundle(
        pipeline=pipeline,
        threshold=threshold_result.threshold,
        model_version=model_version,
        trained_at=trained_at,
        metrics=metrics,
        feature_state=FeatureState.from_frame(raw),
        feature_names=MODEL_FEATURES,
        dataset_summary=dataset_summary,
    )
    bundle.save(output_path)

    report = {
        "model_version": model_version,
        "trained_at": trained_at,
        "dataset": dataset_summary,
        "metrics": metrics,
        "configuration": config,
    }
    report_destination = Path(report_path)
    report_destination.parent.mkdir(parents=True, exist_ok=True)
    report_destination.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return bundle
