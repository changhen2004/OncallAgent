# OnCallAgent — AIOps 智能排障 Agent

面向云服务故障场景的智能运维值班代理：把“Prometheus 告警 + 实时指标 + 内部排障文档”串成一条从告警发现、知识检索到处理建议生成的自动化分析链路，帮助值班人员快速定位故障并产出可执行的排障方案。

## 核心能力

- **RAG 知识库**：Markdown 运维手册构建本地轻量索引；可选 Ollama Embedding + Qdrant 向量检索，并与词法结果做 RRF 混合排序
- **工具调用**：内置时间 / 知识库检索 / Prometheus 告警工具，支持 OpenAI 兼容模型函数调用
- **告警计划分析**：Plan-Execute-Replan 工作流，自动获取活跃告警、命中 runbook、生成处理建议
- **流式对话**：SSE 多轮会话，支持知识库命中回复与工具调用轨迹
- **会话持久化**：可选 PostgreSQL 持久化对话消息、工具调用审计与 Agent Run 状态
- **降级可用**：Prometheus / PostgreSQL / LLM 任一不可用时自动降级，本地开箱即跑
- **可验证**：21 个测试文件 / 82 个 pytest 用例 + 30 条告警问题的 RAG 评估集（词法 + 混合双路径）

## 架构

```text
┌────────────────────────────────────────────────────────────┐
│                     OnCallAgent (FastAPI)                   │
├────────────────────────────────────────────────────────────┤
│  API：/ping /upload /chat /chatStream(SSE) /plan            │
├────────────────────────────────────────────────────────────┤
│  Services：ChatService / ChatAgent        PlanService /     │
│            PlanExecuteReplanAgent                          │
├────────────────────────────────────────────────────────────┤
│  Knowledge：KnowledgeIndex（本地检索 + RRF 混合）            │
│             ExternalKnowledgeIndexer（Ollama + Qdrant）     │
├────────────────────────────────────────────────────────────┤
│  Tools：TimeTool / KnowledgeSearchTool / PrometheusAlerts   │
│         Tool / MCPTool（MCP/SSE 外部工具）                  │
├────────────────────────────────────────────────────────────┤
│  Storage：ConversationStore Protocol → PostgresStore（可选）│
├────────────────────────────────────────────────────────────┤
│  Integrations：OpenAI 兼容 API / Prometheus / Ollama /      │
│                Qdrant / MCP/SSE                            │
└────────────────────────────────────────────────────────────┘
```

## 快速开始

### 前置依赖

