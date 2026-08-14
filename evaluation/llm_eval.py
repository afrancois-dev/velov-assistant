"""LLM evaluation: LLM-as-a-judge scoring of answers against a reference."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.rag.llm import get_client

GROUND_TRUTH = Path(__file__).resolve().parent / "data" / "llm_ground_truth.json"

_JUDGE_PROMPT = (
    "You are an evaluator. Rate how well the candidate answer answers the question "
    "relative to the reference answer. Return a single integer 1-5."
)


@lru_cache(maxsize=1)
def _load() -> list[dict]:
    return json.loads(GROUND_TRUTH.read_text())


def judge(question: str, reference: str, candidate: str) -> int:
    raw = (
        get_client()
        .chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _JUDGE_PROMPT},
                {"role": "user", "content": f"Question: {question}\nReference: {reference}\nCandidate: {candidate}"},
            ],
            temperature=0.0,
        )
        .choices[0]
        .message.content
    ) or "3"
    try:
        return int(raw.strip())
    except ValueError:
        return 3


def main() -> None:
    items = _load()
    print(f"average judge score: {sum(judge(**i) for i in items) / len(items):.2f}")


if __name__ == "__main__":
    main()
