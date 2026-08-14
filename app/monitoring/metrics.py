"""Observability metrics via Pydantic Logfire (charts live in the Logfire UI)."""

from __future__ import annotations

import logfire

_requests = logfire.metric_counter("velov.requests")
_latency_retrieval = logfire.metric_histogram("velov.latency.retrieval_ms", unit="ms")
_latency_llm = logfire.metric_histogram("velov.latency.llm_ms", unit="ms")
_latency_total = logfire.metric_histogram("velov.latency.total_ms", unit="ms")
_tokens = logfire.metric_counter("velov.tokens")
_errors = logfire.metric_counter("velov.errors")
_feedback = logfire.metric_counter("velov.feedback")


def record_request(
    intent: str,
    retrieval_mode: str,
    *,
    latency_retrieval_ms: float,
    latency_llm_ms: float,
    latency_total_ms: float,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> None:
    attrs = {"intent": intent, "retrieval_mode": retrieval_mode}
    _requests.add(1, attributes=attrs)
    _latency_retrieval.record(latency_retrieval_ms, attributes=attrs)
    _latency_llm.record(latency_llm_ms, attributes=attrs)
    _latency_total.record(latency_total_ms, attributes=attrs)
    _tokens.add(total_tokens, attributes={**attrs, "kind": "total"})
    _tokens.add(prompt_tokens, attributes={**attrs, "kind": "prompt"})
    _tokens.add(completion_tokens, attributes={**attrs, "kind": "completion"})


def record_error() -> None:
    _errors.add(1)


def record_feedback(rating: int, conversation_id: str | None = None, comment: str | None = None) -> None:
    _feedback.add(1, attributes={"rating": "up" if rating > 0 else "down"})
    logfire.info("feedback", rating=rating, conversation_id=conversation_id, comment=comment)
