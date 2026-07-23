from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from oncallagent.harness import ToolCallRecord, ToolCallStatus


class Tool(Protocol):
    name: str
    description: str
    input_schema: dict

    async def call(self, arguments: dict) -> str:
        pass


@dataclass(frozen=True)
class ToolExecutionResult:
    tool_call_id: str
    name: str
    content: str
    record: ToolCallRecord


class ToolExecutor:
    def __init__(
        self,
        tools: list[Tool],
        *,
        timeout_seconds: float = 10.0,
        max_record_output_chars: int = 2000,
    ) -> None:
        self.tools = {tool.name: tool for tool in tools}
        self.timeout_seconds = timeout_seconds
        self.max_record_output_chars = max_record_output_chars

    async def execute(
        self, tool_call_id: str, tool_name: str, arguments: dict
    ) -> ToolExecutionResult:
        started_at = datetime.now(timezone.utc)
        serialized_input = _json_dumps(arguments)
        tool = self.tools.get(tool_name)
        if tool is None:
            content = f"tool {tool_name} is not configured"
            return self._result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                content=content,
                input_text=serialized_input,
                output=content,
                status=ToolCallStatus.SKIPPED,
                error=content,
                error_type="not_configured",
                started_at=started_at,
            )

        input_error = _validate_required_schema(tool.input_schema, arguments)
        if input_error:
            content = _failure_payload("invalid_input", input_error)
            return self._result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                content=content,
                input_text=serialized_input,
                output=content,
                status=ToolCallStatus.FAILED,
                error=input_error,
                error_type="invalid_input",
                started_at=started_at,
            )

        try:
            output = await asyncio.wait_for(
                tool.call(arguments), timeout=self.timeout_seconds
            )
        except TimeoutError:
            message = f"tool {tool_name} timed out after {self.timeout_seconds}s"
            content = _failure_payload("timeout", message)
            return self._result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                content=content,
                input_text=serialized_input,
                output=content,
                status=ToolCallStatus.FAILED,
                error=message,
                error_type="timeout",
                started_at=started_at,
            )
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            content = _failure_payload("exception", message)
            return self._result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                content=content,
                input_text=serialized_input,
                output=content,
                status=ToolCallStatus.FAILED,
                error=message,
                error_type="exception",
                started_at=started_at,
            )

        return self._result(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            content=output,
            input_text=serialized_input,
            output=output,
            status=ToolCallStatus.SUCCEEDED,
            error="",
            error_type="",
            started_at=started_at,
        )

    def _result(
        self,
        *,
        tool_call_id: str,
        tool_name: str,
        content: str,
        input_text: str,
        output: str,
        status: ToolCallStatus,
        error: str,
        error_type: str,
        started_at: datetime,
    ) -> ToolExecutionResult:
        ended_at = datetime.now(timezone.utc)
        record = ToolCallRecord(
            name=tool_name,
            input=input_text,
            output=_truncate(output, self.max_record_output_chars),
            status=status,
            error=error,
            error_type=error_type,
            started_at=started_at,
            ended_at=ended_at,
        )
        return ToolExecutionResult(
            tool_call_id=tool_call_id,
            name=tool_name,
            content=content,
            record=record,
        )


def _validate_required_schema(input_schema: dict, arguments: dict) -> str:
    required = input_schema.get("required", [])
    if not isinstance(required, list):
        return ""
    missing = [
        key
        for key in required
        if key not in arguments or arguments[key] is None or arguments[key] == ""
    ]
    if not missing:
        return ""
    return f"missing required tool arguments: {', '.join(map(str, missing))}"


def _failure_payload(error_type: str, message: str) -> str:
    return _json_dumps({"success": False, "error_type": error_type, "message": message})


def _json_dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _truncate(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return f"{text[:limit]}...<truncated>"
