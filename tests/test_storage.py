from __future__ import annotations

import pytest

from oncallagent.agent.planner import PlanExecuteReplanAgent, PlanStep, ReplanDecision
from oncallagent.agent.chat_agent import ChatAgent, ChatMemory
from oncallagent.agent.harness import (
    AgentState,
    Evidence,
    EvidenceType,
    RunStatus,
    StopReason,
    ToolCallRecord,
    ToolCallStatus,
)
from oncallagent.infra.llm import ChatMessage
from oncallagent.storage.store import ConversationStore


# ------------------------------------------------------------------- Fake Store


class FakeConversationStore:
    """In-memory ConversationStore for unit tests — matches the project's
    Fake-based testing convention (see FakeToolCallingModel, FakeChatAgent)."""

    def __init__(self) -> None:
        self.sessions: set[str] = set()
        self.messages: list[dict] = []
        self.tool_records: list[ToolCallRecord] = []
        self.agent_runs: list[dict] = []
        self.evidence_items: list[Evidence] = []
        self.chat_history: list[dict] = []

    async def ensure_session(self, session_id: str) -> None:
        self.sessions.add(session_id)

    async def save_message(
        self, session_id: str, seq: int, role: str, content: str
    ) -> None:
        self.messages.append(
            {"session_id": session_id, "seq": seq, "role": role, "content": content}
        )

    async def load_recent_messages(
        self, session_id: str, limit: int = 6
    ) -> list[dict]:
        session_msgs = [
            {"seq": m["seq"], "role": m["role"], "content": m["content"]}
            for m in self.messages
            if m["session_id"] == session_id
        ]
        session_msgs.sort(key=lambda m: m["seq"])
        return session_msgs[-limit:]

    async def save_tool_record(
        self, session_id: str, record: ToolCallRecord
    ) -> None:
        self.tool_records.append(record)

    async def load_tool_records(self, session_id: str) -> list[ToolCallRecord]:
        return list(self.tool_records)

    async def save_agent_run(self, state: AgentState, **kwargs) -> None:
        self.agent_runs.append(
            {
                "incident_id": state.incident_id,
                "goal": state.goal,
                "status": state.status,
                "stop_reason": state.stop_reason,
            }
        )

    async def save_evidence(self, evidence: Evidence) -> None:
        self.evidence_items.append(evidence)

    async def save_chat_history(
        self, session_id: str, question: str, answer: str
    ) -> None:
        self.chat_history.append(
            {"session_id": session_id, "question": question, "answer": answer}
        )

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------- Fake Dependencies


class FakeToolCallingModel:
    """Two-turn: first turn returns a tool call, second returns a text answer."""

    def __init__(self) -> None:
        self.calls = 0
        self.seen_messages: list[list[dict]] = []

    async def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
        self.calls += 1
        self.seen_messages.append(messages)
        if self.calls == 1:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "name": "query_internal_docs",
                        "arguments": {"query": "latency"},
                    }
                ],
            }
        return {"content": "use the runbook", "tool_calls": []}


class FakeTool:
    name = "query_internal_docs"
    description = "Search docs"
    input_schema = {"type": "object"}

    async def call(self, arguments: dict) -> str:
        return "runbook result"


# ----------------------------------------------------------------------- Tests


@pytest.mark.anyio
async def test_chat_agent_persists_messages() -> None:
    """Messages are persisted to the store after a successful run."""
    store = FakeConversationStore()
    agent = ChatAgent(model=FakeToolCallingModel(), tools=[FakeTool()], storage=store)

    await agent.chat("latency 怎么处理", session_id="s1")

    saved = [m for m in store.messages if m["session_id"] == "s1"]
    assert len(saved) >= 2
    roles = {m["role"] for m in saved}
    assert "user" in roles
    assert "assistant" in roles


@pytest.mark.anyio
async def test_chat_agent_persists_tool_records() -> None:
    """Tool call records are persisted during execution."""
    store = FakeConversationStore()
    agent = ChatAgent(model=FakeToolCallingModel(), tools=[FakeTool()], storage=store)

    await agent.chat("latency 怎么处理", session_id="s1")

    assert len(store.tool_records) == 1
    assert store.tool_records[0].name == "query_internal_docs"
    assert store.tool_records[0].status == ToolCallStatus.SUCCEEDED


