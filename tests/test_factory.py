import pytest

from oncallagent.infra.factory import (
    build_mcp_tools,
    build_optional_chat_agent,
    build_optional_embedder,
    build_optional_external_indexer,
    build_optional_plan_agent,
    build_optional_vector_store,
)
from oncallagent.infra.config import AppConfig, CLSMcpConfig, OpenAIConfig, QdrantConfig
from oncallagent.knowledge.index import KnowledgeIndex


def test_build_optional_chat_agent_returns_none_without_api_key(tmp_path) -> None:
    cfg = AppConfig(openai=OpenAIConfig(api_key=""))

    assert build_optional_chat_agent(cfg, KnowledgeIndex(tmp_path)) is None


def test_build_optional_chat_agent_builds_when_api_key_is_configured(tmp_path) -> None:
    cfg = AppConfig(openai=OpenAIConfig(api_key="sk-test", model="m", api_base="https://api.test/v1"))

    agent = build_optional_chat_agent(cfg, KnowledgeIndex(tmp_path))

    assert agent is not None


def test_build_optional_plan_agent_requires_chat_agent(tmp_path) -> None:
    cfg = AppConfig(openai=OpenAIConfig(api_key="sk-test", model="m", api_base="https://api.test/v1"))

    assert build_optional_plan_agent(cfg, None) is None


def test_build_optional_external_indexer_is_explicitly_enabled() -> None:
    cfg = AppConfig(openai=OpenAIConfig(api_key=""))

    assert build_optional_external_indexer(cfg, enabled=False) is None
    assert build_optional_external_indexer(cfg, enabled=True) is not None


def test_build_optional_vector_store_applies_configured_defaults() -> None:
    cfg = AppConfig(qdrant=QdrantConfig(port=6333, top_k=4, score_threshold=0.3))
    embedder = build_optional_embedder(cfg)

    store = build_optional_vector_store(cfg, embedder)

    assert store is not None
    assert store.base_url == "http://localhost:6333"
    assert store.vector_size == 768
    assert store.top_k == 4
    assert store.score_threshold == 0.3


def test_build_optional_external_indexer_wires_embedder_and_vector_store() -> None:
    cfg = AppConfig(qdrant=QdrantConfig(port=6333, top_k=4, score_threshold=0.3))

    indexer = build_optional_external_indexer(cfg, enabled=True)

    assert indexer is not None
    assert indexer.vector_store is not None
    assert indexer.vector_store.top_k == 4
    assert indexer.vector_store.score_threshold == 0.3


@pytest.mark.anyio
async def test_build_mcp_tools_respects_enabled_flag(monkeypatch) -> None:
    cfg = AppConfig(cls_mcp=CLSMcpConfig(enabled=False))

    assert await build_mcp_tools(cfg) == []
