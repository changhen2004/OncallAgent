# Prometheus 告警 + Runbook + Agent 分析演示流程

## 背景

本流程用于展示 OnCallAgent 的完整排障闭环：Prometheus 告警进入系统后，Agent 根据告警名称和描述检索内部 Runbook，并生成可执行的分析结果。该演示默认使用离线样例 payload，不依赖外部 Prometheus，便于稳定验证和简历取证。

## 运行命令

```bash
/home/chg/.local/bin/uv run python scripts/demo_incident_flow.py
```

如需结构化输出：

```bash
/home/chg/.local/bin/uv run python scripts/demo_incident_flow.py --format json
```

## 当前演示结果

```text
Prometheus firing alerts: 3
Runbook hits: 3
Agent analysis: 发现 3 个活跃告警。
```

命中详情：

- `ResourceCommunityHighP95Latency` -> `resource-community-p95-latency.md`
- `ResourceCommunityHighErrorRate` -> `resource-community-error-rate.md`
- `ResourceCommunityRabbitMQBacklog` -> `resource-community-rabbitmq-backlog.md`

Agent 分析结果：

- ResourceCommunityHighP95Latency: 命中文档 resource-community-p95-latency.md，建议按文档处理。
- ResourceCommunityHighErrorRate: 命中文档 resource-community-error-rate.md，建议按文档处理。
- ResourceCommunityRabbitMQBacklog: 命中文档 resource-community-rabbitmq-backlog.md，建议按文档处理。

## 后续改造方向

- 将离线 payload 替换为真实 `GET /api/v1/alerts` 响应，生成线上演示报告。
- 将 Agent Run 状态中的工具调用记录一起输出到报告中。
- 增加失败场景演示：Prometheus 不可用、Runbook 未命中、工具超时。
