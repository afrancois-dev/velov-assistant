"""Retrieval evaluation: compare dense / sparse / hybrid with Hit Rate and MRR."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from tqdm import tqdm

from app.rag import retriever

ground_truth_file = json.loads(Path("data/faq/ground_truth.json").read_text())


def _ranks(mode: str, top_k: int = 5) -> list[int | None]:
    """Return the rank of the target document for each item (None if not found)."""
    ranks: list[int | None] = []
    for item in tqdm(ground_truth_file, desc=f"{mode:8s}"):
        hits = [h["id"] for h in retriever.retrieve(item["question"], mode=mode, top_k=top_k, rerank=False)]
        ranks.append(next((r for r, hid in enumerate(hits, 1) if hid == item["document"]), None))
    return ranks


def main() -> None:
    for mode in ("dense", "sparse", "hybrid"):
        ranks = _ranks(mode)
        hit_rate = sum(r is not None for r in ranks) / len(ranks)
        mrr = sum(1 / r for r in ranks if r is not None) / len(ranks)
        print(f"{mode:8s} hit_rate@5={hit_rate:.3f}  mrr@5={mrr:.3f}")


if __name__ == "__main__":
    main()
