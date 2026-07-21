from __future__ import annotations

from typing import Protocol

from oncallagent.embedding import EmbeddingService
from oncallagent.indexing import VectorPoint, build_vector_points, split_markdown_by_h1


class VectorStore(Protocol):
    async def upsert_points(self, points: list[VectorPoint]) -> None:
        pass


class ExternalKnowledgeIndexer:
    def __init__(self, *, embedder: EmbeddingService, vector_store: VectorStore) -> None:
        self.embedder = embedder
        self.vector_store = vector_store

    async def index_markdown(self, markdown: str) -> None:
        chunks = split_markdown_by_h1(markdown)
        points = await build_vector_points(chunks, self.embedder)
        if points:
            await self.vector_store.upsert_points(points)
