import pytest

from oncallagent.knowledge.indexing import (
    DocumentChunk,
    VectorPoint,
    build_vector_points,
    extract_runbook_metadata,
    split_markdown,
    split_markdown_by_h1,
    split_text_into_pieces,
)


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.inputs: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.inputs.append(texts)
        return [[float(len(text)), 0.0] for text in texts]


def test_split_markdown_by_h1_keeps_heading_in_content() -> None:
    chunks = split_markdown_by_h1("# A\nbody\n# B\nnext")

    assert [chunk.content for chunk in chunks] == ["# A\nbody", "# B\nnext"]
    assert all(chunk.id for chunk in chunks)


def test_split_markdown_by_h1_returns_single_chunk_when_no_h1() -> None:
    chunks = split_markdown_by_h1("body only")

    assert chunks == [DocumentChunk(id=chunks[0].id, content="body only")]


@pytest.mark.anyio
async def test_build_vector_points_weights_title_twice_and_skips_non_heading() -> None:
    embedder = FakeEmbeddingService()
    chunks = [
        DocumentChunk(id="1", content="# Latency\nstep one\nstep two"),
        DocumentChunk(id="2", content="No heading\nignored"),
    ]

    points = await build_vector_points(chunks, embedder)

    assert len(points) == 1
    assert isinstance(points[0], VectorPoint)
    assert points[0].id == "1"
    assert points[0].payload == {"content": "# Latency\nstep one\nstep two"}
    assert embedder.inputs == [["Latency", "Latency", "step one", "step two"]]


def test_split_markdown_builds_hierarchical_chunks_with_heading_paths() -> None:
    markdown = "# Manual\nintro line\n## Steps\nstep one\nstep two\n### Deep\nstep three"

    chunks = split_markdown(markdown, max_chunk_chars=1_000_000)

    assert [(chunk.heading, chunk.content) for chunk in chunks] == [
        ("Manual", "# Manual\nintro line"),
        ("Manual > Steps", "# Manual\n## Steps\nstep one\nstep two"),
        ("Manual > Steps > Deep", "# Manual\n## Steps\n### Deep\nstep three"),
    ]


def test_split_markdown_splits_long_bodies_into_multiple_chunks_with_overlap() -> None:
    body = "\n".join(f"step {index:03d} instructions here" for index in range(30))

    chunks = split_markdown(f"# Big\n{body}", max_chunk_chars=120, overlap_chars=20)

    assert len(chunks) > 1
    assert all(chunk.heading == "Big" for chunk in chunks)
    assert all(chunk.content.startswith("# Big") for chunk in chunks)
    for previous, following in zip(chunks, chunks[1:]):
        assert previous.content.split("\n")[-1] in following.content


def test_split_markdown_ignores_headings_inside_code_fences() -> None:
    markdown = "# Manual\n## Steps\n```\n# not a heading\nstill body\n```\n## Done\nok"

    chunks = split_markdown(markdown, max_chunk_chars=1_000_000)

    assert [(chunk.heading, chunk.content) for chunk in chunks] == [
        ("Manual > Steps", "# Manual\n## Steps\n```\n# not a heading\nstill body\n```"),
        ("Manual > Done", "# Manual\n## Done\nok"),
    ]


def test_split_text_into_pieces_repeats_tail_for_overlap() -> None:
    text = "\n".join(f"line-{index:03d}" for index in range(40))

    pieces = split_text_into_pieces(text, max_chars=60, overlap_chars=15)

    assert len(pieces) > 1
    for previous, following in zip(pieces, pieces[1:]):
        assert previous.split("\n")[-1] in following


def test_split_text_into_pieces_returns_single_piece_when_short() -> None:
    assert split_text_into_pieces("short text", max_chars=100, overlap_chars=10) == ["short text"]


@pytest.mark.anyio
async def test_build_vector_points_uses_heading_path_and_ancestor_weights() -> None:
    embedder = FakeEmbeddingService()
    chunks = [
        DocumentChunk(
            id="1",
            content="# Manual\n## Steps\nstep one",
            heading="Manual > Steps",
        )
    ]

    points = await build_vector_points(chunks, embedder)

    assert embedder.inputs == [["Steps", "Steps", "Manual", "step one"]]
    assert points[0].payload == {
        "content": "# Manual\n## Steps\nstep one",
        "heading": "Manual > Steps",
    }


@pytest.mark.anyio
async def test_build_vector_points_applies_passage_prefix_when_configured() -> None:
    class PrefixedEmbedder(FakeEmbeddingService):
        passage_prefix = "search_document:"

    embedder = PrefixedEmbedder()
    chunks = [
        DocumentChunk(id="1", content="# Latency\nrestart cache", heading="Latency"),
    ]

    await build_vector_points(chunks, embedder)

    assert embedder.inputs == [
        ["search_document: Latency", "search_document: Latency", "search_document: restart cache"]
    ]


def test_extract_runbook_metadata_extracts_alertname_and_metrics() -> None:
    markdown = (
        "# Manual\n"
        "## 适用告警\n"
        "- 告警名：`ResourceCommunityHighErrorRate`\n"
        "- 重点指标：`resource_community_http_requests_total`\n"
        "- 重点指标：`foo_total`、`bar_total`\n"
    )

    metadata = extract_runbook_metadata(markdown)

    assert metadata["alertname"] == "ResourceCommunityHighErrorRate"
    assert metadata["metrics"] == [
        "resource_community_http_requests_total",
        "foo_total",
        "bar_total",
    ]


def test_extract_runbook_metadata_returns_empty_defaults() -> None:
    assert extract_runbook_metadata("# Manual\nno alerts here") == {
        "alertname": "",
        "metrics": [],
    }
