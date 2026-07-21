from datetime import datetime, timedelta, timezone

from oncallagent.harness import (
    AgentState,
    Evidence,
    EvidenceType,
    RunBudget,
    RunStatus,
    RunUsage,
    StopReason,
    ToolCallRecord,
    ToolCallStatus,
)


def test_run_budget_allows_work_within_limits() -> None:
    budget = RunBudget(max_iterations=2, max_tool_calls=2, max_duration=timedelta(seconds=5))
    usage = RunUsage(iterations=1, tool_calls=1, started_at=datetime.now(timezone.utc))

    reason, allowed = budget.check(usage)

    assert reason == StopReason.NONE
    assert allowed is True


def test_run_budget_stops_when_limits_are_reached() -> None:
    started_at = datetime.now(timezone.utc) - timedelta(seconds=10)

    assert RunBudget(max_iterations=2).check(RunUsage(iterations=2)) == (
        StopReason.BUDGET_EXCEEDED,
        False,
    )
    assert RunBudget(max_tool_calls=2).check(RunUsage(tool_calls=2)) == (
        StopReason.BUDGET_EXCEEDED,
        False,
    )
    assert RunBudget(max_duration=timedelta(seconds=1)).check(RunUsage(started_at=started_at)) == (
        StopReason.TIMEOUT,
        False,
    )


def test_agent_state_records_evidence_tool_calls_and_stop_reason() -> None:
    state = AgentState.new("inc-1", "分析 HighLatency 告警")

    state.add_evidence(Evidence(id="e1", type=EvidenceType.ALERT, source="prom", summary="firing"))
    state.record_tool_call(
        ToolCallRecord(
            name="query_prometheus_alerts",
            input="{}",
            output='{"success":true}',
            status=ToolCallStatus.SUCCEEDED,
        )
    )
    state.stop(StopReason.COMPLETED)

    assert state.status == RunStatus.STOPPED
    assert state.stop_reason == StopReason.COMPLETED
    assert len(state.evidence) == 1
    assert len(state.tool_calls) == 1
    assert state.usage.tool_calls == 1
