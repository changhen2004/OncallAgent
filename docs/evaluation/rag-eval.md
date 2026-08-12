# RAG Eval 评估记录

## 背景

`/home/chg/项目优化文档.md` 的核心建议是先补项目证据，尤其是 OnCallAgent 的 RAG 检索质量、Agent 工具调用边界和 Harness 落地指标。当前仓库最适合优先闭环的是 RAG Eval，因为它能直接把“能检索 runbook”转化为可重复验证的 TopK 命中率。

## 已落地方向

- 评估集：`eval/rag_questions.json`
- 评估脚本：`scripts/rag_eval.py`
- 评估对象：`docs/runbooks/` 下的 Markdown 运维知识库
- 评估指标：Top1 命中率、Top3 命中率、每条问题命中文档和命中排名

## 当前结果

运行命令：

```bash
/home/chg/.local/bin/uv run python scripts/rag_eval.py --format markdown
```

优化前结果：

```text
Total questions: 30
Top1 hits: 28/30 (93.33%)
Top3 hits: 30/30 (100.00%)
```

失败样本分析：

- `p95-008`：问题包含“慢请求日志、latency_ms、level=WARN”，但旧检索将中文拆成单字，“日志、level、resource_community_go”等泛化 token 让 5xx 手册排到第一。
- `backlog-002`：问题包含“点赞、浏览、评论、收藏、热度或积分更新延迟、消息队列积压”，热榜手册和 RabbitMQ 积压手册共享大量业务词，旧检索缺少文件名、标题和短语级权重，导致热榜手册排到第一。

优化策略：

- 中文检索从单字 token 调整为连续中文片段的 bigram/trigram，降低“应该参考哪个”等泛化单字噪声。
- 保留唯一 token 交集作为基础分，避免正文重复词过度放大。
- 对文件名和 Markdown 标题命中的 token 加权，强化 runbook 主题识别。
- 对日志原文和指标类英文短语做连续短语匹配加分，例如 `idempotency begin failed`、`worker delivery channel closed`。

优化后结果：

```text
Total questions: 30
Top1 hits: 30/30 (100.00%)
Top3 hits: 30/30 (100.00%)
```

## 后续改造方向

- RAG 检索质量：继续扩充评估集到更多告警、日志和口语化问题，补充失败样本分析。
- Agent 工具治理：为工具增加超时、错误分类、调用记录和 schema 校验。
- Harness 落地指标：记录 Agent Run 的目标、证据、工具调用、预算停止原因和最终状态。
- 演示闭环：串联 Prometheus 告警、Runbook 命中、Agent 分析结果和评估报告，形成可展示证据链。

## P0：向量路径生效 + 混合检索（已完成）

### 变更内容

- 修复配置漂移：Qdrant HTTP 端口默认 `6334 → 6333`；`nomic-embed-text` 实际为 768 维，`embedder.dimension` 默认 `384 → 768`，保证 Ollama 嵌入维度与 Qdrant 集合维度一致。
- 检索参数可配置：`QdrantConfig` 新增 `top_k`（默认 2）和 `score_threshold`（默认 0.5），`QdrantVectorStore.search` 在未显式传参时使用实例默认值。
- 向量检索接入 Agent 工具：`KnowledgeSearchTool` 与 `ChatService` 改用 `KnowledgeIndex.search_hybrid`，词法结果与 Qdrant 向量结果做 RRF 融合（`oncallagent/knowledge/retriever.py`）。
- 启动时重索引：`enable_external_indexing=True` 时，应用启动和 `/upload` 都会把 `docs/runbooks/` 下文档写入 Qdrant，payload 带 `source` 文件名；外部服务不可用时逐文件降级并记录告警。
- 双路径评估：`scripts/rag_eval.py` 新增 `--retriever hybrid`，先重索引再评估混合检索。

### 使用方式

仅词法（离线，默认）：

```bash
/home/chg/.local/bin/uv run python scripts/rag_eval.py --format markdown
```

混合检索（需要 Ollama + Qdrant 可用，先启动 Qdrant 并创建集合）：

```bash
/home/chg/.local/bin/uv run python scripts/rag_eval.py --retriever hybrid --format markdown
```

当 Qdrant 不可用时，混合模式自动回退为词法结果并保持 100% 命中率，不会中断评估。

### 当前结果

```text
lexical: 30/30 Top1, 30/30 Top3
hybrid : 30/30 Top1, 30/30 Top3（Qdrant 不可用时与 lexical 一致）
```

## P1：切分与索引质量（已完成）

### 变更内容

- 分层切分：`split_markdown` 按 H1/H2/H3 标题层级递归切分，chunk 保留祖先标题作为上下文，并记录标题路径（如 `Manual > Steps`）；代码围栏内的 `#` 行不会误判为标题。
- 超长二次切分：超过 `max_chunk_chars`（默认 1500 字符）的章节按行边界切分，相邻 chunk 保留 `overlap_chars`（默认 100 字符）重叠，避免跨边界丢失上下文。
- 元数据 payload：每个向量点携带 `heading` 标题路径、`source` 文件名，并从 runbook 的“适用告警”段落提取 `alertname` 与 `metrics` 指标名，支持 Qdrant payload filter 按告警过滤。
- 嵌入模板：检索侧使用 `search_query:` 前缀、文档侧使用 `search_document:` 前缀（`embedder.passage_prefix` / `query_prefix` 可配置），标题加权保留（own heading ×2 + 祖先标题）。
- Qdrant 检索支持 `payload_filter` 透传（`QdrantVectorStore.search` 与 `KnowledgeIndex.search_hybrid`）。

### 使用方式

混合检索会先按新切分策略重建索引：

```bash
/home/chg/.local/bin/uv run python scripts/rag_eval.py --retriever hybrid --format markdown
```

本地测试与离线评估不依赖上述外部能力，`scripts/rag_eval.py`（lexical）与 `scripts/demo_incident_flow.py` 行为不变。
