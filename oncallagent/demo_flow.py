from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from oncallagent.knowledge import KnowledgeIndex
from oncallagent.plan import PlanReport, PlanService
from oncallagent.tools import simplify_prometheus_alerts

SAMPLE_PROMETHEUS_ALERTS: dict[str, Any] = {
    "status": "success",
    "data": {
        "alerts": [
            {
                "labels": {"alertname": "ResourceCommunityHighP95Latency"},
                "annotations": {
                    "description": (
                        "resource_community_go 后端 P95 延迟超过 500ms，"
                        "resource_community_http_request_duration_seconds_bucket 异常。"
                    )
                },
                "state": "firing",
                "activeAt": "2026-07-23T10:00:00Z",
            },
            {
                "labels": {"alertname": "ResourceCommunityHighErrorRate"},
                "annotations": {
                    "description": (
                        "resource_community_go 1 分钟内 5xx 错误率超过 5%，"
                        "resource_community_http_requests_total status=5xx 持续升高。"
                    )
                },
                "state": "firing",
                "activeAt": "2026-07-23T10:01:00Z",
            },
            {
                "labels": {"alertname": "ResourceCommunityRabbitMQBacklog"},
                "annotations": {
                    "description": (
                        "resource_community_go.async.jobs 队列 ready 消息持续增加，"
                        "Worker 消费延迟导致热度和积分更新滞后。"
                    )
                },
                "state": "firing",
                "activeAt": "2026-07-23T10:02:00Z",
            },
        ]
    },
}


@dataclass(frozen=True)
class DemoRunbookHit:
    alert_name: str
    description: str
    runbook: str
    score: int


@dataclass(frozen=True)
class DemoFlowReport:
    alert_count: int
    runbook_hit_count: int
    runbook_hits: list[DemoRunbookHit]
    plan_report: PlanReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_count": self.alert_count,
            "runbook_hit_count": self.runbook_hit_count,
            "runbook_hits": [asdict(hit) for hit in self.runbook_hits],
            "agent_analysis": asdict(self.plan_report),
        }

    def to_markdown(self) -> str:
        lines = [
            "# OnCallAgent Incident Demo Flow",
            "",
            "## 1. Prometheus Firing Alerts",
            "",
        ]
        for hit in self.runbook_hits:
            lines.append(f"- `{hit.alert_name}`: {hit.description}")

        lines.extend(["", "## 2. Runbook Retrieval Hits", ""])
        for hit in self.runbook_hits:
            lines.append(
                f"- `{hit.alert_name}` -> `{hit.runbook}` "
                f"(keyword score: {hit.score})"
            )

        lines.extend(["", "## 3. Agent Analysis Result", ""])
        lines.append(self.plan_report.lastmsg)
        lines.append("")
        for message in self.plan_report.msgs:
            lines.append(f"- {message}")
        return "\n".join(lines)


def build_demo_flow_report(
    *,
    docs_dir: str | Path = "docs/runbooks",
    prometheus_payload: dict[str, Any] | None = None,
) -> DemoFlowReport:
    payload = prometheus_payload or SAMPLE_PROMETHEUS_ALERTS
    knowledge = KnowledgeIndex(docs_dir)
    active_alerts = [
        alert for alert in simplify_prometheus_alerts(payload) if alert.state == "firing"
    ]
    runbook_hits: list[DemoRunbookHit] = []
    for alert in active_alerts:
        alert_name = alert.alert_name or "unknown"
        query = f"{alert_name} {alert.description or alert_name}"
        matches = knowledge.search(query, limit=1)
        if not matches:
            continue
        runbook_hits.append(
            DemoRunbookHit(
                alert_name=alert_name,
                description=alert.description,
                runbook=matches[0].filename,
                score=matches[0].score,
            )
        )

    plan_report = PlanService("http://offline-prometheus", knowledge).plan_from_payload(payload)
    return DemoFlowReport(
        alert_count=len(active_alerts),
        runbook_hit_count=len(runbook_hits),
        runbook_hits=runbook_hits,
        plan_report=plan_report,
    )


def dumps_demo_flow_json(report: DemoFlowReport) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
