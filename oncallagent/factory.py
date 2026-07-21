from __future__ import annotations

from oncallagent.agent import LLMExecutor, LLMPlanner, LLMReplanner, PlanExecuteReplanAgent
from oncallagent.chat_agent import ChatAgent
from oncallagent.config import AppConfig
from oncallagent.embedding import OllamaEmbeddingService
from oncallagent.external_indexer import ExternalKnowledgeIndexer
from oncallagent.knowledge import KnowledgeIndex
from oncallagent.llm import OpenAICompatibleChatModel
from oncallagent.mcp import HttpJsonRpcTransport, MCPClient, MCPTool
from oncallagent.qdrant import QdrantVectorStore
from oncallagent.tools import KnowledgeSearchTool, PrometheusAlertsTool, TimeTool


def build_chat_model(cfg: AppConfig) -> OpenAICompatibleChatModel | None:
    if not cfg.openai.api_key:
        return None
    return OpenAICompatibleChatModel(
        api_key=cfg.openai.api_key,
        model=cfg.openai.model,
        api_base=cfg.openai.api_base,
    )


def build_optional_chat_agent(cfg: AppConfig, knowledge: KnowledgeIndex) -> ChatAgent | None:
    model = build_chat_model(cfg)
    if model is None:
        return None
    tools = [
        TimeTool(),
        KnowledgeSearchTool(knowledge),
        PrometheusAlertsTool(cfg.get_prometheus_url()),
    ]
    return ChatAgent(model=model, tools=tools)


def build_optional_plan_agent(
    cfg: AppConfig, chat_agent: ChatAgent | None
) -> PlanExecuteReplanAgent | None:
    model = build_chat_model(cfg)
    if model is None or chat_agent is None:
        return None
    return PlanExecuteReplanAgent(
        planner=LLMPlanner(model),
        executor=LLMExecutor(chat_agent),
        replanner=LLMReplanner(model),
        max_iterations=20,
    )


def build_optional_external_indexer(
    cfg: AppConfig, *, enabled: bool = False
) -> ExternalKnowledgeIndexer | None:
    if not enabled:
        return None
    embedder = OllamaEmbeddingService(cfg.get_embedder_addr(), cfg.embedder.model)
    vector_store = QdrantVectorStore(
        f"http://{cfg.get_qdrant_addr()}",
        cfg.qdrant.collection,
        vector_size=cfg.embedder.dimension,
        embedder=embedder,
    )
    return ExternalKnowledgeIndexer(embedder=embedder, vector_store=vector_store)


async def build_mcp_tools(cfg: AppConfig) -> list[MCPTool]:
    if not cfg.cls_mcp.enabled:
        return []
    client = MCPClient(HttpJsonRpcTransport(cfg.get_cls_mcp_url()))
    return await client.get_tools()
