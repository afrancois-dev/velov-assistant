"""Metrics recorder — persists request/feedback events to Postgres for Grafana."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

_engine = create_engine(settings.postgres_dsn, pool_pre_ping=True)
_Session = sessionmaker(bind=_engine)


class Base(DeclarativeBase):
    pass


class RequestEvent(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True)
    ts = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    conversation_id = Column(String)
    intent = Column(String)
    retrieval_mode = Column(String)
    latency_retrieval_ms = Column(Float, default=0.0)
    latency_llm_ms = Column(Float, default=0.0)
    latency_total_ms = Column(Float, default=0.0)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    error = Column(String, nullable=True)


class FeedbackEvent(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True)
    ts = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    conversation_id = Column(String)
    rating = Column(Integer)
    comment = Column(Text, nullable=True)


def _write(event) -> None:
    try:
        with _Session() as s:
            s.add(event)
            s.commit()
    except Exception:
        pass


def init_db() -> None:
    try:
        Base.metadata.create_all(_engine)
    except Exception:
        pass


def record_request(**kwargs) -> None:
    _write(RequestEvent(**kwargs))


def record_feedback(**kwargs) -> None:
    _write(FeedbackEvent(**kwargs))
