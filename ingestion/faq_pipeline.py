"""dlt pipeline: scrape the Velo'v FAQ, chunk it and load it (embedded) into Qdrant.

The FAQ is a JS SPA (rendered client-side from the auth-gated Cyclocity API), so a
headless browser (Playwright) is used to render it and extract question/answer pairs.
On success the scraped data is dumped to `data/faq/faq.json`; on failure (no browser,
offline, changed DOM) that file is used as a reproducible fallback.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import dlt
from dlt.destinations.adapters import qdrant_adapter

FAQ_URL = "https://velov.grandlyon.com/en/tutorial/groups?tab=FAQ"
FALLBACK_FILE = Path(__file__).resolve().parents[1] / "data" / "faq" / "faq.json"


def _scrape_live() -> list[dict]:
    from playwright.sync_api import sync_playwright

    entries: list[dict] = []
    with sync_playwright() as p:
        page = p.chromium.launch(headless=True).new_page()
        page.goto(FAQ_URL, wait_until="networkidle", timeout=60_000)
        page.wait_for_timeout(1500)

        # each topic is a `.container` section with an <h2> header; questions live in
        # `.line.clickable` rows whose answer (`div[body]`) renders on click.
        sections = page.locator('[data-test-id="faq-list"] .container')
        for si in range(sections.count()):
            section = sections.nth(si)
            topic = section.locator("h2").inner_text().strip()
            lines = section.locator(".line.clickable")
            for li in range(lines.count()):
                line = lines.nth(li)
                if not (question := line.locator('[data-test-id="faq-question"]').inner_text().strip()):
                    continue
                line.locator('[data-test-id="faq-question"]').click()
                page.wait_for_timeout(300)
                entries.append(
                    {
                        "id": f"faq-{re.sub(r'[^a-z0-9]+', '-', question.lower()).strip('-')}",
                        "topic": topic,
                        "question": question,
                        "answer": line.locator("div[body]").inner_text().strip(),
                    }
                )
    return entries


def _dump(entries: list[dict]) -> None:
    FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    FALLBACK_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=2))


def _scrape_faq() -> list[dict]:
    try:
        entries = _scrape_live()
    except Exception:
        return json.loads(FALLBACK_FILE.read_text())
    if entries:
        _dump(entries)
        return entries
    return json.loads(FALLBACK_FILE.read_text())


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
