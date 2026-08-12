from __future__ import annotations

from oncallagent.agent.planner import LLMExecutor, LLMPlanner, LLMReplanner, PlanExecuteReplanAgent
from oncallagent.agent.chat_agent import ChatAgent
from oncallagent.infra.config import AppConfig
from oncallagent.knowledge.embedding import OllamaEmbeddingService
from oncallagent.knowledge.external import ExternalKnowledgeIndexer
from oncallagent.knowledge.index import KnowledgeIndex
from oncallagent.infra.llm import OpenAICompatibleChatModel
from oncallagent.tools.mcp import HttpJsonRpcTransport, MCPClient, MCPTool
from oncallagent.knowledge.qdrant import QdrantVectorStore
from oncallagent.storage.store import ConversationStore, LazyPostgresStore
from oncallagent.tools.builtin import KnowledgeSearchTool, PrometheusAlertsTool, TimeTool


def build_chat_model(cfg: AppConfig) -> OpenAICompatibleChatModel | None:
    if not cfg.openai.api_key:
        return None
    return OpenAICompatibleChatModel(
        api_key=cfg.openai.api_key,
        model=cfg.openai.model,
        api_base=cfg.openai.api_base,
    )


def build_optional_lazy_store(cfg: AppConfig) -> LazyPostgresStore | None:
    """Create a lazily-initialised PostgreSQL store.  Returns None when no
    database_url is configured, preserving the existing in-memory-only mode."""
    if not cfg.storage.database_url:
        return None
    return LazyPostgresStore(
        cfg.storage.database_url,
        min_size=cfg.storage.min_connections,
        max_size=cfg.storage.max_connections,
    )


def build_optional_chat_agent(
    cfg: AppConfig, knowledge: KnowledgeIndex, *, storage: ConversationStore | None = None
) -> ChatAgent | None:
    model = build_chat_model(cfg)
    if model is None:
        return None
    tools = [
        TimeTool(),
        KnowledgeSearchTool(knowledge),
        PrometheusAlertsTool(cfg.get_prometheus_url()),
    ]
    return ChatAgent(model=model, tools=tools, storage=storage)


def build_optional_plan_agent(
    cfg: AppConfig,
    chat_agent: ChatAgent | None,
    *,
    storage: ConversationStore | None = None,
) -> PlanExecuteReplanAgent | None:
    model = build_chat_model(cfg)
    if model is None or chat_agent is None:
        return None
    return PlanExecuteReplanAgent(
        planner=LLMPlanner(model),
        executor=LLMExecutor(chat_agent),
        replanner=LLMReplanner(model),
        max_iterations=20,
        storage=storage,
    )


def build_optional_embedder(cfg: AppConfig) -> OllamaEmbeddingService:
    return OllamaEmbeddingService(
        cfg.get_embedder_addr(),
        cfg.embedder.model,
        passage_prefix=cfg.embedder.passage_prefix,
        query_prefix=cfg.embedder.query_prefix,
    )


def build_optional_vector_store(
    cfg: AppConfig, embedder: OllamaEmbeddingService
) -> QdrantVectorStore:
    return QdrantVectorStore(
        f"http://{cfg.get_qdrant_addr()}",
        cfg.qdrant.collection,
        vector_size=cfg.embedder.dimension,
        embedder=embedder,
        top_k=cfg.qdrant.top_k,
        score_threshold=cfg.qdrant.score_threshold,
    )


def build_optional_external_indexer(
    cfg: AppConfig,
    *,
    enabled: bool = False,
    embedder: OllamaEmbeddingService | None = None,
    vector_store: QdrantVectorStore | None = None,
) -> ExternalKnowledgeIndexer | None:
    if not enabled:
        return None
    embedder = embedder or build_optional_embedder(cfg)
    vector_store = vector_store or build_optional_vector_store(cfg, embedder)
    return ExternalKnowledgeIndexer(embedder=embedder, vector_store=vector_store)


async def build_mcp_tools(cfg: AppConfig) -> list[MCPTool]:
    if not cfg.cls_mcp.enabled:
        return []
    client = MCPClient(HttpJsonRpcTransport(cfg.get_cls_mcp_url()))
    return await client.get_tools()
