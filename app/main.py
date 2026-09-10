"""Velo'v assistant: pydantic-ai agent with two serving modes.

- ``local`` (default): web chat UI via ``agent.to_web()``.
- ``dev``: FastAPI endpoint streaming UI events (Vercel AI Data Stream protocol).
"""

from __future__ import annotations

from typing import Annotated, Any

import logfire
from fastapi import FastAPI
from pydantic import Field
from pydantic_ai import Agent
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.rag import retriever
from app.rag.llm import get_model, rewrite_query
from app.tools.stations import get_velov_info

_SYSTEM = (
    "You are a helpful assistant for Velo'v, Lyon's bike-sharing service. "
    "Answer policy/pricing/rules questions using the search_faq tool. "
    "For real-time station availability (bikes/free stands, nearest station), use get_velov_info. "
    "If neither the FAQ nor get_velov_info can answer, say you don't know."
)


def _is_weak(hits: list[dict[str, Any]]) -> bool:
    return not hits or max((h.get("rerank_score", 0.0) for h in hits), default=0.0) < 0.0


def _format(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"topic": h.get("topic"), "question": h.get("question"), "answer": h.get("answer"), "score": h.get("score")} for h in hits
    ]


def search_faq(
    query: Annotated[str, Field(description="The user's question, phrased for FAQ retrieval.")],
    top_k: Annotated[int, Field(description="Maximum number of FAQ entries to return.")] = 3,
) -> list[dict[str, Any]]:
    """Search the Velo'v FAQ (hybrid dense + BM25, reranked).

    Runs a first hybrid retrieval; if the result is weak, a query-rewriting
    sub-agent expands the question into variants which are re-retrieved and merged.
    """
    first = retriever.retrieve(query, mode="hybrid", top_k=top_k)
    if not _is_weak(first):
        return _format(first)

    merged = {h["id"]: h for h in first}
    for variant in rewrite_query(query):
        for h in retriever.retrieve(variant, mode="hybrid", top_k=top_k):
            merged.setdefault(h["id"], h)
    top = sorted(merged.values(), key=lambda h: h.get("rerank_score", 0.0), reverse=True)[:top_k]
    return _format(top)


agent = Agent(  # type: ignore
    get_model(),
    instructions=_SYSTEM,
    tools=[search_faq, get_velov_info],
)

logfire.configure(token=settings.logfire_token, service_name="velov-assistant")
logfire.instrument_system_metrics()
logfire.instrument_pydantic_ai()

# Local: web chat UI.
webchat_app = agent.to_web()


def _build_fastapi_app() -> FastAPI:
    app = FastAPI(title="Velo'v Assistant")

    @app.post("/chat")
    async def chat(request: Request) -> Response:
        return await VercelAIAdapter.dispatch_request(request, agent=agent)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


# Dev: FastAPI + UI event stream (Vercel AI Data Stream protocol).
fastapi_app = _build_fastapi_app()

app = fastapi_app if settings.app_env == "dev" else webchat_app

if isinstance(app, FastAPI):
    logfire.instrument_fastapi(app)
else:
    logfire.instrument_starlette(app)


def _run_chat(message: str) -> str:
    """Run the agent once and return its answer."""
    return agent.run_sync(message).output


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
