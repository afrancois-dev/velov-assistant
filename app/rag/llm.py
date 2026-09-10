"""LLM model (OpenCode Zen — OpenAI-compatible) and query rewriting via pydantic-ai."""

from __future__ import annotations

import uuid
from typing import cast

import httpx
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import settings

_IS_OPENCODE_GO = "/zen/go/" in settings.openai_base_url.lower()
_OPENCODE_SESSION_ID = uuid.uuid4().hex
_OPENCODE_HTTP_CLIENT = (
    httpx.AsyncClient(
        headers={
            "User-Agent": "velov-assistant/1.0",
            "x-opencode-session": _OPENCODE_SESSION_ID,
        }
    )
    if _IS_OPENCODE_GO
    else None
)


def get_model() -> OpenAIChatModel:
    if _OPENCODE_HTTP_CLIENT is not None:
        provider = OpenAIProvider(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            http_client=_OPENCODE_HTTP_CLIENT,
        )
    else:
        provider = OpenAIProvider(base_url=settings.openai_base_url, api_key=settings.openai_api_key)
    return OpenAIChatModel(
        settings.llm_model,
        provider=provider,
    )


_REWRITE_SYSTEM = (
    "You are a query-rewriting assistant for a bike-sharing FAQ search engine. "
    "Rewrite the user's question into 1 to 3 standalone retrieval queries that capture "
    "the user's intent, expand acronyms/terms and disambiguate. "
    "Return only the list of rewritten queries."
)

_rewrite_agent = Agent(get_model(), instructions=_REWRITE_SYSTEM, output_type=list[str])


def rewrite_query(query: str, n_variants: int = 3) -> list[str]:
    """Expand a raw user question into retrieval variants via the LLM (rewrite sub-agent)."""
    if not settings.openai_api_key:
        return [query]
    variants = [v for v in cast(list[str], _rewrite_agent.run_sync(query).output) if v]
    return variants[:n_variants] or [query]
