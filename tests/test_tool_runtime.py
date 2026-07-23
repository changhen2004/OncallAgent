from __future__ import annotations

import json
import asyncio

import pytest

from oncallagent.harness import ToolCallStatus


class EchoTool:
    name = "echo"
    description = "Echo query"
    input_schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }

    async def call(self, arguments: dict) -> str:
        return f"result:{arguments['query']}"


class FailingTool:
    name = "fail"
    description = "Fail"
    input_schema = {"type": "object", "properties": {}}

    async def call(self, arguments: dict) -> str:
        raise RuntimeError("boom")


class SlowTool:
    name = "slow"
    description = "Slow"
    input_schema = {"type": "object", "properties": {}}

    async def call(self, arguments: dict) -> str:
        await asyncio.sleep(0.05)
        return "late"


@pytest.mark.anyio
async def test_tool_executor_records_success_with_input_output_and_duration() -> None:
    from oncallagent.tool_runtime import ToolExecutor

    executor = ToolExecutor([EchoTool()], timeout_seconds=1.0)

    result = await executor.execute("call-1", "echo", {"query": "latency"})

    assert result.content == "result:latency"
    assert result.record.name == "echo"
    assert json.loads(result.record.input) == {"query": "latency"}
    assert result.record.output == "result:latency"
    assert result.record.status == ToolCallStatus.SUCCEEDED
    assert result.record.error == ""
    assert result.record.error_type == ""
    assert result.record.duration_ms >= 0
    assert result.record.started_at is not None
    assert result.record.ended_at is not None


@pytest.mark.anyio
async def test_tool_executor_validates_required_input_schema() -> None:
    from oncallagent.tool_runtime import ToolExecutor

    executor = ToolExecutor([EchoTool()])

    result = await executor.execute("call-1", "echo", {})

    payload = json.loads(result.content)
    assert payload["success"] is False
    assert payload["error_type"] == "invalid_input"
    assert result.record.status == ToolCallStatus.FAILED
    assert result.record.error_type == "invalid_input"
    assert "query" in result.record.error


@pytest.mark.anyio
async def test_tool_executor_records_exception_without_raising() -> None:
    from oncallagent.tool_runtime import ToolExecutor

    executor = ToolExecutor([FailingTool()])

    result = await executor.execute("call-1", "fail", {})

    payload = json.loads(result.content)
    assert payload["success"] is False
    assert payload["error_type"] == "exception"
    assert result.record.status == ToolCallStatus.FAILED
    assert result.record.error_type == "exception"
    assert result.record.error == "boom"


@pytest.mark.anyio
async def test_tool_executor_enforces_timeout() -> None:
    from oncallagent.tool_runtime import ToolExecutor

    executor = ToolExecutor([SlowTool()], timeout_seconds=0.01)

    result = await executor.execute("call-1", "slow", {})

    payload = json.loads(result.content)
    assert payload["success"] is False
    assert payload["error_type"] == "timeout"
    assert result.record.status == ToolCallStatus.FAILED
    assert result.record.error_type == "timeout"


@pytest.mark.anyio
async def test_tool_executor_records_missing_tool_as_skipped() -> None:
    from oncallagent.tool_runtime import ToolExecutor

    executor = ToolExecutor([])

    result = await executor.execute("call-1", "missing_tool", {})

    assert "tool missing_tool is not configured" in result.content
    assert result.record.status == ToolCallStatus.SKIPPED
    assert result.record.error_type == "not_configured"
