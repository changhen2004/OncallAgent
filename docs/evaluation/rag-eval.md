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
