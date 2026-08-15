"""Hybrid retriever: dense (Qdrant + fastembed) + sparse (BM25) fused with RRF, then rerank."""

from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import ScoredPoint

from app.config import settings

_TEXT_FIELD = "content"
_PAYLOAD_FIELDS = ("topic", "question", "answer", _TEXT_FIELD)
_TOKEN_RE = re.compile(r"\w+")


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


@lru_cache(maxsize=1)
def _dense_model():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=settings.qdrant_embedding_model)


def _vector_name(client: QdrantClient) -> str:
    vectors = client.get_collection(settings.qdrant_collection).config.params.vectors
    return next(iter(vectors), "") if isinstance(vectors, dict) else ""


def _embed(query: str) -> list[float]:
    return next(_dense_model().embed([query])).tolist()


def _doc_id(point: ScoredPoint) -> str:
    payload = point.payload or {}
    value = payload.get("id")
    if value is None:
        value = point.id
    return str(value)


def _to_hit(point: ScoredPoint) -> dict[str, Any]:
    payload = point.payload or {}
    return {"id": _doc_id(point), "score": point.score, **{f: payload.get(f) for f in _PAYLOAD_FIELDS}}


def search_dense(query: str, limit: int = 20) -> list[dict[str, Any]]:
    client = get_qdrant_client()
    return [
        _to_hit(p)
        for p in client.query_points(
            collection_name=settings.qdrant_collection,
            query=_embed(query),
            using=_vector_name(client),
            limit=limit,
            with_payload=True,
        ).points
    ]


def _corpus() -> list[dict]:
    client = get_qdrant_client()
    docs, offset = [], None
    while True:
        points, offset = client.scroll(
            settings.qdrant_collection, limit=256, offset=offset, with_payload=True, with_vectors=False
        )
        docs.extend({"id": _doc_id(p), **(p.payload or {})} for p in points)  # ty: ignore[invalid-argument-type]
        if offset is None:
            return docs


def _bm25_scores(query: str, k1: float = 1.5, b: float = 0.75) -> list[float]:
    tokens = [_TOKEN_RE.findall((d.get(_TEXT_FIELD) or "").lower()) for d in _corpus()]
    lengths = [len(t) for t in tokens]
    avgdl = sum(lengths) / len(lengths) if lengths else 1.0
    df = Counter(term for doc in tokens for term in set(doc))
    terms = _TOKEN_RE.findall(query.lower())
    idf = {t: math.log(1 + (len(tokens) - df[t] + 0.5) / (df[t] + 0.5)) for t in terms if df[t]}
    return [
        sum(idf[t] * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * length / avgdl)) for t in terms if t in idf)
        for tf, length in ((Counter(doc), length) for doc, length in zip(tokens, lengths))
    ]


def search_sparse(query: str, limit: int = 20) -> list[dict[str, Any]]:
    docs = _corpus()
    ranked = sorted(zip(docs, _bm25_scores(query)), key=lambda x: x[1], reverse=True)[:limit]
    return [{"id": d["id"], "score": s, **{f: d.get(f) for f in _PAYLOAD_FIELDS}} for d, s in ranked]


def _rrf(*rankings: list[dict[str, Any]], k: int = 60) -> dict[Any, float]:
    scores: dict[Any, float] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking):
            scores[hit["id"]] = scores.get(hit["id"], 0.0) + 1.0 / (k + rank + 1)
    return scores


def hybrid(query: str, limit: int = 20) -> list[dict[str, Any]]:
    dense, sparse = search_dense(query, limit), search_sparse(query, limit)
    fused = _rrf(dense, sparse)
    by_id = {h["id"]: h for h in [*sparse, *dense]}  # dense wins on id collisions
    return sorted(({**h, "score": fused[h["id"]]} for h in by_id.values()), key=lambda h: h["score"], reverse=True)[:limit]


class Reranker:
    """Cross-encoder re-ranker over candidate documents."""

    def __init__(self) -> None:
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(settings.rerank_model)

    def rerank(self, query: str, candidates: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        scores = self._model.predict([(query, c.get(_TEXT_FIELD) or "") for c in candidates])
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        return sorted(candidates, key=lambda c: c.get("rerank_score", 0.0), reverse=True)[:top_k]


def retrieve(query: str, mode: str = "hybrid", top_k: int = 5, rerank: bool = True) -> list[dict[str, Any]]:
    """Retrieve top documents for a query. mode: "dense" | "sparse" | "hybrid"."""
    candidates = {"dense": search_dense, "sparse": search_sparse}.get(mode, hybrid)(query, limit=20)
    if rerank and candidates:
        candidates = Reranker().rerank(query, candidates, top_k)
    return candidates[:top_k]
