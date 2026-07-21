import pytest

from oncallagent.indexing import VectorPoint
from oncallagent.qdrant import QdrantVectorStore


@pytest.mark.anyio
async def test_recreate_collection_deletes_existing_and_creates_dot_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class FakeResponse:
        def __init__(self, payload=None) -> None:
            self._payload = payload or {}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str):
            calls.append(("GET", url, None))
            return FakeResponse({"result": {"exists": True}})

        async def delete(self, url: str):
            calls.append(("DELETE", url, None))
            return FakeResponse()

        async def put(self, url: str, json: dict):
            calls.append(("PUT", url, json))
            return FakeResponse()

    monkeypatch.setattr("oncallagent.qdrant.httpx.AsyncClient", FakeClient)
    store = QdrantVectorStore("http://qdrant:6333", "oncallagent", vector_size=768)

    await store.recreate_collection()

    assert calls == [
        ("GET", "http://qdrant:6333/collections/oncallagent/exists", None),
        ("DELETE", "http://qdrant:6333/collections/oncallagent", None),
        (
            "PUT",
            "http://qdrant:6333/collections/oncallagent",
            {"vectors": {"size": 768, "distance": "Dot"}},
        ),
    ]


@pytest.mark.anyio
async def test_upsert_points_sends_vectors_and_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def put(self, url: str, json: dict):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("oncallagent.qdrant.httpx.AsyncClient", FakeClient)
    store = QdrantVectorStore("http://qdrant:6333", "oncallagent")

    await store.upsert_points([VectorPoint(id="p1", vector=[0.1, 0.2], payload={"content": "doc"})])

    assert captured == {
        "url": "http://qdrant:6333/collections/oncallagent/points",
        "json": {"points": [{"id": "p1", "vector": [0.1, 0.2], "payload": {"content": "doc"}}]},
    }


@pytest.mark.anyio
async def test_search_embeds_normalizes_and_queries_qdrant(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeEmbedder:
        async def embed(self, texts: list[str]) -> list[list[float]]:
            assert texts == ["latency"]
            return [[3.0, 4.0]]

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"result": [{"payload": {"content": "doc"}, "score": 0.9}]}

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, json: dict):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("oncallagent.qdrant.httpx.AsyncClient", FakeClient)
    store = QdrantVectorStore("http://qdrant:6333", "oncallagent", embedder=FakeEmbedder())

    results = await store.search("latency", limit=2, score_threshold=0.5)

    assert captured == {
        "url": "http://qdrant:6333/collections/oncallagent/points/search",
        "json": {"vector": [0.6, 0.8], "limit": 2, "score_threshold": 0.5, "with_payload": True},
    }
    assert results == [{"content": "doc", "score": 0.9}]
