"""LLM client (OpenCode Zen — OpenAI-compatible) and query rewriting."""

from __future__ import annotations

import json
from functools import lru_cache

from openai import OpenAI

from app.config import settings


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)


_REWRITE_SYSTEM = (
    "You are a query-rewriting assistant for a bike-sharing FAQ search engine. "
    "Rewrite the user's question into 1 to 3 standalone retrieval queries that capture "
    "the user's intent, expand acronyms/terms and disambiguate. "
    "Return a JSON array of strings only."
)


def rewrite_query(query: str, n_variants: int = 3) -> list[str]:
    """Expand a raw user question into retrieval variants via the LLM."""
    if not settings.openai_api_key:
        return [query]
    raw = (
        get_client()
        .chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "system", "content": _REWRITE_SYSTEM}, {"role": "user", "content": query}],
            temperature=0.2,
        )
        .choices[0]
        .message.content
    ) or "[]"
    try:
        variants = [v for v in json.loads(raw) if isinstance(v, str) and v]
    except json.JSONDecodeError:
        variants = [query]
    return variants[:n_variants] or [query]
