# OnCallAgent

智能运维值班代理系统 - 基于 Python、FastAPI、RAG 检索和 Prometheus 告警查询的智能排障助手。

## 项目简介

OnCallAgent 是一个面向运维场景的智能代理系统，主要解决“告警出现后如何结合实时指标和内部排障文档生成处理建议”的问题。

当前项目重点覆盖三类能力：

- **RAG (检索增强生成)** - 将内部运维文档、告警处理手册转化为可检索的 Markdown 知识库，为 Agent 提供领域知识支撑

- **工具调用** - 接入知识检索和 Prometheus 告警查询，让 Agent 能获取实时上下文

- **告警计划分析** - 查询 Prometheus 活跃告警，匹配知识库文档，并生成降级可用的排障步骤

三者协同工作：RAG 提供知识基础，工具调用提供实时数据，计划分析生成可执行建议，共同实现从告警发现、知识检索到处理建议生成的运维分析链路。

本仓库已准备一组基于 `resource_community_go` 资源社区项目的排障文档，可用于演示真实业务系统的告警分析：

- `docs/runbooks/resource-community-p95-latency.md`
- `docs/runbooks/resource-community-error-rate.md`
- `docs/runbooks/resource-community-hot-ranking.md`
- `docs/runbooks/resource-community-rabbitmq-backlog.md`

## 功能特性

- **智能对话** - 支持多轮会话、知识库命中回复、OpenAI 兼容模型工具调用和流式 SSE 响应
- **知识库管理** - Markdown 文档上传、落盘到 `docs/runbooks/`，并构建本地轻量索引
- **告警分析** - 自动获取 Prometheus 活跃告警，匹配内部处理方案
- **RAG 检索** - 默认基于本地 Markdown 关键词检索；开启外部索引后可接入 Ollama Embedding + Qdrant 向量库
- **工具扩展** - 内置时间、知识库检索、Prometheus 告警工具，并保留 MCP/SSE 日志工具发现能力
- **降级可用** - Prometheus 不可用时仍返回可执行检查建议，便于本地开发和测试
- **实践联动** - 可接入 resource_community_go 的 Prometheus 告警和排障文档，形成“业务系统指标 - 告警 - 知识库 - 分析建议”的闭环

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                      OnCallAgent                            │
├─────────────────────────────────────────────────────────────┤
│  API Layer (FastAPI)                                        │
│  ├── /upload    - 文件上传 & 知识库索引                      │
│  ├── /chat      - 智能对话                                   │
│  ├── /chatStream - 流式对话                                  │
│  └── /plan      - 运维计划分析                               │
├─────────────────────────────────────────────────────────────┤
│  Service Layer                                              │
│  ├── ChatService / ChatAgent       - 对话、SSE 和工具调用     │
│  ├── KnowledgeIndex                - Markdown 本地索引        │
│  ├── ExternalKnowledgeIndexer      - 可选向量索引写入         │
│  └── PlanService / PlanAgent       - 告警分析和计划执行       │
├─────────────────────────────────────────────────────────────┤
│  Tools                                                      │
│  ├── TimeTool                  - 当前时间                    │
│  ├── KnowledgeSearchTool       - 知识库检索                  │
│  ├── PrometheusAlertsTool      - 告警查询                    │
│  └── MCPTool                   - 可选 MCP/SSE 外部工具       │
├─────────────────────────────────────────────────────────────┤
│  Integrations                                                │
│  ├── OpenAI Compatible API     - 可选 LLM 工具调用           │
│  ├── Ollama + Qdrant           - 可选向量索引和检索          │
│  ├── Prometheus                - 告警查询                    │
│  └── MCP/SSE                   - 可选外部日志工具            │
├─────────────────────────────────────────────────────────────┤
│  Storage                                                    │
│  └── docs/runbooks/       - Markdown 知识库文档               │
└─────────────────────────────────────────────────────────────┘
```

## 快速开始

### 前置依赖

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Prometheus (可选，用于告警分析；本仓库 Compose 默认 `http://localhost:9090`，接入 resource_community_go 时通常使用 `http://localhost:9091`)
- OpenAI 兼容 API Key (可选；未配置时使用本地知识库降级回复)
- Ollama + Qdrant (可选；仅开启外部索引时需要)
- MCP/SSE 服务 (可选；用于接入外部日志或云日志工具)

