from __future__ import annotations

from typing import Protocol

import httpx

from oncallagent.knowledge.embedding import normalize_embedding
from oncallagent.knowledge.indexing import VectorPoint


class AsyncEmbedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        pass


class QdrantVectorStore:
    def __init__(
        self,
        base_url: str,
        collection: str,
        *,
        vector_size: int = 768,
        embedder: AsyncEmbedder | None = None,
        timeout: float = 10.0,
        top_k: int = 2,
        score_threshold: float = 0.5,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.collection = collection
        self.vector_size = vector_size
        self.embedder = embedder
        self.timeout = timeout
        self.top_k = top_k
        self.score_threshold = score_threshold

    async def recreate_collection(self) -> None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            exists_response = await client.get(
                f"{self.base_url}/collections/{self.collection}/exists"
            )
            exists_response.raise_for_status()
            exists = bool(exists_response.json().get("result", {}).get("exists"))
            if exists:
                delete_response = await client.delete(
                    f"{self.base_url}/collections/{self.collection}"
                )
                delete_response.raise_for_status()

            create_response = await client.put(
                f"{self.base_url}/collections/{self.collection}",
                json={"vectors": {"size": self.vector_size, "distance": "Dot"}},
            )
            create_response.raise_for_status()

    async def upsert_points(self, points: list[VectorPoint]) -> None:
        payload = {
            "points": [
                {"id": point.id, "vector": point.vector, "payload": point.payload}
                for point in points
            ]
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.put(
                f"{self.base_url}/collections/{self.collection}/points",
                json=payload,
            )
            response.raise_for_status()

    async def search(
        self,
        query: str,
        *,
        limit: int | None = None,
        score_threshold: float | None = None,
        payload_filter: dict | None = None,
    ) -> list[dict]:
        if self.embedder is None:
            raise RuntimeError("qdrant retriever embedder is not configured")
        query_prefix = getattr(self.embedder, "query_prefix", "") or ""
        query_text = f"{query_prefix} {query}".strip() if query_prefix else query
        embeddings = await self.embedder.embed([query_text])
        vector = normalize_embedding(embeddings[0])
        request = {
            "vector": vector,
            "limit": self.top_k if limit is None else limit,
            "score_threshold": self.score_threshold if score_threshold is None else score_threshold,
            "with_payload": True,
        }
        if payload_filter is not None:
            request["filter"] = payload_filter
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/collections/{self.collection}/points/search",
                json=request,
            )
            response.raise_for_status()
            payload = response.json()

        results: list[dict] = []
        for item in payload.get("result", []):
            result = dict(item.get("payload", {}))
            if "score" in item:
                result["score"] = item["score"]
            results.append(result)
        return results
