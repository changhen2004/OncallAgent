from oncallagent.knowledge.retriever import SearchResult, rrf_merge


def test_rrf_merge_combines_lexical_and_vector_ranks() -> None:
    lexical = [
        SearchResult(filename="error.md", content="5xx", score=5),
        SearchResult(filename="latency.md", content="p95", score=3),
    ]
    vector = [
        {"source": "latency.md", "content": "p95", "score": 0.9},
        {"source": "queue.md", "content": "rabbitmq", "score": 0.8},
    ]

    merged = rrf_merge(lexical, vector, limit=3)

    assert [result.filename for result in merged] == ["latency.md", "error.md", "queue.md"]
    assert merged[0].score > merged[1].score
    assert merged[0].content == "p95"
    assert merged[2].content == "rabbitmq"


def test_rrf_merge_dedupes_vector_chunks_by_source_keeping_best_score() -> None:
    lexical = [SearchResult(filename="latency.md", content="full", score=1)]
    vector = [
        {"source": "latency.md", "content": "chunk a", "score": 0.5},
        {"source": "latency.md", "content": "chunk b", "score": 0.9},
    ]

    merged = rrf_merge(lexical, vector, limit=3)

    assert len(merged) == 1
    assert merged[0].filename == "latency.md"
    assert merged[0].content == "full"


def test_rrf_merge_returns_lexical_only_when_vector_results_empty() -> None:
    lexical = [SearchResult(filename="error.md", content="5xx", score=2)]

    merged = rrf_merge(lexical, [], limit=3)

    assert merged == lexical


def test_rrf_merge_includes_vector_only_results_without_source() -> None:
    lexical: list[SearchResult] = []

    merged = rrf_merge(lexical, [{"content": "queue steps", "score": 0.7}], limit=3)

    assert len(merged) == 1
    assert merged[0].content == "queue steps"