### 安装步骤

1. **克隆项目**

```bash
git clone <repository-url>
cd OnCallAgent
```

2. **安装依赖**

```bash
/home/chg/.local/bin/uv sync
```

3. **配置文件**

复制配置模板并修改：

```bash
cp config/config_template.json config/config.json
```

编辑 `config/config.json`，按需修改 Prometheus、OpenAI、Qdrant 或 MCP 配置。没有配置文件时会回退读取 `config/config_template.json`。

4. **运行服务**

```bash
/home/chg/.local/bin/uv run uvicorn oncallagent.main:app --host localhost --port 8819
```

服务将在 `http://localhost:8819` 启动。

### 使用 Docker Compose 启动 Prometheus 测试环境

```bash
docker compose -f docker-compose.prometheus.yml up -d
```

该 Compose 文件会在本地暴露 `http://localhost:9090`。如果接入 resource_community_go 的可观测性平台，请改用它暴露的 `http://localhost:9091`。

## 配置说明

### config/config.json

```json
{
  "server": {
    "host": "localhost",
    "port": 8819
  },
  "embedder": {
    "host": "127.0.0.1",
    "port": 11434,
    "model": "nomic-embed-text",
    "dimension": 384
  },
  "qdrant": {
    "host": "127.0.0.1",
    "port": 6334,
    "collection": "oncallagent"
  },
  "openai": {
    "api_key": "your-api-key",
    "model": "your-model-name",
    "api_base": "https://api.openai.com/v1"
  },
  "prometheus": {
    "url": "http://localhost:9090"
  },
  "cls_mcp": {
    "base_url": "http://localhost:3100/sse",
    "enabled": true
  }
}
```

| 配置项 | 说明 |
|--------|------|
| `server.host/port` | HTTP 服务地址 |
| `embedder.*` | Ollama Embedding 地址、模型和向量维度；仅外部索引启用时使用 |
| `qdrant.*` | Qdrant 地址和 collection；仅外部索引启用时使用 |
| `openai.*` | OpenAI 兼容 API 配置；配置 `api_key` 后启用 ChatAgent 工具调用 |
| `prometheus.url` | Prometheus 服务地址 |
| `cls_mcp.*` | MCP/SSE 外部工具地址和启用开关 |

如果接入 `resource_community_go` 的可观测性平台，Prometheus 地址应改为：

```json
{
  "prometheus": {
    "url": "http://localhost:9091"
  }
}
```

## API 文档

### 健康检查

```http
GET /ping
```

**响应:**
```json
{"message": "pong"}
```

### 文件上传 (知识库索引)

```http
POST /upload
Content-Type: multipart/form-data

file: <markdown-file>
```

将 Markdown 文档上传到 `docs/runbooks/`，并更新本地轻量知识库索引。只有在应用启动时显式开启外部索引后，才会额外写入 Ollama + Qdrant 向量索引。

**响应:**
```json
{"message": "上传成功"}
```

### 对话

```http
POST /chat
Content-Type: application/json

{
  "question": "如何处理服务下线告警？",
  "id": "session-id"
}
```

**响应:**
```json
{
  "message": "根据知识库，服务下线可能因为服务 panic..."
}
```

### 流式对话

```http
POST /chatStream
Content-Type: application/json

{
  "question": "当前有哪些告警？",
  "id": "session-id"
}
```

**响应:** Server-Sent Events (SSE) 流式数据

```
data: 根据 Prometheus 查询结果...

data: [DONE]
```

