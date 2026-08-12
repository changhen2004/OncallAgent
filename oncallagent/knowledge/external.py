from __future__ import annotations

from typing import Protocol

from oncallagent.knowledge.embedding import EmbeddingService
from oncallagent.knowledge.indexing import (
    VectorPoint,
    build_vector_points,
    extract_runbook_metadata,
    split_markdown,
)


class VectorStore(Protocol):
    async def upsert_points(self, points: list[VectorPoint]) -> None:
        pass


class ExternalKnowledgeIndexer:
    def __init__(
        self,
        *,
        embedder: EmbeddingService,
        vector_store: VectorStore,
        max_chunk_chars: int = 1500,
        overlap_chars: int = 100,
    ) -> None:
        self.embedder = embedder
        self.vector_store = vector_store
        self.max_chunk_chars = max_chunk_chars
        self.overlap_chars = overlap_chars

    async def index_markdown(self, markdown: str, *, source: str | None = None) -> None:
        chunks = split_markdown(
            markdown,
            max_chunk_chars=self.max_chunk_chars,
            overlap_chars=self.overlap_chars,
        )
        points = await build_vector_points(chunks, self.embedder)
        if not points:
            return
        metadata = extract_runbook_metadata(markdown)
        enriched: list[VectorPoint] = []
        for point in points:
            payload = dict(point.payload)
            if source is not None:
                payload["source"] = source
            if metadata["alertname"]:
                payload["alertname"] = metadata["alertname"]
            if metadata["metrics"]:
                payload["metrics"] = metadata["metrics"]
            enriched.append(VectorPoint(id=point.id, vector=point.vector, payload=payload))
        await self.vector_store.upsert_points(enriched)
