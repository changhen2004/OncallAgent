import pytest

from oncallagent.knowledge.external import ExternalKnowledgeIndexer
from oncallagent.knowledge.indexing import VectorPoint


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

    await indexer.index_markdown("# Latency\nrestart cache", source="latency.md")

    assert len(store.points) == 1
    assert store.points[0].payload == {
        "content": "# Latency\nrestart cache",
        "heading": "Latency",
        "source": "latency.md",
    }


@pytest.mark.anyio
async def test_external_indexer_attaches_runbook_metadata_to_payload() -> None:
    store = FakeVectorStore()
    indexer = ExternalKnowledgeIndexer(embedder=FakeEmbedder(), vector_store=store)
    markdown = (
        "# Error Manual\n"
        "## 适用告警\n"
        "- 告警名：`HighErrorRate`\n"
        "- 重点指标：`http_requests_total`\n"
        "## Steps\nrestart cache workers"
    )

    await indexer.index_markdown(markdown, source="error.md")

    assert len(store.points) == 2
    for point in store.points:
        assert point.payload["source"] == "error.md"
        assert point.payload["alertname"] == "HighErrorRate"
        assert point.payload["metrics"] == ["http_requests_total"]
