from __future__ import annotations

from dataclasses import asdict, dataclass

import httpx


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


class OpenAICompatibleChatModel:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        api_base: str,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout

    def build_payload(self, messages: list[ChatMessage]) -> dict:
        return {
            "model": self.model,
            "messages": [asdict(message) for message in messages],
        }

    async def chat(self, messages: list[ChatMessage]) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                json=self.build_payload(messages),
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
        return payload["choices"][0]["message"]["content"]

    async def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
        request = {"model": self.model, "messages": messages}
        if tools:
            request["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {"type": "object"}),
                    },
                }
                for tool in tools
            ]
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                json=request,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()

        message = payload["choices"][0]["message"]
        return {
            "content": message.get("content") or "",
            "tool_calls": [
                {
                    "id": call.get("id", ""),
                    "name": call.get("function", {}).get("name", ""),
                    "arguments": call.get("function", {}).get("arguments", {}),
                }
                for call in message.get("tool_calls", []) or []
            ],
        }
