from oncallagent.indexing import DocumentChunk, VectorPoint, build_vector_points, split_markdown_by_h1
import pytest


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
    assert points[0].payload == {"content": "Latency\nstep one\nstep two"}
    assert embedder.inputs == [["Latency", "Latency", "step one", "step two"]]
