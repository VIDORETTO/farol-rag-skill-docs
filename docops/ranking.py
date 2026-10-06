"""Rank evidence from several packages on one, package-independent scale (seam S10).

Each package's index scores hits against its own statistics: BM25 uses the
package's IDF and the fused score is a reciprocal rank, so the first hit of an
irrelevant package ties with the first hit of the right one. A ``Ranker``
rescores the pooled candidates together. The default ranker needs no model:
BM25 computed over the pool itself, fused (reciprocal rank) with the cosine of
the query and each candidate's best window when every package shares one
embedding model. ``docops.backends.semantic`` cross-encoders plug into the same
protocol (TK-204).
"""

from __future__ import annotations

import math
import unicodedata
from typing import Any, Mapping, Protocol, Sequence

from .backends.local_fts import _STOPWORDS, _TOKEN

_K1 = 1.2
_RRF_K = 60
_B = 0.75


class Ranker(Protocol):
    def rank(self, query: str, candidates: list[dict[str, Any]]) -> list[float]: ...


def _terms(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    return [token for token in _TOKEN.findall(folded) if token.strip("_")]


def _content(terms: list[str]) -> list[str]:
    content = [term for term in terms if term not in _STOPWORDS]
    return content or terms


def pooled_bm25(query: str, texts: Sequence[str]) -> list[float]:
    """BM25 of ``query`` against ``texts`` using the statistics of ``texts`` alone."""

    documents = [_terms(text) for text in texts]
    if not documents:
        return []
    average = sum(len(terms) for terms in documents) / len(documents) or 1.0
    frequency: dict[str, int] = {}
    for terms in documents:
        for term in set(terms):
            frequency[term] = frequency.get(term, 0) + 1
    query_terms = set(_content(_terms(query)))
    scores = []
    for terms in documents:
        counts: dict[str, int] = {}
        for term in terms:
            counts[term] = counts.get(term, 0) + 1
        score = 0.0
        for term in query_terms:
            tf = counts.get(term, 0)
            if not tf:
                continue
            idf = math.log(1 + (len(documents) - frequency[term] + 0.5) / (frequency[term] + 0.5))
            score += idf * tf * (_K1 + 1) / (tf + _K1 * (1 - _B + _B * len(terms) / average))
        scores.append(score)
    return scores


def reciprocal_rank_fusion(*score_lists: Sequence[float], k: int = _RRF_K) -> list[float]:
    fused = [0.0] * (len(score_lists[0]) if score_lists else 0)
    for scores in score_lists:
        order = sorted(range(len(scores)), key=lambda index: -scores[index])
        for position, index in enumerate(order):
            if scores[index] > 0:
                fused[index] += 1.0 / (k + position + 1)
    return fused


class PooledRanker:
    """Default ranker: pooled BM25, fused with shared-model cosine when available."""

    def __init__(self, embedder: Any | None = None) -> None:
        self.embedder = embedder

    def rank(self, query: str, candidates: list[dict[str, Any]]) -> list[float]:
        """Scores for ``candidates``; each candidate's ``score`` is its package-local score."""

        texts = [_with_heading(candidate) for candidate in candidates]
        lexical = pooled_bm25(query, texts)
        if self.embedder is None:
            return lexical
        return reciprocal_rank_fusion(lexical, _cosines(self.embedder, query, candidates))


def merge_by_package(candidates: list[dict[str, Any]], scores: Sequence[float]) -> list[int]:
    """Interleave packages without reordering any package's own ranking.

    Each package already ordered its hits with its own index; global scores
    only decide which package supplies the next hit (the best of the current
    heads), so a package's recall is never lost to the merge.
    """

    queues: dict[str, list[int]] = {}
    for index in sorted(range(len(candidates)), key=lambda item: -float(candidates[item].get("score") or 0.0)):
        queues.setdefault(str(candidates[index].get("package") or ""), []).append(index)
    order: list[int] = []
    while any(queues.values()):
        heads = [(package, members[0]) for package, members in queues.items() if members]
        package, best = max(heads, key=lambda item: (scores[item[1]], -item[1]))
        order.append(best)
        queues[package].pop(0)
    return order


def _with_heading(candidate: Mapping[str, Any]) -> str:
    heading = " ".join(str(part) for part in candidate.get("heading_path") or [])
    return f"{heading}\n{candidate.get('text') or ''}"


def _cosines(embedder: Any, query: str, candidates: list[dict[str, Any]]) -> list[float]:
    import numpy as np

    from .backends.semantic import windows

    owners: list[int] = []
    chunks: list[str] = []
    for position, candidate in enumerate(candidates):
        for chunk in windows(str(candidate.get("text") or ""), " › ".join(candidate.get("heading_path") or [])):
            owners.append(position)
            chunks.append(chunk)
    if not chunks:
        return [0.0] * len(candidates)
    matrix = np.asarray(embedder.embed_documents(chunks), dtype=np.float32)
    matrix /= np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12)
    vector = np.asarray(embedder.embed_query(query), dtype=np.float32)
    vector /= max(float(np.linalg.norm(vector)), 1e-12)
    best = [0.0] * len(candidates)
    for owner, similarity in zip(owners, (matrix @ vector).tolist()):
        best[owner] = max(best[owner], similarity)
    return best


# -- Optional cross-encoder reranker (TK-204, D-301) -------------------------

# Licenses verified in fastembed 0.8.1's model list (specs/farol-3.1/decisions.md).
RERANKER_LICENSES = {
    "Xenova/ms-marco-MiniLM-L-6-v2": "apache-2.0",
    "Xenova/ms-marco-MiniLM-L-12-v2": "apache-2.0",
    "BAAI/bge-reranker-base": "mit",
    "jinaai/jina-reranker-v1-tiny-en": "apache-2.0",
    "jinaai/jina-reranker-v1-turbo-en": "apache-2.0",
    "jinaai/jina-reranker-v2-base-multilingual": "cc-by-nc-4.0",
}


class CrossEncoderRanker:
    """Local cross-encoder (fastembed, CPU): scores are comparable across packages."""

    global_order = True

    def __init__(self, model: str, cache_dir: str | None = None) -> None:
        import os
        from pathlib import Path

        from .backends.semantic import _quiet_native_stderr

        directory = Path(cache_dir or os.environ.get("FAROL_MODELS_DIR") or Path.home() / ".cache" / "farol" / "models")
        with _quiet_native_stderr():
            from fastembed.rerank.cross_encoder import TextCrossEncoder  # type: ignore[import-not-found]

            self._model = TextCrossEncoder(model, cache_dir=str(directory))
        self.name = model

    def rank(self, query: str, candidates: list[dict[str, Any]]) -> list[float]:
        texts = [_with_heading(candidate) for candidate in candidates]
        return [float(score) for score in self._model.rerank(query, texts, batch_size=16)]


def configured_reranker() -> str | None:
    import os

    return (os.environ.get("FAROL_RERANKER") or "").strip() or None


def load_reranker(model: str) -> tuple[Any | None, str | None]:
    """The configured reranker, or ``None`` and the reason it is unavailable."""

    try:
        return CrossEncoderRanker(model), None
    except Exception:
        return None, f"reranker_unavailable: {model} could not be loaded"
