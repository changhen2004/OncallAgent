import json
from datetime import datetime, timedelta, timezone

import pytest

from oncallagent.tools import (
    PrometheusAlertsTool,
    RagRetrieverNotConfigured,
    calculate_active_time,
    current_time_text,
    retrieve_internal_docs,
    simplify_prometheus_alerts,
)


def test_current_time_text_uses_asia_shanghai_and_epoch_formats() -> None:
    now = datetime(2026, 7, 21, 12, 34, 56, 123456, tzinfo=timezone.utc)

    output = current_time_text(now)

    assert "Current time (Asia/Shanghai):" in output
    assert "Format: 2026-07-21 20:34:56 CST" in output
    assert "Unix timestamp (seconds):" in output
    assert "Unix timestamp (milliseconds):" in output
    assert "Unix timestamp (microseconds):" in output


def test_calculate_active_time_matches_go_duration_shape() -> None:
    now = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)
    active_at = (now - timedelta(hours=2, minutes=30, seconds=15)).isoformat().replace("+00:00", "Z")

    assert calculate_active_time(active_at, now=now) == "2h30m15s"
    assert calculate_active_time("not-a-time", now=now) == "unknown"


def test_simplify_prometheus_alerts_deduplicates_by_alertname() -> None:
    now = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)
    active_at = (now - timedelta(seconds=15)).isoformat().replace("+00:00", "Z")
    payload = {
        "data": {
            "alerts": [
                {
                    "labels": {"alertname": "HighErrorRate", "instance": "a"},
                    "annotations": {"description": "5xx too high"},
                    "state": "firing",
                    "activeAt": active_at,
                },
                {
                    "labels": {"alertname": "HighErrorRate", "instance": "b"},
                    "annotations": {"description": "duplicate"},
                    "state": "firing",
                    "activeAt": active_at,
                },
            ]
        }
    }

    alerts = simplify_prometheus_alerts(payload, now=now)

    assert len(alerts) == 1
    assert alerts[0].alert_name == "HighErrorRate"
    assert alerts[0].description == "5xx too high"
    assert alerts[0].duration == "15s"


@pytest.mark.anyio
async def test_prometheus_alerts_tool_returns_go_compatible_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_query(self: PrometheusAlertsTool) -> dict:
        return {"data": {"alerts": []}}

    monkeypatch.setattr(PrometheusAlertsTool, "_query_alerts", fake_query)

    output = await PrometheusAlertsTool("http://prom").run()

    assert json.loads(output) == {
        "success": True,
        "alerts": [],
        "message": "Successfully retrieved 0 active alerts",
    }


def test_retrieve_internal_docs_rejects_missing_retriever() -> None:
    with pytest.raises(RagRetrieverNotConfigured, match="rag retriever is not configured"):
        retrieve_internal_docs(None, "latency")
