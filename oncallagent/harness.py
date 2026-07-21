from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum


class RunStatus(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"


class StopReason(StrEnum):
    NONE = ""
    COMPLETED = "completed"
    BUDGET_EXCEEDED = "budget_exceeded"
    TIMEOUT = "timeout"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    TOOL_FAILURE = "tool_failure"
    HUMAN_APPROVAL = "human_approval_required"


@dataclass
class RunUsage:
    iterations: int = 0
    tool_calls: int = 0
    started_at: datetime | None = None


@dataclass(frozen=True)
class RunBudget:
    max_iterations: int = 0
    max_tool_calls: int = 0
    max_duration: timedelta = timedelta(0)

    def check(self, usage: RunUsage) -> tuple[StopReason, bool]:
        if self.max_iterations > 0 and usage.iterations >= self.max_iterations:
            return StopReason.BUDGET_EXCEEDED, False
        if self.max_tool_calls > 0 and usage.tool_calls >= self.max_tool_calls:
            return StopReason.BUDGET_EXCEEDED, False
        if self.max_duration > timedelta(0) and usage.started_at is not None:
            now = datetime.now(usage.started_at.tzinfo or timezone.utc)
            if now - usage.started_at >= self.max_duration:
                return StopReason.TIMEOUT, False
        return StopReason.NONE, True


class EvidenceType(StrEnum):
    ALERT = "alert"
    METRIC = "metric"
    LOG = "log"
    RUNBOOK = "runbook"
    HISTORY = "history"


@dataclass
class Evidence:
    id: str
    type: EvidenceType
    source: str
    summary: str
    score: float = 0.0
    created_at: datetime | None = None


class ToolCallStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ToolCallRecord:
    name: str
    input: str
    output: str
    status: ToolCallStatus
    error: str = ""
    started_at: datetime | None = None
    ended_at: datetime | None = None


@dataclass
class AgentState:
    incident_id: str
    goal: str
    status: RunStatus
    stop_reason: StopReason
    evidence: list[Evidence] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    usage: RunUsage = field(default_factory=RunUsage)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def new(cls, incident_id: str, goal: str) -> AgentState:
        now = datetime.now(timezone.utc)
        return cls(
            incident_id=incident_id,
            goal=goal,
            status=RunStatus.RUNNING,
            stop_reason=StopReason.NONE,
            usage=RunUsage(started_at=now),
            created_at=now,
            updated_at=now,
        )

    def add_evidence(self, evidence: Evidence) -> None:
        if evidence.created_at is None:
            evidence.created_at = datetime.now(timezone.utc)
        self.evidence.append(evidence)
        self.updated_at = datetime.now(timezone.utc)

    def record_tool_call(self, record: ToolCallRecord) -> None:
        self.tool_calls.append(record)
        self.usage.tool_calls += 1
        self.updated_at = datetime.now(timezone.utc)

    def stop(self, reason: StopReason) -> None:
        self.status = RunStatus.STOPPED
        self.stop_reason = reason
        self.updated_at = datetime.now(timezone.utc)
