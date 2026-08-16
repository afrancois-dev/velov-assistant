"""dlt pipeline: fetch the Velo'v FAQ from the Cyclocity API, chunk it and load it (embedded) into Qdrant.

The FAQ is served by the Cyclocity backend (api.cyclocity.fr) — the same API the
velov.grandlyon.com SPA calls client-side. Access uses an anonymous client-token exchange:
a public code/key pair (shipped in the SPA bundle) is posted to
`/auth/environments/PRD/client_tokens` to obtain a short-lived access token, which then
authorizes a `POST /contracts/lyon/faqs/search`. Each Q/A pair is flattened into one
self-contained chunk, then embedded by the Qdrant destination (`qdrant_adapter(embed="content")`).

The client key is a public constant with an env override (`SOURCES__VELOV_FAQ__CLIENT_KEY`,
optionally set in `.env` via `load_dotenv`); everything else is hardcoded (public, shipped in the
SPA bundle). On failure (offline, changed API) the cached `data/faq/faq.json` is used as a
reproducible fallback, and refreshed after every successful live fetch.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Iterator

import dlt
from dlt.destinations.adapters import qdrant_adapter
from dlt.sources.helpers.rest_client.auth import AuthConfigBase
from dlt.sources.rest_api import rest_api_resources
from dotenv import load_dotenv
from requests import PreparedRequest

load_dotenv()

logger = logging.getLogger(__name__)

# public topic-code -> human label map (stable across the Cyclocity API).
TOPICS = {"ABO": "Subscriptions", "RIDE": "Journeys", "PAY": "Payments"}

# public cyclocity API details (shipped in the velov.grandlyon.com SPA bundle).
BASE_URL = "https://api.cyclocity.fr"
TOKEN_URL = "https://api.cyclocity.fr/auth/environments/PRD/client_tokens"
CLIENT_CODE = "vls.web.lyon:PRD"
LANGUAGE = "en"
# public client key (not a secret). override via SOURCES__VELOV_FAQ__CLIENT_KEY (e.g. .env).
CLIENT_KEY = "c3d9f5c22a9157a7cc7fe0e38269573bdd2f13ec48f867360ecdcbd35b196f87"
# resolved against the repo root so the pipeline works from any cwd.
FALLBACK_FILE = Path(__file__).resolve().parent.parent / "data" / "faq" / "faq.json"


class CyclocityClientTokenAuth(AuthConfigBase):
    """Exchange a public client code/key for a short-lived `Taknv1` access token.

    dlt's RESTClient calls this on the first request; the token is cached for the
    lifetime of the run (the FAQ endpoint is queried once per load). Fully
    instantiated with explicit values, so it is marked resolved to skip dlt's
    config resolution.
    """

    __is_resolved__ = True

    def __init__(self, token_url: str, client_code: str, client_key: str) -> None:
        super().__init__()
        self.token_url = token_url
        self.client_code = client_code
        self.client_key = client_key
        self._access_token: str | None = None

    def __call__(self, request: PreparedRequest) -> PreparedRequest:  # ty: ignore[invalid-method-override]
        if self._access_token is None:
            self._access_token = self._fetch_token()
        request.headers["Authorization"] = f"Taknv1 {self._access_token}"
        return request

    def _fetch_token(self) -> str:
        from dlt.sources.helpers import requests

        response = requests.post(
            self.token_url,
            json={"code": self.client_code, "key": self.client_key},
        )
        response.raise_for_status()
        return str(response.json()["accessToken"])


def _entry(topic: str, question: str, answer: str) -> dict[str, Any]:
    return {
        "id": f"faq-{re.sub(r'[^a-z0-9]+', '-', question.lower()).strip('-')}",
        "topic": topic,
        "question": question,
        "answer": answer,
        "content": "\n".join(filter(None, (topic, question, answer))),
    }


def _flatten_group(group: dict[str, Any], sink: list[dict[str, Any]] | None = None) -> Iterator[dict[str, Any]]:
    """Flatten one API group (`{topicCode, contents[]}`) into per-Q/A records."""
    topic = TOPICS.get(group.get("topicCode", ""), group.get("topicCode"))
    entries = [_entry(topic, c.get("question", "").strip(), c.get("response", "").strip()) for c in group.get("contents", [])]
    if sink is not None:
        sink.extend(entries)
    yield from entries


@dlt.source(name="velov_faq")
def faq_source(sink: list[dict[str, Any]] | None = None) -> Any:
    """Load the Velo'v FAQ from the Cyclocity API.

    Args:
        sink: Optional collector of flattened records, used to refresh the fallback cache.
    """
    yield from rest_api_resources(
        {
            "client": {
                "base_url": BASE_URL,
                "auth": CyclocityClientTokenAuth(TOKEN_URL, CLIENT_CODE, CLIENT_KEY),
            },
            "resources": [
                {
                    "name": "faq",
                    "primary_key": "id",
                    "write_disposition": "merge",
                    "endpoint": {
                        "path": "contracts/lyon/faqs/search",
                        "method": "POST",
                        "json": {"language": LANGUAGE},
                        "paginator": {"type": "single_page"},
                    },
                    "processing_steps": [{"yield_map": lambda g: _flatten_group(g, sink)}],
                },
            ],
        }
    )


@dlt.resource(name="faq", primary_key="id", write_disposition="replace")
def faq_from_file(path: str) -> Iterator[dict[str, Any]]:
    """Yield cached FAQ entries from a JSON file (reproducible fallback)."""
    yield from (
        _entry(e.get("topic", ""), e.get("question", ""), e.get("answer", "")) for e in json.loads(Path(path).read_text())
    )


def _refresh_cache(entries: list[dict[str, Any]], path: Path) -> None:
    if not entries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2))
    logger.info("refreshed FAQ fallback cache: %s (%d entries)", path, len(entries))


def run() -> None:
    """Run the FAQ ingestion pipeline into Qdrant, with a cached-file fallback."""
    pipeline = dlt.pipeline(pipeline_name="velov_faq", destination="qdrant", dataset_name="velov")

    sink: list[dict[str, Any]] = []
    try:
        info = pipeline.run(qdrant_adapter(faq_source(sink=sink), embed="content"))
    except Exception as exc:  # offline / changed API -> reproducible fallback
        logger.warning("live FAQ fetch failed (%s); using cached %s", exc, FALLBACK_FILE)
        info = pipeline.run(qdrant_adapter(faq_from_file(str(FALLBACK_FILE)), embed="content"))
    else:
        _refresh_cache(sink, FALLBACK_FILE)

    print(info)


if __name__ == "__main__":
    run()
