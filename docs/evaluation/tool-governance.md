# Agent 工具治理记录

## 背景

`/home/chg/项目优化文档.md` 建议 OnCallAgent 从“能调用工具”升级为“工具调用可控、可观测、可兜底”。本次改造先落地最小闭环：统一工具执行入口、调用记录、超时控制、错误分类和输入 schema 校验。

## 已落地方向

- 统一入口：`oncallagent/tool_runtime.py` 的 `ToolExecutor`
- 调用记录：每次工具调用生成 `ToolCallRecord`
- 记录字段：工具名、输入 JSON、输出摘要、状态、错误类型、错误信息、开始时间、结束时间、耗时
- 错误分类：`not_configured`、`invalid_input`、`timeout`、`exception`
- 兜底策略：工具失败不抛出到 Agent 主流程，而是返回结构化失败 JSON 作为 tool message
- ChatAgent 接入：`ChatAgent.tool_call_records(session_id)` 可查看指定会话的工具调用记录

## 验证命令

```bash
/home/chg/.local/bin/uv run pytest tests/test_tool_runtime.py tests/test_chat_agent.py tests/test_harness.py
```

## 后续改造方向

- 将工具调用记录接入 `AgentState`，形成完整 Agent Run 证据链。
- 为 Prometheus、RAG、MCP 工具补充更细粒度的输入 schema。
- 在 `/chat` 或调试接口中按需暴露工具调用摘要，便于演示和排障。
- 对工具调用失败率、平均耗时和超时次数增加 Prometheus 指标。
