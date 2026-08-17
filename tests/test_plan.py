from datetime import datetime, timedelta, timezone

import pytest

from oncallagent.knowledge.index import KnowledgeIndex
from oncallagent.agent.harness import AgentState, StopReason
from oncallagent.agent.planner import AgentRunResult
from oncallagent.services.plan import PlanService
from oncallagent.tools.builtin import PrometheusAlertsTool


class FakePlanAgent:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.incident_ids: list[str] = []

    async def run(self, query: str, incident_id: str = "plan") -> AgentRunResult:
        self.queries.append(query)
        self.incident_ids.append(incident_id)
        state = AgentState.new(incident_id, query)
        state.stop(StopReason.COMPLETED)
        return AgentRunResult(
            last_message="P-E-R final",
            details=["planned", "executed", "replanned"],
            state=state,
        )


@pytest.mark.anyio
async def test_plan_uses_simplified_deduplicated_prometheus_alerts(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "error.md").write_text("# HighErrorRate\nCheck 5xx dashboard.", encoding="utf-8")
    now = datetime.now(timezone.utc)
    active_at = (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")

    async def fake_query(self: PrometheusAlertsTool) -> dict:
        return {
            "data": {
                "alerts": [
                    {
                        "labels": {"alertname": "HighErrorRate"},
                        "annotations": {"description": "5xx too high"},
                        "state": "firing",
                        "activeAt": active_at,
                    },
                    {
                        "labels": {"alertname": "HighErrorRate"},
                        "annotations": {"description": "duplicate"},
                        "state": "firing",
                        "activeAt": active_at,
                    },
                ]
            }
        }

    monkeypatch.setattr(PrometheusAlertsTool, "_query_alerts", fake_query)
    service = PlanService("http://prom", KnowledgeIndex(docs))

    report = await service.plan()

    assert report.lastmsg == "发现 1 个活跃告警。"
    assert len(report.msgs) == 1
    assert "HighErrorRate" in report.msgs[0]
    assert "error.md" in report.msgs[0]


@pytest.mark.anyio
async def test_plan_enters_plan_execute_replan_when_agent_is_available(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_query(self: PrometheusAlertsTool) -> dict:
        return {
            "data": {
                "alerts": [
                    {
                        "labels": {"alertname": "HighLatency"},
                        "annotations": {"description": "p95 latency too high"},
                        "state": "firing",
                    }
                ]
            }
        }

    monkeypatch.setattr(PrometheusAlertsTool, "_query_alerts", fake_query)
    agent = FakePlanAgent()
    service = PlanService("http://prom", KnowledgeIndex(tmp_path), agent=agent)

    report = await service.plan()

    assert report.lastmsg == "P-E-R final"
    assert report.msgs == ["planned", "executed", "replanned"]
    assert agent.incident_ids == ["plan"]
    assert "HighLatency" in agent.queries[0]
    assert "p95 latency too high" in agent.queries[0]
