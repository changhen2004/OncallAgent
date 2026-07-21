import pytest

from oncallagent.external_indexer import ExternalKnowledgeIndexer
from oncallagent.indexing import VectorPoint


class FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class FakeVectorStore:
    def __init__(self) -> None:
        self.points: list[VectorPoint] = []

    async def upsert_points(self, points: list[VectorPoint]) -> None:
        self.points.extend(points)


@pytest.mark.anyio
async def test_external_indexer_splits_embeds_and_upserts_markdown() -> None:
    store = FakeVectorStore()
    indexer = ExternalKnowledgeIndexer(embedder=FakeEmbedder(), vector_store=store)

    await indexer.index_markdown("# Latency\nrestart cache")

    assert len(store.points) == 1
    assert store.points[0].payload == {"content": "Latency\nrestart cache"}
