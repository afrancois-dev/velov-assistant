"""dlt pipeline: fetch the Velo'v FAQ from the Cyclocity API, chunk it and load it (embedded) into Qdrant.

The FAQ is served by the Cyclocity backend — the same API the velov.grandlyon.com SPA
calls client-side. Access uses an anonymous client-token exchange: a public code/key pair
(shipped in the SPA bundle) is posted to /auth/environments/PRD/client_tokens to obtain a
short-lived access token, which then authorizes /contracts/lyon/faqs/search.
On success the fetched data is dumped to `data/faq/faq.json`; on failure (offline, changed
API) that file is used as a reproducible fallback.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import dlt
import httpx
from dlt.destinations.adapters import qdrant_adapter

CLIENT_TOKEN_URL = "https://api.cyclocity.fr/auth/environments/PRD/client_tokens"
FAQS_URL = "https://api.cyclocity.fr/contracts/lyon/faqs/search"
# public client code/key shipped in the velov.grandlyon.com SPA bundle (not a secret).
# Probably static per SPA release, not per session
# I should fetch the js bundle and parse it to get the latest code/key pair, but for a first version this is good enough
CLIENT_CODE = "vls.web.lyon:PRD"
CLIENT_KEY = "c3d9f5c22a9157a7cc7fe0e38269573bdd2f13ec48f867360ecdcbd35b196f87"
TOPICS = {"ABO": "Subscriptions", "RIDE": "Journeys", "PAY": "Payments"}

fallback_file = Path("data/faq/faq.json")


def _scrape_live() -> list[dict]:
    with httpx.Client(timeout=30.0, headers={"User-Agent": "velov-assistant/0.1"}) as client:
        token = (
            client.post(CLIENT_TOKEN_URL, json={"code": CLIENT_CODE, "key": CLIENT_KEY}).raise_for_status().json()["accessToken"]
        )
        groups = (
            client.post(FAQS_URL, json={"language": "en"}, headers={"Authorization": f"Taknv1 {token}"}).raise_for_status().json()
        )

    entries: list[dict] = []
    for group in groups:
        topic = TOPICS.get(group["topicCode"], group["topicCode"])
        for content in group["contents"]:
            question = content["question"].strip()
            entries.append(
                {
                    "id": f"faq-{re.sub(r'[^a-z0-9]+', '-', question.lower()).strip('-')}",
                    "topic": topic,
                    "question": question,
                    "answer": content["response"].strip(),
                }
            )
    return entries


def _dump(entries: list[dict]) -> None:
    fallback_file.parent.mkdir(parents=True, exist_ok=True)
    fallback_file.write_text(json.dumps(entries, ensure_ascii=False, indent=2))


def _scrape_faq() -> list[dict]:
    try:
        entries = _scrape_live()
    except Exception:
        return json.loads(fallback_file.read_text())
    if entries:
        _dump(entries)
        return entries
    return json.loads(fallback_file.read_text())


@dlt.resource(name="faq", primary_key="id", write_disposition="replace")
def faq_resource():
    """Yield one self-contained chunk per FAQ entry (embedded by the Qdrant destination)."""
    for i, e in enumerate(_scrape_faq()):
        content = "\n".join(filter(None, (e.get("topic"), e.get("question"), e.get("answer"))))
        yield {
            "id": e.get("id", f"faq-{i}"),
            "topic": e.get("topic"),
            "question": e.get("question"),
            "answer": e.get("answer"),
            "content": content,
        }


def run() -> None:
    """Run the FAQ ingestion pipeline into Qdrant."""
    pipeline = dlt.pipeline(pipeline_name="velov_faq", destination="qdrant", dataset_name="velov")
    print(pipeline.run(qdrant_adapter(faq_resource, embed="content")))


if __name__ == "__main__":
    run()
