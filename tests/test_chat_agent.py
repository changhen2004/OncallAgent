import pytest

from oncallagent.chat_agent import ChatAgent, ChatMemory
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
