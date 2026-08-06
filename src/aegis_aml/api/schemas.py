from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TransactionRequest(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    from_bank: str = Field(min_length=1, max_length=64)
    from_account: str = Field(min_length=1, max_length=128)
    to_bank: str = Field(min_length=1, max_length=64)
    to_account: str = Field(min_length=1, max_length=128)
    amount_received: float = Field(ge=0)
    receiving_currency: str = Field(min_length=3, max_length=16)
    amount_paid: float = Field(ge=0)
    payment_currency: str = Field(min_length=3, max_length=16)
    payment_format: str = Field(min_length=1, max_length=64)

    @field_validator("receiving_currency", "payment_currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class ScoreResponse(BaseModel):
    transaction_id: str
    alert_id: str | None
    risk_score: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    decision: Literal["alert", "allow"]
    reason_codes: list[str]
    model_version: str


class FeedbackRequest(BaseModel):
    outcome: Literal["confirmed_laundering", "false_positive", "needs_review"]
    notes: str | None = Field(default=None, max_length=2000)


class HealthResponse(BaseModel):
    status: str
    model_ready: bool
    model_version: str | None = None
