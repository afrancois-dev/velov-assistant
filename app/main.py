"""FastAPI application: /chat (RAG + function calling) and /feedback."""

from __future__ import annotations

import time

import logfire
from fastapi import FastAPI
from pydantic_ai import Agent
from pydantic_ai.messages import ToolReturnPart

from app.config import settings
from app.monitoring import metrics

from app.rag import retriever
from app.rag.llm import get_model, rewrite_query
from app.schemas import ChatRequest, ChatResponse, FeedbackRequest, Source
from app.tools.stations import find_nearest_bikes, get_station_availability


app = FastAPI(title="Velo'v Assistant")
logfire.configure(token=settings.logfire_token)


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


def _run_chat(message: str) -> tuple[str, str, list[Source], list[str], dict]:
    started = time.perf_counter()

    t0 = time.perf_counter()
    sources = _retrieve_context(message)
    latency_retrieval = (time.perf_counter() - t0) * 1000

    instructions = f"""{_RAG_SYSTEM}
        FAQ context:
        {_context_block(sources)}"""

    agent = Agent(  # type: ignore
        get_model(),
        instructions=instructions,
        tools=[get_station_availability, find_nearest_bikes],
    )

    t0 = time.perf_counter()
    result = agent.run_sync(message)
    latency_llm = (time.perf_counter() - t0) * 1000

    tools_used = [part.tool_name for msg in result.all_messages() for part in msg.parts if isinstance(part, ToolReturnPart)]
    usage = result.usage

    meta = {
        "latency_retrieval_ms": round(latency_retrieval, 2),
        "latency_llm_ms": round(latency_llm, 2),
        "latency_total_ms": round((time.perf_counter() - started) * 1000, 2),
        "prompt_tokens": usage.input_tokens,
        "completion_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
    }
    return result.output, "tool" if tools_used else "rag", sources, tools_used, meta


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