### 运维计划分析

```http
GET /plan
```

自动获取 Prometheus 活跃告警，检索内部知识库，生成分析报告。

**响应:**
```json
{
  "message": "获取运维信息成功",
  "data": {
    "lastmsg": "发现 1 个活跃告警。",
    "msgs": ["HighErrorRate: 命中文档 resource-community-error-rate.md，建议按文档处理。"]
  }
}
```

## 接入 resource_community_go 实践

`resource_community_go` 已提供 Prometheus + Grafana 可观测性平台和压测演练脚本。OnCallAgent 可以将它作为一个具体业务系统来做告警分析演示。

### 1. 启动资源社区项目

```bash
cd /home/chg/Go_Project/resource_community_go
docker compose up --build
```

访问地址：

- Backend: `http://localhost:8080`
- Metrics: `http://localhost:8080/metrics`
- Prometheus: `http://localhost:9091`
- Grafana: `http://localhost:3001`

### 2. 运行演练脚本生成指标

```bash
cd /home/chg/Go_Project/resource_community_go
scripts/observability_drill.sh --duration 90 --concurrency 12
```

如果需要验证错误率面板：

```bash
scripts/observability_drill.sh --duration 90 --concurrency 12 --include-error-traffic
```

脚本会在 `docs/evidence/` 下生成演练报告，包含 QPS、P50、P95、错误率和排障案例记录。

### 3. 导入排障文档

本仓库 `docs/runbooks/` 下已经准备了 4 篇社区项目排障文档：

| 文档 | 场景 |
|------|------|
| `resource-community-p95-latency.md` | 接口 P95 延迟过高 |
| `resource-community-error-rate.md` | 5xx 错误率升高 |
| `resource-community-hot-ranking.md` | 热榜不更新 |
| `resource-community-rabbitmq-backlog.md` | RabbitMQ 队列积压 |

通过 `/upload` 接口上传：

```bash
curl -F "file=@docs/runbooks/resource-community-p95-latency.md" http://localhost:8819/upload
curl -F "file=@docs/runbooks/resource-community-error-rate.md" http://localhost:8819/upload
curl -F "file=@docs/runbooks/resource-community-hot-ranking.md" http://localhost:8819/upload
curl -F "file=@docs/runbooks/resource-community-rabbitmq-backlog.md" http://localhost:8819/upload
```

### 4. 触发分析

配置 `config/config.json`：

```json
{
  "prometheus": {
    "url": "http://localhost:9091"
  }
}
```

然后调用：

```bash
curl http://localhost:8819/plan
```

Agent 会先通过 Prometheus 工具查询当前活跃告警，再结合知识库中的排障文档生成分析结果。

## 项目结构

```
OnCallAgent/
├── oncallagent/
│   ├── main.py                 # FastAPI 入口和路由
│   ├── config.py               # 配置加载
│   ├── chat.py                 # 对话服务
│   ├── chat_agent.py           # LLM 工具调用对话代理
│   ├── agent.py                # 计划-执行-重规划代理
│   ├── knowledge.py            # Markdown 本地知识库索引
│   ├── embedding.py            # Ollama Embedding 客户端和向量工具
│   ├── indexing.py             # Markdown 分块和向量点构建
│   ├── external_indexer.py     # 可选外部向量索引器
│   ├── qdrant.py               # Qdrant 向量库客户端
│   ├── llm.py                  # OpenAI 兼容 Chat Completions 客户端
│   ├── mcp.py                  # MCP/SSE 工具发现客户端
│   ├── tools.py                # 内置 Agent 工具
│   ├── tool_runtime.py         # 工具执行、超时和调用记录
│   ├── factory.py              # 可选依赖装配
│   ├── harness.py              # SDD 验证辅助
│   └── plan.py                 # Prometheus 告警计划分析
├── tests/
│   ├── test_api.py             # API 行为测试
│   └── ...                     # Agent、配置、索引、Qdrant、MCP 等测试
├── config/
│   ├── config.json             # 配置文件
│   └── config_template.json    # 配置模板
├── docs/
│   ├── runbooks/               # 运维知识库文档
│   ├── evaluation/             # RAG Eval 和项目证据记录
│   └── development/            # 开发流程和工程规范文档
├── eval/
│   └── rag_questions.json      # RAG 评估问题集
├── scripts/
│   ├── rag_eval.py             # RAG TopK 命中率评估脚本
│   ├── demo_incident_flow.py   # Prometheus -> Runbook -> Agent 演示脚本
│   └── cls-mcp.sh              # CLS MCP 启动脚本
├── prometheus_config/          # Prometheus 配置
├── prometheusTestServer/       # 测试服务器
├── docker-compose.prometheus.yml
├── pyproject.toml
└── uv.lock
```

