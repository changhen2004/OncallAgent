from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchResult:
    filename: str
    content: str
    score: float


class VectorSearch(Protocol):
    async def search(
        self,
        query: str,
        *,
        limit: int = 3,
        score_threshold: float = 0.5,
        payload_filter: dict | None = None,
    ) -> list[dict]:
        pass


def rrf_merge(
    lexical_results: list[SearchResult],
    vector_results: list[dict],
    *,
    k: int = 60,
    limit: int = 3,
) -> list[SearchResult]:
    """Merge lexical and vector results with Reciprocal Rank Fusion.

    ``vector_results`` items are payload dicts with ``content`` and optionally
    ``source`` (the source filename) and ``score``.  Chunks sharing the same
    source are deduplicated before ranking so each document contributes once.
    """
    if not vector_results:
        return lexical_results

    best_vector: dict[str, dict] = {}
    for item in vector_results:
        key = _result_key(item)
        if key not in best_vector or _score(item) > _score(best_vector[key]):
            best_vector[key] = item

    scores: dict[str, float] = defaultdict(float)
    for rank, result in enumerate(lexical_results):
        scores[result.filename] += 1.0 / (k + rank + 1)

    for rank, item in enumerate(best_vector.values()):
        key = _result_key(item)
        scores[key] += 1.0 / (k + rank + 1)

    content_by_key = {result.filename: result.content for result in lexical_results}
    for key, item in best_vector.items():
        content_by_key.setdefault(key, str(item.get("content", "")))

    merged_keys = sorted(scores, key=lambda key: (-scores[key], key))[:limit]
    return [
        SearchResult(filename=key, content=content_by_key[key], score=scores[key])
        for key in merged_keys
    ]


def _score(item: dict) -> float:
    try:
        return float(item.get("score", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _result_key(item: dict) -> str:
    source = item.get("source")
    if source:
        return str(source)
    content = str(item.get("content", ""))
    return f"chunk-{hash(content)}"
