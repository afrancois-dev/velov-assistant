"""FastAPI application: /chat (RAG + function calling) and /feedback."""

from __future__ import annotations

import json
import time

import logfire
from fastapi import FastAPI

from app.config import settings
from app.monitoring import metrics
from app.monitoring.logfire_setup import configure_logfire, instrument
from app.rag import retriever
from app.rag.llm import get_client, rewrite_query
from app.schemas import ChatRequest, ChatResponse, FeedbackRequest, Source
from app.tools.stations import TOOL_IMPL, TOOL_SCHEMAS

configure_logfire()

app = FastAPI(title="Velo'v Assistant")
instrument(app)


_RAG_SYSTEM = (
    "You are a helpful assistant for Velo'v, Lyon's bike-sharing service. "
    "Answer policy/pricing/rules questions using ONLY the provided FAQ context. "
    "For real-time station availability, call the available functions. "
    "If neither the context nor the tools can answer, say you don't know."
)


def _retrieve_context(query: str) -> list[Source]:
    hits: dict = {}
    for variant in rewrite_query(query):
        hits.update((h["id"], h) for h in retriever.retrieve(variant, mode="hybrid", top_k=5))
    top = sorted(hits.values(), key=lambda h: h.get("score", 0.0), reverse=True)[:5]
    return [Source(topic=s.get("topic"), question=s.get("question"), answer=s.get("answer"), score=s.get("score")) for s in top]


def _context_block(sources: list[Source]) -> str:
    return "\n\n".join(f"[{i}] Q: {s.question}\nA: {s.answer}" for i, s in enumerate(sources, 1))


@logfire.instrument("chat", extract_args=True)
def _run_chat(message: str) -> tuple[str, str, list[Source], list[str], dict]:
    started = time.perf_counter()

    t0 = time.perf_counter()
    sources = _retrieve_context(message)
    latency_retrieval = (time.perf_counter() - t0) * 1000

    messages = [
        {"role": "system", "content": _RAG_SYSTEM},
        {"role": "system", "content": f"FAQ context:\n{_context_block(sources)}"},
        {"role": "user", "content": message},
    ]

    t0 = time.perf_counter()
    resp = get_client().chat.completions.create(
        model=settings.llm_model, messages=messages, tools=TOOL_SCHEMAS, tool_choice="auto"
    )
    first = resp.choices[0].message
    tools_used: list[str] = []

    while first.tool_calls:
        for call in first.tool_calls:
            if not (fn := TOOL_IMPL.get(call.function.name)):
                continue
            args = json.loads(call.function.arguments or "{}")
            with logfire.span(f"tool:{call.function.name}") as span:
                result = fn(**args)
                span.set_attribute("args", args)
            tools_used.append(call.function.name)
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, ensure_ascii=False, default=str)}
            )
        resp = get_client().chat.completions.create(model=settings.llm_model, messages=messages, tools=TOOL_SCHEMAS)
        first = resp.choices[0].message

    latency_llm = (time.perf_counter() - t0) * 1000
    usage = resp.usage

    meta = {
        "latency_retrieval_ms": round(latency_retrieval, 2),
        "latency_llm_ms": round(latency_llm, 2),
        "latency_total_ms": round((time.perf_counter() - started) * 1000, 2),
        **{k: getattr(usage, k, 0) for k in ("prompt_tokens", "completion_tokens", "total_tokens")},
    }
    return first.content or "", "tool" if tools_used else "rag", sources, tools_used, meta


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    try:
        answer, intent, sources, tools_used, meta = _run_chat(req.message)
    except Exception:
        metrics.record_error()
        raise
    metrics.record_request(intent=intent, retrieval_mode="hybrid", **meta)
    return ChatResponse(answer=answer, intent=intent, sources=sources, tools_used=tools_used)


@app.post("/feedback")
def feedback(req: FeedbackRequest) -> dict:
    metrics.record_feedback(rating=req.rating, conversation_id=req.conversation_id, comment=req.comment)
    return {"status": "ok"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
