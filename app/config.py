"""Application configuration via pydantic-settings."""

from __future__ import annotations

import os

from pydantic_settings import BaseSettings, SettingsConfigDict

_APP_ENV = os.environ.get("APP_ENV", "local")
_ENV_FILE = ".env.dev" if _APP_ENV == "dev" else ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    # Runtime environment: "local" (web chat + local Qdrant) | "dev" (FastAPI streaming + remote Qdrant).
    app_env: str = _APP_ENV

    # LLM (OpenCode Zen — OpenAI-compatible)
    openai_api_key: str = ""
    openai_base_url: str = "https://opencode.ai/zen/v1/"
    llm_model: str = "deepseek-v4-flash-free"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_embedding_model: str = "BAAI/bge-small-en-v1.5"
    qdrant_collection: str = "velov_faq"

    # Grand Lyon API
    grandlyon_stations_url: str = "https://data.grandlyon.com/fr/datapusher/ws/rdata/jcd_jcdecaux.jcdvelov/all.json"
    photon_geocode_url: str = "https://download.data.grandlyon.com/geocoding/photon-bal/api"

    # Re-ranker
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Observability
    logfire_token: str | None = None


settings = Settings()
