# OnCallAgent: AIOps 智能排障 Agent

OnCallAgent 是一个 FastAPI 版智能运维值班代理，把 Prometheus 告警、实时指标、内部 runbook、RAG 检索和可选 LLM 工具调用组合成排障分析流程。它可以独立使用，也可以接入 [GoCommunity](https://github.com/changhen2004/resource_community_go) 的 Prometheus 指标和告警，演示从业务异常到排障建议的闭环。

## 核心能力

- 兼容原始 API：`GET /ping`、`POST /upload`、`POST /chat`、`POST /chatStream`、`GET /plan`。
- RAG 知识库：读取 `docs/runbooks/*.md`，按中文 bigram / trigram、文件名、标题和短语匹配做本地检索。
- 混合检索：可选 Ollama Embedding + Qdrant 向量检索，与本地词法检索通过 RRF 融合。
- 告警分析：`/plan` 查询 Prometheus `/api/v1/alerts`，识别 firing 告警并匹配 runbook；配置 LLM 后进入 Plan-Execute-Replan 工作流。
- 工具调用：ChatAgent 可调用时间、知识库检索和 Prometheus 告警工具；工具层包含超时、参数校验、异常捕获和审计记录。
- 流式对话：`/chatStream` 以 SSE 返回，Agent 可用时走 Agent 流式路径，否则先输出检索进度再返回降级答案。
- 可选持久化：配置 PostgreSQL 后保存会话消息、工具调用记录、Agent Run 和 Evidence；未配置时使用内存会话。
- 降级可用：没有 OpenAI 兼容模型、Prometheus、PostgreSQL、Qdrant 或 Ollama 时，核心接口仍可用并返回知识库或检查清单。
- 评估与演示：内置 pytest、RAG 评估集、离线 incident flow，以及本地 Prometheus 测试服务。

## 架构

```text
FastAPI
  |-- /ping
  |-- /upload: Markdown runbook 入库
  |-- /chat: ChatService / ChatAgent
  |-- /chatStream: SSE
  |-- /plan: PlanService / PlanExecuteReplanAgent

KnowledgeIndex
  |-- 本地词法检索
  |-- 可选 QdrantVectorStore + OllamaEmbeddingService
  |-- search_hybrid 使用 RRF 合并结果

Tools
  |-- TimeTool
  |-- KnowledgeSearchTool
  |-- PrometheusAlertsTool
  |-- MCPTool / MCPClient

Storage
  |-- 默认内存
  |-- 可选 LazyPostgresStore + migrations
```

## 快速开始

项目使用 [uv](https://docs.astral.sh/uv/) 管理依赖，需要 Python 3.11+。

```bash
git clone <repository-url>
cd OnCallAgent
uv sync
cp config/config_template.json config/config.json
```

如果只想本地降级运行，请把 `config/config.json` 中的 `openai.api_key` 改为空字符串。模板里的 `xxx` 是占位符；只要该字段非空，应用就会按“已配置 LLM”装配 ChatAgent 和 Plan Agent。

启动服务：

```bash
uv run uvicorn oncallagent.main:app --host localhost --port 8819
```

检查服务：

```bash
curl http://localhost:8819/ping
```

返回 `{"message":"pong"}` 表示 API 已就绪。

## 可选依赖

| 依赖 | 用途 | 不可用时行为 |
|---|---|---|
| OpenAI 兼容 API | ChatAgent 工具调用、Plan-Execute-Replan | `/chat` 使用知识库降级回复，`/plan` 使用规则化 runbook 命中 |
| Prometheus | `/plan` 查询活跃告警 | 返回 Prometheus 不可用的降级检查清单 |
| Ollama | 生成文档和查询 embedding | 外部索引失败会记录日志，检索回退本地词法 |
| Qdrant | 向量索引和向量检索 | 混合检索回退本地词法 |
| PostgreSQL | 会话、工具审计、Agent Run、Evidence 持久化 | 使用内存会话，不持久化 |
| MCP/SSE 服务 | 接入外部工具 | `build_mcp_tools` 返回可用 MCP 工具，未调用时不影响主流程 |

启动仓库自带的 Prometheus / Grafana / 测试指标服务：

```bash
docker compose -f docker-compose.prometheus.yml up -d
```

| 服务 | 地址 |
|---|---|
| OnCallAgent | http://localhost:8819 |
| Prometheus 测试环境 | http://localhost:9090 |
| Grafana | http://localhost:3000，默认 `admin/admin` |
| 测试指标服务 | http://localhost:2112/metrics |

接入 GoCommunity 时，将 `config/config.json` 的 `prometheus.url` 改为 `http://localhost:9091`。

## 配置

默认加载 `config/config.json`；如果文件不存在，则回退到 `config/config_template.json`；两者都不存在时使用代码默认值。

| 配置项 | 说明 |
|---|---|
| `server.host` / `server.port` | 服务监听配置，默认 `localhost:8819` |
| `openai.api_key` | OpenAI 兼容 API Key；为空则不装配 LLM Agent |
| `openai.model` / `openai.api_base` | OpenAI 兼容模型和接口地址 |
| `prometheus.url` | Prometheus 地址，默认 `http://localhost:9090` |
| `embedder.*` | Ollama embedding 服务、模型、维度和 query / passage 前缀 |
| `qdrant.*` | Qdrant 地址、collection、top_k 和 score_threshold |
| `storage.database_url` | PostgreSQL 连接串；为空则关闭持久化 |
| `cls_mcp.base_url` / `cls_mcp.enabled` | MCP/SSE 外部工具配置 |

`create_app(enable_external_indexing=True)` 默认会在应用生命周期启动时尝试把 `docs/runbooks/` 重建到外部向量索引；失败会逐文件记录日志，不阻断本地词法检索。

## API

| 方法 | 路径 | 请求 | 返回 |
|---|---|---|---|
| `GET` | `/ping` | 无 | `{"message":"pong"}` |
| `POST` | `/upload` | multipart 文件字段 `file` | 保存到 `docs/runbooks/` 并更新索引 |
| `POST` | `/chat` | `{"question":"...","id":"session-id"}` | `{"message":"..."}` |
| `POST` | `/chatStream` | `{"question":"...","id":"session-id"}` | SSE，结束事件为 `data: [DONE]` |
| `GET` | `/plan` | 无 | `{"message":"获取运维信息成功","data":{"lastmsg":"...","msgs":[...]}}` |

请求校验失败统一返回 `400` 和 `{"message":"invalid request"}`。

## RAG 与 Agent 实现

`KnowledgeIndex` 启动时加载 `docs/runbooks/*.md`。本地检索会对中文生成 bigram / trigram，对英文、指标名和文件名保留词元，并额外提升 Markdown 标题、文件名和连续短语命中权重。

外部向量索引由 `OllamaEmbeddingService`、`QdrantVectorStore` 和 `ExternalKnowledgeIndexer` 组成。Markdown 会按标题层级切分，超长内容带重叠拆分，payload 包含 `heading`、`source`、`alertname` 和 `metrics` 等元数据。`search_hybrid` 在向量检索可用时使用 RRF 合并词法和向量结果；向量服务异常时回退词法结果。

配置 LLM 后，`ChatAgent` 会使用 OpenAI 兼容 `/chat/completions` 接口进行工具调用，最多迭代 8 轮。`/plan` 在存在 firing 告警且 Plan Agent 可用时进入 Plan-Execute-Replan，最多迭代 20 轮；没有 LLM 时按告警摘要检索 runbook 并返回规则化建议。

## 与 GoCommunity 联动

GoCommunity 提供真实业务指标、Prometheus 告警、Grafana 面板和压测演练脚本。OnCallAgent 仓库内置了对应 runbook：

| 故障场景 | runbook |
|---|---|
| 接口 P95 升高 | `docs/runbooks/resource-community-p95-latency.md` |
| 错误率升高 | `docs/runbooks/resource-community-error-rate.md` |
| 热榜异常 | `docs/runbooks/resource-community-hot-ranking.md` |
| RabbitMQ 积压 | `docs/runbooks/resource-community-rabbitmq-backlog.md` |

联动流程：

```text
GoCommunity /metrics -> Prometheus 告警 -> OnCallAgent /plan -> runbook 命中和排障建议
```

## 测试、评估与演示

```bash
uv run pytest
uv run python scripts/rag_eval.py --format markdown
uv run python scripts/rag_eval.py --retriever hybrid --format markdown
uv run python scripts/demo_incident_flow.py
```

当前测试覆盖 API、配置加载、RAG 检索、混合索引、Qdrant 集成封装、Embedding、工具运行时、ChatAgent、PlanService、Harness、PostgreSQL 存储、Prometheus 测试服务和演示流程。RAG 评估集位于 `eval/rag_questions.json`，评估说明见 `docs/evaluation/rag-eval.md`。

## 项目结构

```text
OnCallAgent/
├── oncallagent/
│   ├── main.py               # FastAPI 应用入口与路由
│   ├── agent/                # ChatAgent、Plan-Execute-Replan、Harness
│   ├── services/             # chat / plan 服务
│   ├── tools/                # 内置工具、工具执行器、MCP 工具
│   ├── knowledge/            # 本地检索、切分、Embedding、Qdrant、混合检索
│   ├── storage/              # PostgreSQL store 和迁移
│   ├── infra/                # 配置、LLM、对象装配
│   └── eval/                 # RAG 评估和 incident demo
├── docs/
│   ├── runbooks/             # 运维知识库
│   ├── evaluation/           # 评估和 Agent Run 记录
│   └── development/          # 开发过程文档
├── tests/                    # pytest 测试
├── eval/                     # RAG 问题集
├── config/                   # 配置模板
├── scripts/                  # 评估、演示、MCP 辅助脚本
├── prometheus_config/        # Prometheus 规则
├── prometheusTestServer/     # 本地指标模拟服务
├── docker-compose.prometheus.yml
├── pyproject.toml
└── uv.lock
```

## 后续方向

- 为混合检索增加 rerank 和更细的 payload filter 接入。
- 增加索引生命周期管理，例如按 source 删除旧 chunk、内容 hash 去重和增量更新。
- 为应用自身补充 `/metrics`，跟踪检索延迟、命中率和工具成功率。
- 扩展 MCP 外部工具、权限边界和结果截断策略。
- 接入 Alertmanager Webhook，形成更完整的告警事件入口。
