from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class AlertRecord(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    transaction_id: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    risk_score: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    decision: Mapped[bool] = mapped_column(Boolean)
    model_version: Mapped[str] = mapped_column(String(64))
    reason_codes: Mapped[list[str]] = mapped_column(JSON)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    analyst_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    analyst_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)


def create_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    url = database_url or os.getenv("AEGIS_DATABASE_URL", "sqlite:///./aegis_alerts.db")
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def save_alert(session_factory: sessionmaker[Session], record: dict[str, Any]) -> None:
    with session_factory.begin() as session:
        session.add(AlertRecord(**record))


def add_feedback(
    session_factory: sessionmaker[Session],
    alert_id: str,
    outcome: str,
    notes: str | None,
) -> bool:
    with session_factory.begin() as session:
        alert = session.query(AlertRecord).filter(AlertRecord.alert_id == alert_id).one_or_none()
        if alert is None:
            return False
        alert.analyst_outcome = outcome
        alert.analyst_notes = notes
        return True


def recent_alerts(session_factory: sessionmaker[Session], limit: int = 100) -> list[dict[str, Any]]:
    with session_factory() as session:
        records = session.query(AlertRecord).order_by(AlertRecord.created_at.desc()).limit(limit).all()
        return [
            {
                "alert_id": row.alert_id,
                "transaction_id": row.transaction_id,
                "created_at": row.created_at.isoformat(),
                "risk_score": row.risk_score,
                "decision": row.decision,
                "reason_codes": row.reason_codes,
                "analyst_outcome": row.analyst_outcome,
            }
            for row in records
        ]