## 核心组件

### 1. ChatService / ChatAgent (对话服务)

默认基于知识库检索生成回复；配置 OpenAI 兼容 API Key 后启用 ChatAgent 工具调用，支持：
- 会话级内存
- Markdown 文档命中
- SSE 流式输出
- 时间、知识库和 Prometheus 工具调用
- Harness Run 状态记录，包括停止原因、迭代次数和工具调用记录

### 2. PlanService / PlanExecuteReplanAgent (运维计划服务)

默认 PlanService 提供降级可用的告警分析；配置 LLM 后可装配计划-执行-重规划代理。现有服务支持：
- 查询 Prometheus `/api/v1/alerts`
- 识别 firing 告警
- 匹配知识库文档并生成处理建议
- Prometheus 不可用时返回降级检查清单

### 3. KnowledgeIndex / ExternalKnowledgeIndexer (知识库)

默认使用 Markdown 文档的轻量检索：
- 文档上传后保存到 `docs/runbooks/`
- 启动时自动加载已有 Markdown
- 开启 `enable_external_indexing` 后，可通过 Ollama Embedding 将分块写入 Qdrant

### 4. Tools / Integrations (工具和外部集成)

内置工具和外部集成包括：
- `TimeTool`：获取当前时间
- `KnowledgeSearchTool`：检索本地知识库
- `PrometheusAlertsTool`：查询并去重活跃告警
- `MCPTool`：通过 MCP/SSE 发现外部工具，适合接入云日志或专用排障工具

## 可验证内容

推荐的本地验证顺序：

```bash
/home/chg/.local/bin/uv run pytest
docker compose -f docker-compose.prometheus.yml config
/home/chg/.local/bin/uv run python scripts/rag_eval.py --format markdown
/home/chg/.local/bin/uv run python scripts/demo_incident_flow.py
curl http://localhost:9090/api/v1/alerts
curl http://localhost:8819/ping
curl http://localhost:8819/plan
```

接入资源社区项目或外部集成后，可额外验证：

```bash
curl http://localhost:9091/api/v1/alerts
curl http://localhost:6333/collections/oncallagent
curl http://localhost:3100/sse
curl http://localhost:8819/plan
```

## 开发指南

### 添加新工具

在 `oncallagent/` 目录增加服务类，并通过 `create_app()` 注入路由或依赖。新行为必须先补充 `tests/` 下的 API 或服务测试。

### 扩展知识库

将 Markdown 文档放入 `docs/runbooks/` 目录，通过 `/upload` 接口上传。

文档格式建议：
- 使用一级标题作为文档标题
- 标题会获得更高的检索权重
- 保持文档结构清晰

## 技术栈

- **框架**: [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/)
- **依赖管理**: [uv](https://docs.astral.sh/uv/)
- **知识库**: Markdown 本地索引，可选 Ollama Embedding + Qdrant 向量索引
- **LLM**: OpenAI 兼容 Chat Completions API
- **监控**: [Prometheus](https://prometheus.io/)
- **外部工具**: MCP/SSE

## License

MIT