- Python 3.11+ 与 [uv](https://docs.astral.sh/uv/)
- Prometheus（可选，用于告警分析；本仓库 Compose 默认 `http://localhost:9090`，接入 GoCommunity 时使用 `http://localhost:9091`）
- OpenAI 兼容 API Key（可选；未配置时使用本地知识库降级回复）
- Ollama + Qdrant（可选；仅开启外部向量索引时需要）
- PostgreSQL（可选；用于会话与审计持久化）
- MCP/SSE 服务（可选；用于接入外部日志工具）

### 安装与启动

```bash
git clone <repository-url> && cd OnCallAgent
uv sync

# 配置文件（可选）：默认读取 config/config.json，缺失时自动回退 config/config_template.json
cp config/config_template.json config/config.json

uv run uvicorn oncallagent.main:app --host localhost --port 8819
```

启动 Prometheus 测试环境：

```bash
docker compose -f docker-compose.prometheus.yml up -d
```

服务地址：`http://localhost:8819`；`/ping` 返回 `{"message": "pong"}` 即就绪。

## 配置说明

| 配置项 | 说明 |
|---|---|
| `server.host/port` | HTTP 服务地址（默认 8819） |
| `openai.*` | OpenAI 兼容 API；配置 `api_key` 后启用 ChatAgent 工具调用 |
| `prometheus.url` | Prometheus 地址；接入 GoCommunity 可观测平台时改为 `http://localhost:9091` |
| `embedder.*` / `qdrant.*` | 外部向量索引；仅开启外部索引时使用 |
| `storage.database_url` | PostgreSQL 连接串；留空则纯内存运行 |
| `cls_mcp.*` | MCP/SSE 外部工具地址与开关 |

## API 一览

| 端点 | 说明 |
|---|---|
| `GET /ping` | 健康检查 |
| `POST /upload` | 上传 Markdown 到 `docs/runbooks/` 并重建知识库索引 |
| `POST /chat` | 非流式对话（`question` + 会话 `id`） |
| `POST /chatStream` | SSE 流式对话 |
| `GET /plan` | 查询 Prometheus 活跃告警，匹配知识库并生成排障报告 |

## 核心设计

### 1. RAG 检索：面向中文运维场景的命中率优化

- 本地索引对中文采用 **bigram/trigram 连续片段切分**，避免单字拆分带来的泛化噪声；文件名与 Markdown 标题命中加权，日志原文 / 指标类英文短语整段匹配加分
- 用 30 条真实告警问题做回归评估：**Top1 命中率 93.3% → 100%，Top3 100%**（见 `docs/evaluation/rag-eval.md`）
- 可扩展外部索引：开启后通过 Ollama Embedding 分块写入 Qdrant，检索链路可插拔

### 2. Agent 工具调用治理

- 统一 Tool 接口，内置 `TimeTool` / `KnowledgeSearchTool` / `PrometheusAlertsTool` / `MCPTool`
- 每次工具调用具备超时控制、异常捕获、参数校验与失败降级，并实时写入审计记录
- Harness 记录 Agent Run 的目标、执行轨迹、工具调用次数与停止原因，支撑故障复盘与效果优化

### 3. Plan-Execute-Replan 告警分析

- `PlanService` 查询 Prometheus `/api/v1/alerts`，识别 firing 告警并去重
- 命中知识库 runbook 生成处理建议；配置 LLM 后由 `PlanExecuteReplanAgent` 编排“计划 → 执行 → 重规划”
- Prometheus 不可用时返回**降级检查清单**，保证功能不中断

### 4. 会话与审计持久化（可选）

- 基于 `ConversationStore` Protocol 注入 `PostgresStore`，`create_app()` 保持同步、连接池懒加载
- 持久化内容：会话消息滑动窗口（重启自动恢复）、工具调用审计、Agent Run 状态（`AgentState` + `Evidence`）
- 迁移由 `migrations.py` 按版本自动执行；不配置 `database_url` 时完全回退纯内存模式

### 5. 降级可用设计

所有外部依赖均可选：无 LLM 用知识库检索回复、无 Prometheus 用降级清单、无 PostgreSQL 用内存存储，保证本地开发与演示场景开箱即用。

## 测试与评估

```bash
uv run pytest                                    # 20 个文件 / 69 个用例
uv run python scripts/rag_eval.py --format markdown   # RAG TopK 命中率评估
uv run python scripts/demo_incident_flow.py           # 告警 → Runbook → Agent 演示
```

- 测试覆盖：API 行为、配置加载、工具调用、告警分析、RAG 检索评估、存储持久化等
- 评估集：`eval/rag_questions.json`（30 条真实告警问题）

## 与 GoCommunity 联动

GoCommunity 提供 Prometheus + Grafana 可观测平台与压测演练脚本，OnCallAgent 将其作为真实业务系统做告警分析演示，形成“业务指标 → 告警 → 知识库 → 分析建议”闭环：

```text
GoCommunity ──Prometheus──▶ 告警 ──▶ OnCallAgent（RAG + Agent）──▶ 排障建议
```

仓库已内置对应 runbook（`docs/runbooks/`）：

| 故障场景 | runbook |
|---|---|
| 接口 P95 升高 | `resource-community-p95-latency.md` |
| 错误率升高 | `resource-community-error-rate.md` |
| 热榜异常 | `resource-community-hot-ranking.md` |
| RabbitMQ 积压 | `resource-community-rabbitmq-backlog.md` |

## 项目结构

```text
OnCallAgent/
├── oncallagent/
│   ├── main.py               # FastAPI 应用入口与路由
│   ├── agent/                # chat_agent / planner / harness（工作流编排）
│   ├── services/             # chat / plan（业务服务）
│   ├── tools/                # builtin / runtime / mcp（工具层）
│   ├── knowledge/            # index / indexing / embedding / external / qdrant（RAG）
│   ├── storage/              # store / migrations（PostgreSQL 持久化）
│   ├── infra/                # config / llm / factory（基础设施与装配）
│   └── eval/                 # rag_eval / demo_flow（评估与演示）
├── tests/                    # pytest 测试
├── eval/                     # rag_questions.json 评估集
├── docs/
│   ├── runbooks/             # 运维知识库（Markdown）
│   ├── evaluation/           # RAG Eval 与 Agent Run 证据记录
│   └── development/          # 开发规范文档
├── config/                   # config.json / config_template.json
├── scripts/                  # rag_eval.py / demo_incident_flow.py / cls-mcp.sh
├── prometheus_config/        # Prometheus 配置
├── prometheusTestServer/     # 本地 Prometheus 测试服务
├── docker-compose.prometheus.yml
├── pyproject.toml
└── uv.lock
```

## 后续优化方向

- **RAG**：扩充评估集（口语化问题、更多日志场景）、引入 rerank 与向量混合检索
- **工具**：接入更多 MCP 外部工具、工具 Schema 校验与权限边界
- **治理**：Harness 预算控制、评估指标持续跟踪
- **部署**：服务容器化与一键 Compose、接入告警事件源（Alertmanager Webhook）
