from __future__ import annotations

import math
from typing import Protocol

import httpx


class EmbeddingService(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        pass


def average_embeddings(embeddings: list[list[float]]) -> list[float]:
    if not embeddings:
        raise ValueError("no embeddings provided")

    dim = len(embeddings[0])
    avg = [0.0] * dim
    for index, embedding in enumerate(embeddings):
        if len(embedding) != dim:
            raise ValueError(
                f"embedding {index} has different length: got {len(embedding)}, expected {dim}"
            )
        for vector_index, value in enumerate(embedding):
            avg[vector_index] += value

    return [value / len(embeddings) for value in avg]


def normalize_embedding(embedding: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in embedding))
    if norm == 0:
        return embedding
    return [value / norm for value in embedding]


class OllamaEmbeddingService:
    def __init__(self, base_url: str, model: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for text in texts:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                response.raise_for_status()
                payload = response.json()
                embeddings.append([float(value) for value in payload.get("embedding", [])])
        return embeddings
