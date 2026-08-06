FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system aegis && useradd --system --gid aegis --create-home aegis
WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install --upgrade pip && \
    python -m pip install ".[streaming,dashboard,postgres]"

COPY configs ./configs
COPY scripts ./scripts
COPY dashboard.py ./dashboard.py
COPY infra ./infra
RUN mkdir -p /app/data/raw /app/data/processed /app/models /app/reports && \
    chown -R aegis:aegis /app

USER aegis
EXPOSE 8000
CMD ["uvicorn", "aegis_aml.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
