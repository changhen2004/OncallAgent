from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from oncallagent.embedding import average_embeddings, normalize_embedding


class EmbeddingService(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        pass


@dataclass(frozen=True)
class DocumentChunk:
    id: str
    content: str


@dataclass(frozen=True)
class VectorPoint:
    id: str
    vector: list[float]
    payload: dict[str, str]


def split_markdown_by_h1(markdown: str) -> list[DocumentChunk]:
    chunks: list[str] = []
    current: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("# ") and current:
            chunks.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)

    if current:
        chunks.append("\n".join(current).strip())

    return [DocumentChunk(id=str(uuid4()), content=chunk) for chunk in chunks if chunk]


async def build_vector_points(
    chunks: list[DocumentChunk], embedder: EmbeddingService
) -> list[VectorPoint]:
    points: list[VectorPoint] = []
    for chunk in chunks:
        lines = chunk.content.split("\n")
        if not lines or not lines[0].startswith("#"):
            continue

        title = lines[0].removeprefix("# ").strip()
        body = lines[1:]
        weighted_text = [title, title, *body]
        embeddings = await embedder.embed(weighted_text)
        vector = normalize_embedding(average_embeddings(embeddings))
        points.append(
            VectorPoint(
                id=chunk.id,
                vector=vector,
                payload={"content": title + "\n" + "\n".join(body)},
            )
        )
    return points
