"""Retrieval evaluation: compare dense / sparse / hybrid with Hit Rate and MRR."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.rag import retriever

GROUND_TRUTH = Path(__file__).resolve().parent / "data" / "ground_truth.json"


@lru_cache(maxsize=1)
def _load() -> list[dict]:
    return json.loads(GROUND_TRUTH.read_text())


def _hit_ids(item: dict, mode: str, top_k: int) -> set:
    return {r["id"] for r in retriever.retrieve(item["question"], mode=mode, top_k=top_k, rerank=False)}


def hit_rate(mode: str, top_k: int = 5) -> float:
    items = _load()
    return sum(i["document"] in _hit_ids(i, mode, top_k) for i in items) / len(items)


def mrr(mode: str, top_k: int = 5) -> float:
    items = _load()
    return sum(
        next(
            (
                1 / r
                for r, h in enumerate(retriever.retrieve(i["question"], mode=mode, top_k=top_k, rerank=False), 1)
                if h["id"] == i["document"]
            ),
            0.0,
        )
        for i in items
    ) / len(items)


def main() -> None:
    for mode in ("dense", "sparse", "hybrid"):
        print(f"{mode:8s} hit_rate@5={hit_rate(mode):.3f}  mrr@5={mrr(mode):.3f}")


if __name__ == "__main__":
    main()
