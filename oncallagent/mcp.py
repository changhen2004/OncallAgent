from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import httpx


LATEST_PROTOCOL_VERSION = "2024-11-05"


class JsonRpcTransport(Protocol):
    async def request(self, method: str, params: dict | None = None) -> dict:
        pass


class HttpJsonRpcTransport:
    def __init__(self, url: str, timeout: float = 30.0) -> None:
        self.url = url
        self.timeout = timeout
        self._next_id = 1

    async def request(self, method: str, params: dict | None = None) -> dict:
        request_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.url, json=payload)
            response.raise_for_status()
            body = response.json()

        if body.get("error"):
            raise RuntimeError(body["error"])
        return body.get("result", body)


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict
    _transport: JsonRpcTransport | None = field(default=None, compare=False, repr=False)

    async def call(self, arguments: dict) -> str:
        if self._transport is None:
            raise RuntimeError("mcp tool transport is not configured")
        result = await self._transport.request(
            "tools/call",
            {"name": self.name, "arguments": arguments},
        )
        content = result.get("content", [])
        if not content:
            return ""
        return "\n".join(item.get("text", "") for item in content if item.get("type") == "text")


class MCPClient:
    def __init__(
        self,
        transport: JsonRpcTransport,
        *,
        client_name: str = "OnCallAgent",
        client_version: str = "1.0.0",
    ) -> None:
        self.transport = transport
        self.client_name = client_name
        self.client_version = client_version
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        await self.transport.request(
            "initialize",
            {
                "protocolVersion": LATEST_PROTOCOL_VERSION,
                "clientInfo": {"name": self.client_name, "version": self.client_version},
            },
        )
        self._initialized = True

    async def get_tools(self) -> list[MCPTool]:
        await self.initialize()
        result = await self.transport.request("tools/list")
        return [
            MCPTool(
                name=tool["name"],
                description=tool.get("description", ""),
                input_schema=tool.get("inputSchema", {}),
                _transport=self.transport,
            )
            for tool in result.get("tools", [])
        ]
