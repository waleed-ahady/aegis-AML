# Validation record

The delivered repository was validated on Python 3.13.5.

## Completed checks

- Python bytecode compilation for `src/`, `scripts/`, and `dashboard.py`
- Nine pytest tests covering data contracts, invalid-row handling, offline/online feature parity, temporal leakage protection, threshold selection, model-bundle round trip, scoring, drift, and API startup
- Editable package and console-entry-point validation
- Wheel build validation
- End-to-end smoke run with 1,800 generated transactions:
  - generation;
  - ingestion and quality report;
  - temporal training and evaluation;
  - model serialization and loading;
  - graph-risk report;
  - drift report;
  - online transaction scoring
- TOML and YAML parsing for project, configuration, CI, and infrastructure files
- Git ignore and tracked-file size review

## Environment limitation

Docker was not available in the construction environment, so the Compose stack was not executed here. The Compose YAML was parsed successfully, and the underlying application components were exercised directly. Run `docker compose up --build` in an environment with Docker to validate image pulls, container networking, and host-specific resource behavior.

## Dataset limitation

The full IBM dataset was not redistributed or downloaded during packaging. The repository includes a tiny generated sample and a credential-aware download script. Full-dataset runtime and memory requirements depend on the selected IBM variant and deployment environment.
