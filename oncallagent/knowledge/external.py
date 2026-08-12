from __future__ import annotations

from typing import Protocol

from oncallagent.knowledge.embedding import EmbeddingService
from oncallagent.knowledge.indexing import VectorPoint, build_vector_points, split_markdown_by_h1


class VectorStore(Protocol):
    async def upsert_points(self, points: list[VectorPoint]) -> None:
        pass


class ExternalKnowledgeIndexer:
    def __init__(self, *, embedder: EmbeddingService, vector_store: VectorStore) -> None:
        self.embedder = embedder
        self.vector_store = vector_store

    async def index_markdown(self, markdown: str, *, source: str | None = None) -> None:
        chunks = split_markdown_by_h1(markdown)
        points = await build_vector_points(chunks, self.embedder)
        if not points:
            return
        if source is not None:
            points = [
                VectorPoint(
                    id=point.id,
                    vector=point.vector,
                    payload={**point.payload, "source": source},
                )
                for point in points
            ]
        await self.vector_store.upsert_points(points)
