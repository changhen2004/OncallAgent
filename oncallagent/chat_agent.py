from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Protocol

from oncallagent.harness import ToolCallRecord
from oncallagent.llm import ChatMessage
from oncallagent.tool_runtime import ToolExecutor


class Tool(Protocol):
    name: str
    description: str
    input_schema: dict

    async def call(self, arguments: dict) -> str:
        pass


class ToolCallingModel(Protocol):
    async def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
        pass


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class ToolResult:
    tool_call_id: str
    name: str
    content: str


class ChatMemory:
    def __init__(self, max_window_size: int = 6) -> None:
        self.max_window_size = max_window_size if max_window_size > 0 else 6
        self._messages: list[ChatMessage] = []

    def append(self, message: ChatMessage) -> None:
        self._messages.append(message)
        if len(self._messages) > self.max_window_size:
            self._messages = self._messages[-self.max_window_size :]

    def history(self) -> list[ChatMessage]:
        return list(self._messages)


class ChatAgent:
    def __init__(
        self,
        model: ToolCallingModel,
        tools: list[Tool],
        *,
        max_iterations: int = 8,
        tool_timeout_seconds: float = 10.0,
    ) -> None:
        self.model = model
        self.tools = {tool.name: tool for tool in tools}
        self.tool_executor = ToolExecutor(tools, timeout_seconds=tool_timeout_seconds)
        self.max_iterations = max_iterations
        self._memories: dict[str, ChatMemory] = defaultdict(ChatMemory)
        self._tool_records: dict[str, list[ToolCallRecord]] = defaultdict(list)

    async def chat(self, question: str, session_id: str) -> str:
        memory = self._memories[session_id]
        messages = [self._message_to_dict(message) for message in memory.history()]
        messages.append({"role": "user", "content": question})
        tool_specs = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in self.tools.values()
        ]

        answer = ""
        for _ in range(self.max_iterations):
            response = await self.model.chat_with_tools(messages, tool_specs)
            answer = response.get("content", "")
            tool_calls = [self._normalize_tool_call(call) for call in response.get("tool_calls", [])]
            if not tool_calls:
                memory.append(ChatMessage(role="user", content=question))
                memory.append(ChatMessage(role="assistant", content=answer))
                return answer

            messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments, ensure_ascii=False),
                            },
                        }
                        for call in tool_calls
                    ],
                }
            )
            for call in tool_calls:
                result = await self._call_tool(call, session_id)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": result.tool_call_id,
                        "name": result.name,
                        "content": result.content,
                    }
                )

        memory.append(ChatMessage(role="user", content=question))
        memory.append(ChatMessage(role="assistant", content=answer))
        return answer

    def tool_call_records(self, session_id: str) -> list[ToolCallRecord]:
        return list(self._tool_records[session_id])

    async def _call_tool(self, call: ToolCall, session_id: str) -> ToolResult:
        execution = await self.tool_executor.execute(call.id, call.name, call.arguments)
        self._tool_records[session_id].append(execution.record)
        return ToolResult(call.id, call.name, execution.content)

    @staticmethod
    def _message_to_dict(message: ChatMessage) -> dict:
        return {"role": message.role, "content": message.content}

    @staticmethod
    def _normalize_tool_call(call: dict) -> ToolCall:
        raw_arguments = call.get("arguments", {})
        if isinstance(raw_arguments, str):
            arguments = json.loads(raw_arguments or "{}")
        else:
            arguments = raw_arguments
        return ToolCall(id=call.get("id", ""), name=call.get("name", ""), arguments=arguments)
