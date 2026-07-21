from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import httpx

from oncallagent.knowledge import KnowledgeIndex


class RagRetrieverNotConfigured(RuntimeError):
    pass


class Retriever(Protocol):
    def search(self, query: str, limit: int = 3) -> list[Any]:
        pass


@dataclass(frozen=True)
class SimplifiedAlert:
    alert_name: str
    description: str
    state: str
    active_at: str
    duration: str


def current_time_text(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    shanghai = current.astimezone(ZoneInfo("Asia/Shanghai"))
    return (
        "Current time (Asia/Shanghai):\n"
        f"  Format: {shanghai.strftime('%Y-%m-%d %H:%M:%S CST')}\n"
        f"  Unix timestamp (seconds): {int(current.timestamp())}\n"
        f"  Unix timestamp (milliseconds): {int(current.timestamp() * 1000)}\n"
        f"  Unix timestamp (microseconds): {int(current.timestamp() * 1_000_000)}"
    )


def calculate_active_time(active_at: str, now: datetime | None = None) -> str:
    try:
        normalized = active_at.replace("Z", "+00:00")
        active_time = datetime.fromisoformat(normalized)
    except ValueError:
        return "unknown"

    current = now or datetime.now(active_time.tzinfo or timezone.utc)
    duration = current - active_time
    total_seconds = max(0, int(duration.total_seconds()))
    hours = total_seconds // 3600
    minutes = (total_seconds // 60) % 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours}h{minutes}m{seconds}s"
    if minutes > 0:
        return f"{minutes}m{seconds}s"
    return f"{seconds}s"


def simplify_prometheus_alerts(payload: dict[str, Any], now: datetime | None = None) -> list[SimplifiedAlert]:
    seen_alert_names: set[str] = set()
    simplified: list[SimplifiedAlert] = []
    for alert in payload.get("data", {}).get("alerts", []):
        labels = alert.get("labels", {})
        alert_name = labels.get("alertname", "")
        if alert_name in seen_alert_names:
            continue
        seen_alert_names.add(alert_name)
        annotations = alert.get("annotations", {})
        active_at = alert.get("activeAt", "")
        simplified.append(
            SimplifiedAlert(
                alert_name=alert_name,
                description=annotations.get("description", ""),
                state=alert.get("state", ""),
                active_at=active_at,
                duration=calculate_active_time(active_at, now=now),
            )
        )
    return simplified


class PrometheusAlertsTool:
    name = "query_prometheus_alerts"
    description = (
        "Query active alerts from Prometheus alerting system. Use this tool when you need "
        "to check what alerts are currently firing or investigate alert status."
    )
    input_schema = {"type": "object", "properties": {}}

    def __init__(self, url: str, timeout: float = 10.0) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout

    async def call(self, arguments: dict) -> str:
        return await self.run()

    async def run(self) -> str:
        payload = await self._query_alerts()
        alerts = simplify_prometheus_alerts(payload)
        output = {
            "success": True,
            "alerts": [asdict(alert) for alert in alerts],
            "message": f"Successfully retrieved {len(alerts)} active alerts",
        }
        return json.dumps(output, ensure_ascii=False)

    async def _query_alerts(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.url}/api/v1/alerts")
            response.raise_for_status()
            return response.json()


def retrieve_internal_docs(retriever: Retriever | None, query: str) -> list[Any]:
    if retriever is None:
        raise RagRetrieverNotConfigured("rag retriever is not configured")
    return retriever.search(query)


class TimeTool:
    name = "get_current_time"
    description = "Get current system time in Asia/Shanghai and Unix timestamp formats."
    input_schema = {"type": "object", "properties": {}}

    async def call(self, arguments: dict) -> str:
        return current_time_text()


class KnowledgeSearchTool:
    name = "query_internal_docs"
    description = "Search internal documentation and knowledge base for relevant runbook steps."
    input_schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }

    def __init__(self, knowledge: KnowledgeIndex) -> None:
        self.knowledge = knowledge

    async def call(self, arguments: dict) -> str:
        query = str(arguments.get("query", ""))
        results = self.knowledge.search(query)
        return "\n\n".join(result.content for result in results)
