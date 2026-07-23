# Harness 接入真实 Agent Run 记录

## 背景

OnCallAgent 已有 `AgentState`、`RunBudget`、`ToolCallRecord` 等 Harness 结构，但此前真实 `ChatAgent` 调用链路只返回文本答案，工具调用记录停留在 Agent 内部，无法形成完整 Run 证据。本次改造将 Harness 状态接入真实 Agent 执行路径。

## 已落地方向

- `ChatAgent.run(question, session_id, incident_id)` 返回 `ChatAgentRunResult`
- `ChatAgentRunResult.state` 包含本次运行目标、状态、停止原因、迭代次数和工具调用次数
- 每次真实工具调用都会写入 `AgentState.tool_calls`
- `chat(question, session_id)` 保持兼容，内部复用 `run()` 并只返回答案
- 达到最大迭代次数时，Run 以 `budget_exceeded` 停止原因结束
- 正常完成时，Run 以 `completed` 停止原因结束

## 当前记录字段

- `incident_id`：本次事件或会话标识
- `goal`：用户问题或运维目标
- `status`：`running` / `stopped`
- `stop_reason`：`completed` / `budget_exceeded` / `timeout` 等
- `usage.iterations`：模型循环次数
- `usage.tool_calls`：工具调用次数
- `tool_calls`：工具名、输入、输出摘要、状态、错误类型、耗时和起止时间

## 验证命令

```bash
/home/chg/.local/bin/uv run pytest tests/test_chat_agent.py tests/test_tool_runtime.py tests/test_harness.py
```

## 后续改造方向

- 将 `PlanExecuteReplanAgent` 每一步执行产生的 ChatAgent Run 状态合并到总状态。
- 增加只读调试接口，按 session 查询最近一次 Agent Run 记录。
- 将工具失败记录转为可检索 Evidence，支撑后续 Replan 和证据审查。
