from __future__ import annotations

import subprocess
import sys


def test_demo_flow_report_connects_alerts_runbooks_and_agent_analysis() -> None:
    from oncallagent.demo_flow import build_demo_flow_report

    report = build_demo_flow_report(docs_dir="docs/runbooks")
    markdown = report.to_markdown()

    assert report.alert_count == 3
    assert report.runbook_hit_count == 3
    assert "ResourceCommunityHighP95Latency" in markdown
    assert "ResourceCommunityHighErrorRate" in markdown
    assert "ResourceCommunityRabbitMQBacklog" in markdown
    assert "resource-community-p95-latency.md" in markdown
    assert "resource-community-error-rate.md" in markdown
    assert "resource-community-rabbitmq-backlog.md" in markdown
    assert "发现 3 个活跃告警。" in markdown


def test_demo_flow_script_runs_from_repo_root() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/demo_incident_flow.py"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# OnCallAgent Incident Demo Flow" in result.stdout
    assert "## 1. Prometheus Firing Alerts" in result.stdout
    assert "## 2. Runbook Retrieval Hits" in result.stdout
    assert "## 3. Agent Analysis Result" in result.stdout
