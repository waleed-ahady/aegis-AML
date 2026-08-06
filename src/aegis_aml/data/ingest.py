from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from aegis_aml.data.contracts import clean


def ingest_csv(
    source: str | Path,
    destination: str | Path,
    quality_report: str | Path | None = None,
    max_rows: int | None = None,
) -> Path:
    """Read, validate, normalize, and persist an IBM AML transaction CSV."""
    source_path = Path(source)
    output_path = Path(destination)
    frame = pd.read_csv(source_path, nrows=max_rows, low_memory=False)
    cleaned, report = clean(frame)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.suffix.lower() == ".parquet":
        try:
            cleaned.to_parquet(output_path, index=False)
        except ImportError as exc:
            raise RuntimeError("Parquet output requires `pip install -e '.[data]'`") from exc
    else:
        cleaned.to_csv(output_path, index=False)

    report_path = Path(quality_report) if quality_report else output_path.with_suffix(".quality.json")
    report_path.write_text(json.dumps(report.__dict__, indent=2), encoding="utf-8")
    return output_path


def read_transactions(path: str | Path, max_rows: int | None = None) -> pd.DataFrame:
    source = Path(path)
    if source.suffix.lower() == ".parquet":
        frame = pd.read_parquet(source)
        if max_rows:
            frame = frame.head(max_rows)
    else:
        frame = pd.read_csv(source, nrows=max_rows, low_memory=False)
    cleaned, _ = clean(frame)
    return cleaned
