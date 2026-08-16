"""Ground-truth generation: LLM writes questions from FAQ docs (llm-zoomcamp 01-data-gen)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import cast

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from app.rag.llm import get_model

faq_file = Path("data/faq/faq.json")
ground_truth_file = Path("data/faq/ground_truth.json")

DATA_GEN_INSTRUCTIONS = """
You emulate a user who's interested in Velo'v, Lyon's bike-sharing service.
Formulate 5 questions this user might ask based on a FAQ record. The record
should contain the answer to the questions, and the questions should be complete and not too short.
If possible, use as few words as possible from the record.

The output should resemble how people ask questions on the internet. Not too formal, not too short, not too long.
""".strip()


class Questions(BaseModel):
    questions: list[str] = Field(description="5 questions the user might ask")


_gen_agent = Agent(get_model(), instructions=DATA_GEN_INSTRUCTIONS, output_type=Questions)


def generate_ground_truth(doc: dict) -> list[dict]:
    output = cast(Questions, _gen_agent.run_sync(json.dumps(doc, ensure_ascii=False)).output)
    return [{"question": q, "document": doc["id"]} for q in output.questions]


def main() -> None:
    faq = json.loads(faq_file.read_text())
    records: list[dict] = []

    for i, doc in enumerate(faq, 1):
        records.extend(generate_ground_truth(doc))
        print(f"[{i}/{len(faq)}] {doc['id']}")
        time.sleep(1)  # to avoid rate limit

    ground_truth_file.write_text(json.dumps(records, ensure_ascii=False, indent=2))
    print(f"wrote {len(records)} records to {ground_truth_file}")


if __name__ == "__main__":
    main()
