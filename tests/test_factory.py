import pytest

from oncallagent.factory import (
    build_mcp_tools,
    build_optional_chat_agent,
    build_optional_external_indexer,
    build_optional_plan_agent,
)
from oncallagent.config import AppConfig, CLSMcpConfig, OpenAIConfig
from oncallagent.knowledge import KnowledgeIndex


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


@pytest.mark.anyio
async def test_build_mcp_tools_respects_enabled_flag(monkeypatch) -> None:
    cfg = AppConfig(cls_mcp=CLSMcpConfig(enabled=False))

    assert await build_mcp_tools(cfg) == []
