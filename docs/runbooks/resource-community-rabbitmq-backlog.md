# resource_community_go RabbitMQ 队列积压排障手册

## 适用症状

- 点赞、浏览、评论、收藏后热度或积分更新延迟
- RabbitMQ 管理台显示 `resource_community_go.async.jobs` 队列消息持续增加
- Worker 日志出现消费失败或反复重试

## 相关链路

后端将部分非关键更新封装为异步任务：

- `article_published`：初始化热度并发放发布积分
- `article_viewed`：记录浏览热度
- `article_liked`：应用点赞计数和热度
- `comment_created`：发放互动积分并增加评论热度
- `favorite_created`：增加收藏热度

Worker 从 RabbitMQ 消费消息，执行成功后 Ack；执行失败时 Nack 并重新入队。

## 排查步骤

1. 打开 RabbitMQ 管理台，确认 `resource_community_go.async.jobs` 的 ready 和 unacked 数量。
2. 如果 ready 持续增加，说明生产速度高于消费速度，或 Worker 未正常消费。
3. 如果 unacked 长时间不下降，说明 Worker 已取到消息但处理卡住或失败。
4. 查看 Worker 日志，重点关注 `process async job failed` 和 `idempotency complete failed`。
5. 检查 Redis 状态，因为 Worker 使用 Redis 做幂等记录。
6. 检查 MySQL 状态，因为热度和积分最终需要落库或查询文章数据。

## 常见原因

- Worker 容器未启动或不断重启。
- Redis 异常导致幂等记录无法创建或完成。
- MySQL 异常导致任务处理失败并被重新入队。
- 某类任务 payload 缺少必要字段，导致处理逻辑反复失败。
- 本地压测流量过大，单个 Worker 消费速度不足。

## 恢复动作

- 先恢复 Worker 容器，确认它能稳定连接 RabbitMQ。
- 如果 Redis 异常，恢复 Redis 后重启 Worker，避免幂等状态异常影响消费。
- 如果 MySQL 异常，优先恢复 MySQL，再观察 Nack 是否停止。
- 如果某类消息反复失败，需要从日志确认 job type 和 payload，修复处理逻辑后再恢复消费。
- 本地演练中如果积压过多，可以先停止流量，再等待 Worker 追平。

## 验证

确认以下状态：

- RabbitMQ 队列 ready 数量持续下降
- unacked 数量没有长期卡住
- Worker 日志不再持续出现 `process async job failed`
- 点赞、评论、收藏后热榜和积分能在短时间内更新

关联观察：

```promql
sum(rate(resource_community_http_requests_total[1m])) by (path)
```

如果 QPS 已下降但队列仍不下降，重点排查 Worker 和下游依赖。
