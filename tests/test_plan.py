from datetime import datetime, timedelta, timezone

import pytest

from oncallagent.knowledge import KnowledgeIndex
from oncallagent.plan import PlanService
from oncallagent.tools import PrometheusAlertsTool


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
