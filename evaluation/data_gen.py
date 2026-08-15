"""Ground-truth generation: LLM writes questions from FAQ docs (llm-zoomcamp 01-data-gen)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.rag.llm import get_client

faq_file = Path("data/faq/faq.json")
ground_truth_file = Path("data/faq/ground_truth.json")

DATA_GEN_INSTRUCTIONS = """
You emulate a customer who's interested in Velo'v, Lyon's bike-sharing service.
Formulate 5 questions this customer might ask based on a FAQ record. The record
should contain the answer to the questions, and the questions should be complete and not too short.
If possible, use as few words as possible from the record.

The output should resemble how people ask questions on the internet. Not too formal, not too short, not too long.
""".strip()


class Questions(BaseModel):
    questions: list[str] = Field(description="5 questions the customer might ask")


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=60))
def _generate(doc: dict) -> Questions:
    content = (
        get_client()
        .chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": DATA_GEN_INSTRUCTIONS},
                {"role": "user", "content": json.dumps(doc, ensure_ascii=False)},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        .choices[0]
        .message.content
    )
    return Questions.model_validate(json.loads(content or "{}"))


def generate_ground_truth(doc: dict) -> list[dict]:
    questions = _generate(doc).questions
    return [{"question": q, "document": doc["id"]} for q in questions]


def main() -> None:
    faq = json.loads(faq_file.read_text())
    records: list[dict] = []
    for i, doc in enumerate(faq, 1):
        records.extend(generate_ground_truth(doc))
        print(f"[{i}/{len(faq)}] {doc['id']}")
        time.sleep(1)
    ground_truth_file.write_text(json.dumps(records, ensure_ascii=False, indent=2))
    print(f"wrote {len(records)} records to {ground_truth_file}")


if __name__ == "__main__":
    main()
