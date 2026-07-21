# resource_community_go 接口 P95 延迟过高排障手册

## 适用告警

- 告警名：`ResourceCommunityHighP95Latency`
- 触发条件：`resource_community_go` 后端 1 分钟内整体 P95 延迟超过 500ms
- 重点指标：`resource_community_http_request_duration_seconds_bucket`

## 快速判断

优先确认是全站延迟升高，还是单个路由延迟升高。

常用 PromQL：

```promql
histogram_quantile(
  0.95,
  sum(rate(resource_community_http_request_duration_seconds_bucket[1m])) by (le)
)
```

按路由查看：

```promql
histogram_quantile(
  0.95,
  sum(rate(resource_community_http_request_duration_seconds_bucket[1m])) by (path, le)
)
```

## 排查步骤

1. 在 Grafana 的 `P95 Latency By Route` 面板确认慢接口路径。
2. 如果慢接口集中在 `/api/articles` 或 `/api/articles/hot`，优先检查 Redis 是否可用，因为列表和热榜依赖缓存。
3. 如果慢接口集中在 `/api/articles/:id`，检查文章详情缓存是否命中，以及 MySQL 查询是否变慢。
4. 如果所有接口同时变慢，检查 MySQL、Redis、RabbitMQ 容器健康状态和后端容器 CPU、内存。
5. 查看后端日志中的 `latency_ms` 和 `level=WARN` 慢请求记录，确认具体请求路径和状态码。

## 常见原因

- Redis 不可用，资源列表、详情、热榜请求回源 MySQL。
- MySQL 数据量增加后缺少合适索引，分页、关键词搜索或标签筛选变慢。
- RabbitMQ 不可用后，部分业务走同步兜底逻辑，导致主链路耗时增加。
- 本地 Docker 资源不足，多个容器争用 CPU 或内存。

## 恢复动作

- Redis 异常时，先恢复 Redis 容器，再观察 P95 是否下降。
- MySQL 查询慢时，先降低压测流量或缩小分页大小，再检查慢查询和索引。
- RabbitMQ 异常时，恢复 RabbitMQ 后端口和健康检查，确认 Worker 恢复消费。
- 如果只是局部接口慢，优先针对具体路由排查，不要直接重启所有服务。

## 验证

恢复后观察以下指标至少 2 分钟：

```promql
histogram_quantile(
  0.95,
  sum(rate(resource_community_http_request_duration_seconds_bucket[1m])) by (le)
)
```

确认 P95 回到 500ms 以下，并检查错误率没有同步升高。
