"""Application configuration via pydantic-settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM (OpenCode Zen — OpenAI-compatible)
    openai_api_key: str = ""
    openai_base_url: str = "https://opencode.ai/zen/v1/"
    llm_model: str = "gpt-4o-mini"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_embedding_model: str = "BAAI/bge-small-en-v1.5"
    qdrant_collection: str = "velov_faq"

    # Grand Lyon API
    grandlyon_stations_url: str = "https://data.grandlyon.com/fr/datapusher/ws/rdata/jcd_jcdecaux.jcdvelov/all.json"
    grandlyon_timeseries_url: str = "https://data.grandlyon.com/fr/datapusher/ws/timeseries/jcd_jcdecaux.historiquevelov/all.json"

    # PostgreSQL (metrics/feedback for Grafana)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "velov"
    postgres_user: str = "velov"
    postgres_password: str = "velov"

    # Observability
    logfire_token: str | None = None

    # Re-ranker
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
