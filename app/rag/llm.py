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

_STATION_REFORMULATE_SYSTEM = (
    "You normalize location intents for the Lyon Velo'v station network. "
    "Rewrite the user's location into 1 to 3 short station or landmark names. "
    "Preserve proper names, fix obvious spelling and punctuation variations, "
    "and do not invent addresses or coordinates. Return only the list of strings."
)

_station_reformulate_agent = Agent(get_model(), instructions=_STATION_REFORMULATE_SYSTEM, output_type=list[str])


def rewrite_query(query: str, n_variants: int = 3) -> list[str]:
    """Expand a raw user question into retrieval variants via the LLM (rewrite sub-agent)."""
    if not settings.openai_api_key:
        return [query]
    variants = [v for v in cast(list[str], _rewrite_agent.run_sync(query).output) if v]
    return variants[:n_variants] or [query]


def reformulate_station_query(query: str, n_variants: int = 3) -> list[str]:
    """Suggest corrected station/location names after deterministic matching fails."""
    if not settings.openai_api_key:
        return [query]
    try:
        output = cast(list[str], _station_reformulate_agent.run_sync(query).output)
    except Exception:
        return [query]
    variants = [v.strip() for v in output if v.strip()]
    return variants[:n_variants] or [query]
