# resource_community_go 热榜不更新排障手册

## 适用症状

- `/api/articles/hot` 返回结果长期不变化
- 用户浏览、点赞、评论、收藏后热榜分数没有明显变化
- 热榜接口正常返回 200，但内容不是预期顺序

## 相关链路

热榜由 Redis ZSet 维护，热度来源包括：

- 资源发布：初始化热度
- 资源浏览：增加浏览热度
- 点赞：增加点赞热度
- 评论：增加评论热度
- 收藏：增加收藏热度

浏览、点赞、评论、收藏行为会发布 RabbitMQ 异步任务，由 Worker 消费后更新热度。

## 排查步骤

1. 先确认 `/api/articles/hot` 是否返回 200。如果接口 5xx，按 5xx 错误率手册处理。
2. 查看 Redis 是否可用，热榜依赖 Redis ZSet。
3. 检查 RabbitMQ 队列是否有积压。如果队列积压，互动行为可能已经写入消息队列，但 Worker 尚未更新热度。
4. 查看 Worker 日志，搜索 `process async job failed`、`idempotency begin failed`、`worker delivery channel closed`。
5. 触发一次点赞或收藏后，观察热榜是否变化。如果不变化，重点检查 Worker 是否运行。
6. 如果 Worker 正常但热榜仍不变化，检查文章 ID 是否存在，以及 Redis 中热榜 key 是否被正确写入。

## 常见原因

- Worker 没有启动，RabbitMQ 消息无人消费。
- RabbitMQ 队列积压，热度更新延迟。
- Redis 不可用，热榜写入或读取失败。
- 文章列表或热榜缓存未及时失效，导致前端看到旧数据。
- 幂等记录异常，导致消息被判定为已处理。

## 恢复动作

- 启动或重启 `resource-community-go-worker`。
- 恢复 RabbitMQ 后观察队列积压是否下降。
- 恢复 Redis 后重新触发一次浏览、点赞或收藏事件。
- 如果是缓存旧数据，等待缓存过期或手动清理资源列表和热榜相关缓存 key。

## 验证

恢复后执行以下动作：

1. 请求 `/api/articles/hot` 记录当前排序。
2. 对某篇文章执行点赞或收藏。
3. 等待 Worker 消费完成。
4. 再次请求 `/api/articles/hot`，确认目标文章热度或排序发生变化。

同时观察接口 QPS 和错误率，确认热榜恢复没有引入 5xx。
