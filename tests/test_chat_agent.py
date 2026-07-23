import pytest

from oncallagent.chat_agent import ChatAgent, ChatMemory
from oncallagent.harness import RunStatus, StopReason
from oncallagent.llm import ChatMessage


def test_chat_memory_keeps_last_window_messages() -> None:
    memory = ChatMemory(max_window_size=3)

    for index in range(5):
        memory.append(ChatMessage(role="user", content=f"m{index}"))

    assert [message.content for message in memory.history()] == ["m2", "m3", "m4"]


class FakeToolCallingModel:
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
        assert arguments == {"query": "latency"}
        return "runbook result"


@pytest.mark.anyio
async def test_chat_agent_executes_tool_calls_and_returns_final_answer() -> None:
    model = FakeToolCallingModel()
    agent = ChatAgent(model=model, tools=[FakeTool()])

    answer = await agent.chat("latency 怎么处理", session_id="s1")

    assert answer == "use the runbook"
    assert model.calls == 2
    assert model.seen_messages[-1][-1] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "name": "query_internal_docs",
        "content": "runbook result",
    }
    records = agent.tool_call_records("s1")
    assert len(records) == 1
    assert records[0].name == "query_internal_docs"
    assert records[0].status == "succeeded"


@pytest.mark.anyio
async def test_chat_agent_run_returns_harness_state_with_real_tool_records() -> None:
    model = FakeToolCallingModel()
    agent = ChatAgent(model=model, tools=[FakeTool()])

    result = await agent.run("latency 怎么处理", session_id="s1", incident_id="inc-1")

    assert result.answer == "use the runbook"
    assert result.state.incident_id == "inc-1"
    assert result.state.goal == "latency 怎么处理"
    assert result.state.status == RunStatus.STOPPED
    assert result.state.stop_reason == StopReason.COMPLETED
    assert result.state.usage.iterations == 2
    assert result.state.usage.tool_calls == 1
    assert len(result.state.tool_calls) == 1
    assert result.state.tool_calls[0].name == "query_internal_docs"


@pytest.mark.anyio
async def test_chat_agent_run_stops_with_budget_reason_when_iterations_exhausted() -> None:
    class LoopingModel:
        async def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
            return {
                "content": "need more tools",
                "tool_calls": [
                    {
                        "id": "call-loop",
                        "name": "query_internal_docs",
                        "arguments": {"query": "latency"},
                    }
                ],
            }

    agent = ChatAgent(model=LoopingModel(), tools=[FakeTool()], max_iterations=1)

    result = await agent.run("latency 怎么处理", session_id="s1")

    assert result.answer == "need more tools"
    assert result.state.status == RunStatus.STOPPED
    assert result.state.stop_reason == StopReason.BUDGET_EXCEEDED
    assert result.state.usage.iterations == 1
    assert result.state.usage.tool_calls == 1
