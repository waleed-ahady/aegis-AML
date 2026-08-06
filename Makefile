SHELL := /bin/bash
PYTHON ?= python
VENV ?= .venv

.PHONY: help install install-all lint format test generate-demo ingest train graph drift api producer consumer dashboard demo docker-up docker-down clean

help:
	@echo "AegisAML commands"
	@echo "  make install       Install core and development dependencies"
	@echo "  make demo          Generate data, ingest, train, evaluate, and graph-report"
	@echo "  make api           Start the scoring API"
	@echo "  make test          Run unit and API tests"
	@echo "  make docker-up     Start API, Redpanda, Postgres, Prometheus, and dashboard"

install:
	$(PYTHON) -m pip install -e ".[dev]"

install-all:
	$(PYTHON) -m pip install -e ".[all]"

lint:
	ruff check src tests scripts
	mypy src/aegis_aml

format:
	ruff check --fix src tests scripts
	ruff format src tests scripts

test:
	pytest --cov=aegis_aml --cov-report=term-missing

generate-demo:
	$(PYTHON) scripts/generate_demo_data.py --rows 12000 --output data/raw/demo_transactions.csv

ingest:
	$(PYTHON) scripts/ingest_data.py --input data/raw/demo_transactions.csv --output data/processed/transactions.csv

train:
	$(PYTHON) scripts/train_model.py --data data/processed/transactions.csv --output models/model_bundle.joblib --report reports/evaluation.json

graph:
	$(PYTHON) scripts/build_graph_report.py --data data/processed/transactions.csv --output reports/graph_risk.csv

drift:
	$(PYTHON) scripts/check_drift.py --reference data/processed/transactions.csv --current data/processed/transactions.csv --output reports/drift.json

api:
	uvicorn aegis_aml.api.main:app --host 0.0.0.0 --port 8000 --reload

producer:
	$(PYTHON) scripts/stream_producer.py --data data/processed/transactions.csv

consumer:
	$(PYTHON) scripts/stream_consumer.py

dashboard:
	streamlit run dashboard.py

demo: generate-demo ingest train graph
	@echo "Demo complete. Run 'make api' and open http://localhost:8000/docs"

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find data/raw data/processed models reports -type f ! -name '.gitkeep' -delete
