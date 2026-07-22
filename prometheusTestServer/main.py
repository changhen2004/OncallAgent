from __future__ import annotations

import asyncio
import logging
import math
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from enum import Enum

import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

LOGGER = logging.getLogger(__name__)
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 2112
HANDLERS = [
    "/api/v1/order",
    "/api/v1/user",
    "/api/v1/payment",
    "/api/v1/inventory",
    "/api/v1/notification",
]
QUEUES = ["order_queue", "notify_queue", "payment_queue"]
HISTOGRAM_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5)


class Scenario(Enum):
    NORMAL = "正常"
    DEGRADED = "降级"
    ALERT = "⚠️  告警"


class TestServerMetrics:
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry()
        self.http_requests_total = Counter(
            "http_requests_total",
            "HTTP 请求总数",
            ["handler", "method", "status_code"],
            registry=self.registry,
        )
        self.http_request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP 请求耗时分布（秒）",
            ["handler", "method"],
            buckets=HISTOGRAM_BUCKETS,
            registry=self.registry,
        )
        self.active_connections = Gauge(
            "active_connections",
            "当前活跃连接数",
            registry=self.registry,
        )
        self.error_rate = Gauge(
            "error_rate_per_minute",
            "每分钟错误率（百分比）",
            ["handler"],
            registry=self.registry,
        )
        self.cpu_usage = Gauge(
            "process_cpu_usage_percent",
            "进程 CPU 使用率（模拟）",
            registry=self.registry,
        )
        self.memory_usage = Gauge(
            "process_memory_bytes",
            "进程内存使用量（字节，模拟）",
            registry=self.registry,
        )
        self.db_pool_used = Gauge(
            "db_pool_connections_used",
            "数据库连接池已用连接数",
            registry=self.registry,
        )
        self.db_pool_max = Gauge(
            "db_pool_connections_max",
            "数据库连接池最大连接数",
            registry=self.registry,
        )
        self.queue_depth = Gauge(
            "message_queue_depth",
            "消息队列积压深度",
            ["queue"],
            registry=self.registry,
        )
        self.db_pool_max.set(100)


def current_scenario(now: datetime) -> Scenario:
    return Scenario.ALERT


def simulate_metrics_once(
    metrics: TestServerMetrics,
    *,
    now: datetime | None = None,
    rng: random.Random | None = None,
) -> None:
    now = now or datetime.now()
    rng = rng or random
    scenario = current_scenario(now)
    LOGGER.info("[%s] 当前场景: %s", now.strftime("%H:%M:%S"), scenario.value)

    base_qps = 50.0
    base_error_pct = 0.01
    base_latency_ms = 80.0

    if scenario == Scenario.DEGRADED:
        base_error_pct = 0.08
        base_latency_ms = 300.0
    elif scenario == Scenario.ALERT:
        base_qps = 120.0
        base_error_pct = 0.35
        base_latency_ms = 1500.0

    cpu_base = 25.0
    if scenario == Scenario.DEGRADED:
        cpu_base = 60.0
    elif scenario == Scenario.ALERT:
        cpu_base = 85.0
    metrics.cpu_usage.set(cpu_base + rng.random() * 10 - 5)

    memory_usage = 200 * 1024 * 1024 + rng.random() * 50 * 1024 * 1024
    if scenario == Scenario.ALERT:
        memory_usage += 300 * 1024 * 1024
    metrics.memory_usage.set(memory_usage)

    db_used = 20.0 + rng.random() * 20
    if scenario == Scenario.ALERT:
        db_used = 90 + rng.random() * 10
    metrics.db_pool_used.set(db_used)

    active_connections = base_qps * (0.8 + rng.random() * 0.4)
    metrics.active_connections.set(active_connections)

    for queue in QUEUES:
        depth = rng.random() * 10
        if scenario == Scenario.ALERT:
            depth = 500 + rng.random() * 200
        elif scenario == Scenario.DEGRADED:
            depth = 50 + rng.random() * 50
        metrics.queue_depth.labels(queue=queue).set(depth)

    for handler in HANDLERS:
        qps = base_qps * (0.5 + rng.random())
        request_count = int(qps)
        error_rate = base_error_pct * (0.5 + rng.random())
        wave = math.sin(now.timestamp() / 10) * 0.2
        latency = base_latency_ms * (1 + wave + rng.random() * 0.3) / 1000.0

        success_count = int(float(request_count) * (1 - error_rate))
        error_count = request_count - success_count
        metrics.http_requests_total.labels(handler, "GET", "200").inc(success_count)
        if error_count > 0:
            metrics.http_requests_total.labels(handler, "GET", "500").inc(error_count)
        metrics.http_request_duration.labels(handler, "GET").observe(latency)
        metrics.error_rate.labels(handler=handler).set(error_rate * 100)


async def simulate_metrics_forever(
    metrics: TestServerMetrics, *, interval_seconds: float = 1.0
) -> None:
    while True:
        simulate_metrics_once(metrics)
        await asyncio.sleep(interval_seconds)


ROOT_TEXT = """Prometheus Test Server 运行中
访问 /metrics 查看指标

场景循环（每 3 分钟）：
  0~90s   : 正常
  90~150s : 轻微降级（错误率 8%，延迟 300ms）
  150~180s: 告警（错误率 35%，延迟 1.5s，CPU 85%，队列积压）
"""


def create_app(
    *,
    metrics: TestServerMetrics | None = None,
    start_background_task: bool = True,
    interval_seconds: float = 1.0,
) -> FastAPI:
    metrics = metrics or TestServerMetrics()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task: asyncio.Task[None] | None = None
        if start_background_task:
            simulate_metrics_once(metrics)
            task = asyncio.create_task(
                simulate_metrics_forever(metrics, interval_seconds=interval_seconds)
            )
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="Prometheus Test Server", lifespan=lifespan)

    @app.get("/", response_class=PlainTextResponse)
    async def root() -> str:
        return ROOT_TEXT

    @app.get("/metrics")
    async def prometheus_metrics() -> Response:
        return Response(
            content=generate_latest(metrics.registry),
            media_type=CONTENT_TYPE_LATEST,
        )

    return app


app = create_app()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    LOGGER.info("Prometheus 测试服务器启动，监听 :%s", LISTEN_PORT)
    LOGGER.info("Prometheus scrape_configs 配置示例：")
    LOGGER.info("  - job_name: 'oncall-test'")
    LOGGER.info("    static_configs:")
    LOGGER.info("      - targets: ['localhost:%s']", LISTEN_PORT)
    uvicorn.run(app, host=LISTEN_HOST, port=LISTEN_PORT)


if __name__ == "__main__":
    main()
