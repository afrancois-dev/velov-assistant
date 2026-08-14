"""Pydantic Logfire setup — tracing for LLM, retrieval and tool calls."""

from __future__ import annotations

import logfire

from app.config import settings


def configure_logfire() -> None:
    logfire.configure(
        token=settings.logfire_token or None,
        service_name="velov-assistant",
        console=False,
        send_to_logfire=bool(settings.logfire_token),
    )


def instrument(app=None) -> None:
    """Instrument FastAPI, OpenAI and HTTP clients when logfire is enabled."""
    if not settings.logfire_token:
        return
    if app:
        logfire.instrument_fastapi(app)
    logfire.instrument_openai()
    logfire.instrument_httpx()
