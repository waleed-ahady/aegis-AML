from __future__ import annotations

from pathlib import Path

import pytest

from aegis_aml.data.contracts import clean
from aegis_aml.data.generate import generate_demo_transactions
from aegis_aml.modeling.train import train_model


@pytest.fixture(scope="session")
def trained_artifacts(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    directory = tmp_path_factory.mktemp("artifacts")
    data_path = directory / "transactions.csv"
    model_path = directory / "model.joblib"
    report_path = directory / "evaluation.json"
    cleaned, _ = clean(generate_demo_transactions(rows=2200, seed=7))
    cleaned.to_csv(data_path, index=False)
    train_model(data_path, model_path, report_path)
    return model_path, report_path
