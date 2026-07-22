from __future__ import annotations

import random
from datetime import UTC, datetime

from fastapi.testclient import TestClient


def test_root_endpoint_describes_prometheus_test_server() -> None:
    from prometheusTestServer import main as test_server

    app = test_server.create_app(start_background_task=False)

    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "Prometheus Test Server 运行中" in response.text
    assert "访问 /metrics 查看指标" in response.text


def test_metrics_endpoint_exposes_equivalent_go_metric_names() -> None:
    from prometheusTestServer import main as test_server

    metrics = test_server.TestServerMetrics()
    test_server.simulate_metrics_once(
        metrics,
        now=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
        rng=random.Random(1),
    )
    app = test_server.create_app(metrics=metrics, start_background_task=False)

    response = TestClient(app).get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "http_requests_total" in body
    assert 'handler="/api/v1/order",method="GET",status_code="200"' in body
    assert "http_request_duration_seconds_bucket" in body
    assert "active_connections" in body
    assert "error_rate_per_minute" in body
    assert "process_cpu_usage_percent" in body
    assert "process_memory_bytes" in body
    assert "db_pool_connections_used" in body
    assert "db_pool_connections_max" in body
    assert 'message_queue_depth{queue="order_queue"}' in body


def test_dockerfile_runs_python_test_server_without_go_builder() -> None:
    dockerfile = "prometheusTestServer/Dockerfile"

    with open(dockerfile, encoding="utf-8") as file:
        content = file.read()

    assert "golang" not in content.lower()
    assert "go build" not in content
    assert "main.go" not in content
    assert "python" in content.lower()
    assert "prometheusTestServer/main.py" in content
