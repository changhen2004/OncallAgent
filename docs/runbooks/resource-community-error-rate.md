# resource_community_go 5xx 错误率升高排障手册

## 适用告警

- 告警名：`ResourceCommunityHighErrorRate`
- 触发条件：`resource_community_go` 1 分钟内 5xx 错误率超过 5%
- 重点指标：`resource_community_http_requests_total`

## 快速判断

先确认错误率是否真实升高，再定位是哪个路由产生 5xx。

整体 5xx 错误率：

```promql
(
  sum(rate(resource_community_http_requests_total{status=~"5.."}[1m]))
  /
  clamp_min(sum(rate(resource_community_http_requests_total[1m])), 0.001)
) * 100
```

按路由查看 5xx：

```promql
sum(rate(resource_community_http_requests_total{status=~"5.."}[1m])) by (path)
```

## 排查步骤

1. 在 Grafana 查看 `QPS By Status`，确认 5xx 是否持续出现。
2. 用按路由 PromQL 找出 5xx 来源路径。
3. 查看后端日志中的 `level=ERROR`、`status=500` 和 `errors` 字段。
4. 如果错误集中在登录、注册、资源发布、积分解锁等写接口，优先检查 MySQL 连接和表结构迁移状态。
5. 如果错误集中在点赞、评论、收藏等互动接口，检查 Redis 和 RabbitMQ 是否可用。
6. 如果 `/metrics` 或 `/healthz` 正常，但业务接口 5xx，说明后端进程未崩溃，应继续定位依赖或业务逻辑。

## 常见原因

- MySQL 容器未就绪、连接串错误或账号权限错误。
- Redis 连接异常，导致限流、缓存或积分相关逻辑失败。
- RabbitMQ 连接异常，异步任务发布失败并触发同步兜底，兜底逻辑又遇到数据库错误。
- 请求参数不符合预期但被错误处理为 500，需要检查 handler 的错误映射。

## 恢复动作

- MySQL 异常：确认 `resource-community-go-mysql` 健康状态，必要时查看容器日志。
- Redis 异常：确认 `resource-community-go-redis` 健康状态，检查端口和密码配置。
- RabbitMQ 异常：确认 `resource-community-go-rabbitmq` 健康状态，查看管理台队列和连接状态。
- 参数导致的 500：补充参数校验或错误码映射，将客户端错误返回 4xx。

## 验证

恢复后执行：

```promql
sum(rate(resource_community_http_requests_total{status=~"5.."}[1m])) by (path)
```

确认 5xx QPS 回到 0，随后观察整体错误率至少 2 分钟。