@pytest.mark.anyio
async def test_chat_agent_graceful_without_store() -> None:
    """Storage=None should behave identically to current behaviour."""
    agent = ChatAgent(model=FakeToolCallingModel(), tools=[FakeTool()], storage=None)

    answer = await agent.chat("latency 怎么处理", session_id="s1")

    assert answer == "use the runbook"


@pytest.mark.anyio
async def test_sliding_window_reloads_from_storage() -> None:
    """Pre-populated storage messages are loaded into ChatMemory."""
    store = FakeConversationStore()
    await store.ensure_session("s1")
    await store.save_message("s1", 1, "user", "previous question")
    await store.save_message("s1", 2, "assistant", "previous answer")

    agent = ChatAgent(model=FakeToolCallingModel(), tools=[FakeTool()], storage=store)

    await agent.chat("new question", session_id="s1")

    memory = agent._memories["s1"]
    history = memory.history()
    contents = {msg.content for msg in history}
    assert "previous question" in contents
    assert "previous answer" in contents


@pytest.mark.anyio
async def test_agent_run_is_persisted() -> None:
    """AgentState is saved to the store after the run completes."""
    store = FakeConversationStore()
    agent = ChatAgent(model=FakeToolCallingModel(), tools=[FakeTool()], storage=store)

    result = await agent.run("question", session_id="s1", incident_id="inc-1")

    assert len(store.agent_runs) == 1
    saved = store.agent_runs[0]
    assert saved["incident_id"] == "inc-1"
    assert saved["goal"] == "question"
    assert saved["status"] == RunStatus.STOPPED
    assert saved["stop_reason"] == StopReason.COMPLETED


@pytest.mark.anyio
async def test_chat_agent_sessions_are_independent() -> None:
    """Different sessions don't leak messages into each other."""
    store = FakeConversationStore()
    await store.ensure_session("s1")
    await store.save_message("s1", 1, "user", "hello s1")
    await store.ensure_session("s2")
    await store.save_message("s2", 1, "user", "hello s2")

    s1_msgs = await store.load_recent_messages("s1")
    s2_msgs = await store.load_recent_messages("s2")

    assert len(s1_msgs) == 1 and s1_msgs[0]["content"] == "hello s1"
    assert len(s2_msgs) == 1 and s2_msgs[0]["content"] == "hello s2"


@pytest.mark.anyio
async def test_load_recent_messages_respects_limit() -> None:
    """load_recent_messages only returns the most recent N messages."""
    store = FakeConversationStore()
    await store.ensure_session("s1")
    for i in range(10):
        await store.save_message("s1", i + 1, "user", f"msg{i}")

    recent = await store.load_recent_messages("s1", limit=3)
    assert len(recent) == 3
    assert recent[-1]["content"] == "msg9"


class FakePlanner:
    async def plan(self, query: str) -> list[PlanStep]:
        return [PlanStep(description="check alerts"), PlanStep(description="query docs")]


class FakeExecutor:
    async def execute(self, step: PlanStep) -> str:
        return f"done: {step.description}"


class FakeReplanner:
    async def replan(
        self, query: str, completed: list[str], remaining: list[PlanStep]
    ) -> ReplanDecision:
        if remaining:
            return ReplanDecision(remaining_steps=remaining, final_answer="")
        return ReplanDecision(remaining_steps=[], final_answer="final report")


def test_plan_agent_persists_run_state() -> None:
    """PlanExecuteReplanAgent saves run state to storage."""
    store = FakeConversationStore()
    agent = PlanExecuteReplanAgent(
        FakePlanner(), FakeExecutor(), FakeReplanner(), max_iterations=20, storage=store
    )

    result = agent.run_sync("分析告警")

    assert result.state.stop_reason == StopReason.COMPLETED
    assert len(store.agent_runs) == 1
    assert store.agent_runs[0]["goal"] == "分析告警"
    assert store.agent_runs[0]["status"] == RunStatus.STOPPED
