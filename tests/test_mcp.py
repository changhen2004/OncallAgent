import pytest

from oncallagent.mcp import JsonRpcTransport, MCPClient, MCPTool


class FakeTransport(JsonRpcTransport):
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def request(self, method: str, params: dict | None = None) -> dict:
        self.requests.append({"method": method, "params": params})
        if method == "initialize":
            return {"protocolVersion": "2024-11-05", "serverInfo": {"name": "cls"}}
        if method == "tools/list":
            return {
                "tools": [
                    {
                        "name": "search_logs",
                        "description": "Search CLS logs",
                        "inputSchema": {"type": "object"},
                    }
                ]
            }
        if method == "tools/call":
            return {"content": [{"type": "text", "text": "log result"}]}
        raise AssertionError(method)


@pytest.mark.anyio
async def test_mcp_client_initializes_and_lists_tools() -> None:
    transport = FakeTransport()
    client = MCPClient(transport, client_name="OnCallAgent", client_version="1.0.0")

    tools = await client.get_tools()

    assert transport.requests[0] == {
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "OnCallAgent", "version": "1.0.0"},
        },
    }
    assert tools == [
        MCPTool(name="search_logs", description="Search CLS logs", input_schema={"type": "object"})
    ]


@pytest.mark.anyio
async def test_mcp_tool_invokes_tools_call() -> None:
    transport = FakeTransport()
    client = MCPClient(transport)
    tool = (await client.get_tools())[0]

    result = await tool.call({"query": "error"})

    assert result == "log result"
    assert transport.requests[-1] == {
        "method": "tools/call",
        "params": {"name": "search_logs", "arguments": {"query": "error"}},
    }
