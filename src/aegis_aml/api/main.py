from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from aegis_aml.api.schemas import FeedbackRequest, HealthResponse, ScoreResponse, TransactionRequest
from aegis_aml.api.service import ScoringService
from aegis_aml.config import load_config
from aegis_aml.logging import configure_logging
from aegis_aml.monitoring.metrics import (
    FEEDBACK_TOTAL,
    MODEL_READY,
    RISK_SCORE,
    SCORE_LATENCY,
    SCORE_REQUESTS,
)
from aegis_aml.persistence.database import add_feedback, create_session_factory, recent_alerts, save_alert

configure_logging()
logger = logging.getLogger(__name__)


def _config() -> dict[str, Any]:
    try:
        return load_config()
    except FileNotFoundError:
        return {"serving": {"api_key_required": False, "update_in_memory_profiles": True}}


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = _config()
    model_path = Path(os.getenv("AEGIS_MODEL_PATH", "models/model_bundle.joblib"))
    app.state.config = config
    app.state.session_factory = create_session_factory()
    app.state.scoring_service = None
    if model_path.exists():
        app.state.scoring_service = ScoringService(
            model_path,
            update_state=bool(config.get("serving", {}).get("update_in_memory_profiles", True)),
        )
        MODEL_READY.set(1)
        logger.info(
            "Model loaded",
            extra={"model_version": app.state.scoring_service.bundle.model_version},
        )
    else:
        MODEL_READY.set(0)
        logger.warning("Model bundle not found at %s", model_path)
    yield


app = FastAPI(
    title="AegisAML API",
    version="0.1.0",
    description="Real-time anti-money-laundering transaction scoring and analyst feedback API.",
    lifespan=lifespan,
)

@app.get("/", tags=["Root"]) # added one
def root():
    return {"project": "AegisAML",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready"
    }


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    config = app.state.config
    required = bool(config.get("serving", {}).get("api_key_required", False))
    expected = os.getenv("AEGIS_API_KEY")
    if required and (not expected or x_api_key != expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


@app.exception_handler(Exception)
async def unhandled_exception(_: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled API error", exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    service = app.state.scoring_service
    return HealthResponse(
        status="ok",
        model_ready=service is not None,
        model_version=service.bundle.model_version if service else None,
    )


@app.get("/ready", response_model=HealthResponse)
def ready() -> HealthResponse:
    service = app.state.scoring_service
    if service is None:
        raise HTTPException(status_code=503, detail="Model is not loaded")
    return HealthResponse(status="ready", model_ready=True, model_version=service.bundle.model_version)


@app.post("/v1/score", response_model=ScoreResponse, dependencies=[Depends(require_api_key)])
def score_transaction(request: TransactionRequest) -> ScoreResponse:
    service = app.state.scoring_service
    if service is None:
        SCORE_REQUESTS.labels(decision="unknown", status="not_ready").inc()
        raise HTTPException(status_code=503, detail="Model is not loaded")

    start = time.perf_counter()
    try:
        result = service.score(request.model_dump())
        RISK_SCORE.observe(result["risk_score"])
        SCORE_REQUESTS.labels(decision=result["decision"], status="success").inc()
        if result["decision"] == "alert":
            save_alert(
                app.state.session_factory,
                {
                    "alert_id": result["alert_id"],
                    "transaction_id": result["transaction_id"],
                    "risk_score": result["risk_score"],
                    "threshold": result["threshold"],
                    "decision": True,
                    "model_version": result["model_version"],
                    "reason_codes": result["reason_codes"],
                    "payload": request.model_dump(mode="json"),
                },
            )
        return ScoreResponse(**{key: value for key, value in result.items() if key != "features"})
    except Exception:
        SCORE_REQUESTS.labels(decision="unknown", status="error").inc()
        raise
    finally:
        SCORE_LATENCY.observe(time.perf_counter() - start)


@app.post("/v1/alerts/{alert_id}/feedback", dependencies=[Depends(require_api_key)])
def submit_feedback(alert_id: str, feedback: FeedbackRequest) -> dict[str, str]:
    updated = add_feedback(app.state.session_factory, alert_id, feedback.outcome, feedback.notes)
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")
    FEEDBACK_TOTAL.labels(outcome=feedback.outcome).inc()
    return {"status": "accepted", "alert_id": alert_id}


@app.get("/v1/alerts", dependencies=[Depends(require_api_key)])
def list_alerts(limit: int = 100) -> list[dict[str, Any]]:
    return recent_alerts(app.state.session_factory, limit=min(max(limit, 1), 500))


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
