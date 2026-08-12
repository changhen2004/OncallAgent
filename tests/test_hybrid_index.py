import pytest

from oncallagent.knowledge.index import KnowledgeIndex


class FakeVectorStore:
    def __init__(self, results=None, error=None) -> None:
        self.results = results or []
        self.error = error
        self.queries: list[str] = []

    async def search(
        self,
        query: str,
        *,
        limit: int = 3,
        score_threshold: float = 0.5,
        payload_filter: dict | None = None,
    ):
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        return self.results


@pytest.mark.anyio
async def test_search_hybrid_merges_vector_results_with_lexical(tmp_path) -> None:
    (tmp_path / "error.md").write_text("5xx error rate high", encoding="utf-8")
    (tmp_path / "queue.md").write_text("rabbitmq backlog", encoding="utf-8")
    vector = FakeVectorStore(
        results=[{"source": "queue.md", "content": "rabbitmq backlog steps", "score": 0.9}]
    )
    knowledge = KnowledgeIndex(tmp_path, vector_store=vector)

    results = await knowledge.search_hybrid("rabbitmq backlog", limit=2)

    assert [result.filename for result in results] == ["queue.md"]
    assert results[0].content == "rabbitmq backlog"
    assert vector.queries == ["rabbitmq backlog"]


@pytest.mark.anyio
async def test_search_hybrid_falls_back_to_lexical_when_vector_fails(tmp_path) -> None:
    (tmp_path / "error.md").write_text("5xx error rate high", encoding="utf-8")
    vector = FakeVectorStore(error=RuntimeError("qdrant down"))
    knowledge = KnowledgeIndex(tmp_path, vector_store=vector)

    results = await knowledge.search_hybrid("5xx", limit=3)

    assert [result.filename for result in results] == ["error.md"]


@pytest.mark.anyio
async def test_search_hybrid_without_vector_store_returns_lexical(tmp_path) -> None:
    (tmp_path / "error.md").write_text("5xx error rate high", encoding="utf-8")

    results = await KnowledgeIndex(tmp_path).search_hybrid("5xx", limit=3)

    assert [result.filename for result in results] == ["error.md"]


@pytest.mark.anyio
async def test_reindex_external_reindexes_all_docs_with_source(tmp_path) -> None:
    (tmp_path / "a.md").write_text("# A\nbody a", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B\nbody b", encoding="utf-8")

    class FakeIndexer:
        def __init__(self) -> None:
            self.calls: list[tuple[str | None, str]] = []

        async def index_markdown(self, markdown: str, *, source: str | None = None) -> None:
            self.calls.append((source, markdown))

    indexer = FakeIndexer()
    knowledge = KnowledgeIndex(tmp_path, external_indexer=indexer)

    await knowledge.reindex_external()

    assert sorted(source for source, _ in indexer.calls) == ["a.md", "b.md"]
    assert any("body a" in markdown for _, markdown in indexer.calls)


@pytest.mark.anyio
async def test_save_upload_indexes_external_with_source(tmp_path) -> None:
    class FakeUploadFile:
        filename = "latency.md"

        async def read(self):
            return b"# Latency\nrestart cache"

    class FakeIndexer:
        def __init__(self) -> None:
            self.calls: list[tuple[str | None, str]] = []

        async def index_markdown(self, markdown: str, *, source: str | None = None) -> None:
            self.calls.append((source, markdown))

    indexer = FakeIndexer()
    knowledge = KnowledgeIndex(tmp_path, external_indexer=indexer)

    await knowledge.save_upload(FakeUploadFile())

    assert indexer.calls == [("latency.md", "# Latency\nrestart cache")]


@pytest.mark.anyio
async def test_search_hybrid_passes_payload_filter_to_vector_store(tmp_path) -> None:
    (tmp_path / "error.md").write_text("5xx error rate high", encoding="utf-8")

    class FilterVectorStore:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int, dict | None]] = []

        async def search(
            self,
            query: str,
            *,
            limit: int = 3,
            score_threshold: float = 0.5,
            payload_filter: dict | None = None,
        ):
            self.calls.append((query, limit, payload_filter))
            return []

    vector = FilterVectorStore()
    knowledge = KnowledgeIndex(tmp_path, vector_store=vector)

    await knowledge.search_hybrid("5xx", limit=3, payload_filter={"must": []})

    assert vector.calls == [("5xx", 3, {"must": []})]
