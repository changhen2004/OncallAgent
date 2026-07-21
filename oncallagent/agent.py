from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Protocol

from oncallagent.harness import AgentState, RunBudget, StopReason
from oncallagent.llm import ChatMessage


@dataclass(frozen=True)
class PlanStep:
    description: str


@dataclass(frozen=True)
class ReplanDecision:
    remaining_steps: list[PlanStep]
    final_answer: str = ""


@dataclass(frozen=True)
class AgentRunResult:
    last_message: str
    details: list[str]
    state: AgentState


class Planner(Protocol):
    async def plan(self, query: str) -> list[PlanStep]:
        pass


class Executor(Protocol):
    async def execute(self, step: PlanStep) -> str:
        pass


class Replanner(Protocol):
    async def replan(
        self, query: str, completed: list[str], remaining: list[PlanStep]
    ) -> ReplanDecision:
        pass


class ChatModel(Protocol):
    async def chat(self, messages: list[ChatMessage]) -> str:
        pass


class ChatAgentLike(Protocol):
    async def chat(self, question: str, session_id: str) -> str:
        pass


class LLMPlanner:
    def __init__(self, model: ChatModel) -> None:
        self.model = model

    async def plan(self, query: str) -> list[PlanStep]:
        output = await self.model.chat(
            [
                ChatMessage(
                    role="user",
                    content=(
                        "为以下运维目标生成执行计划。优先输出 JSON: "
                        '{"steps":["step 1","step 2"]}。目标: ' + query
                    ),
                )
            ]
        )
        return [PlanStep(description=step) for step in _parse_steps(output)]


class LLMExecutor:
    def __init__(self, chat_agent: ChatAgentLike, *, session_id: str = "plan-executor") -> None:
        self.chat_agent = chat_agent
        self.session_id = session_id

    async def execute(self, step: PlanStep) -> str:
        return await self.chat_agent.chat(step.description, self.session_id)


class LLMReplanner:
    def __init__(self, model: ChatModel) -> None:
        self.model = model

    async def replan(
        self, query: str, completed: list[str], remaining: list[PlanStep]
    ) -> ReplanDecision:
        output = await self.model.chat(
            [
                ChatMessage(
                    role="user",
                    content=(
                        "根据目标、已完成结果和剩余步骤判断是否结束。"
                        "优先输出 JSON: "
                        '{"final_answer":"...","remaining_steps":["..."]}。'
                        f"目标: {query}\n已完成: {completed}\n剩余: {[step.description for step in remaining]}"
                    ),
                )
            ]
        )
        parsed = _parse_json_object(output)
        if parsed is not None:
            return ReplanDecision(
                remaining_steps=[
                    PlanStep(description=step)
                    for step in parsed.get("remaining_steps", [])
                    if str(step).strip()
                ],
                final_answer=str(parsed.get("final_answer", "")).strip(),
            )
        return ReplanDecision(remaining_steps=[], final_answer=output.strip())


class PlanExecuteReplanAgent:
    def __init__(
        self,
        planner: Planner,
        executor: Executor,
        replanner: Replanner,
        *,
        max_iterations: int = 20,
    ) -> None:
        self.planner = planner
        self.executor = executor
        self.replanner = replanner
        self.budget = RunBudget(max_iterations=max_iterations)

    async def run(self, query: str, incident_id: str = "plan") -> AgentRunResult:
        state = AgentState.new(incident_id, query)
        remaining = await self.planner.plan(query)
        details: list[str] = []
        last_message = ""

        while remaining:
            reason, allowed = self.budget.check(state.usage)
            if not allowed:
                state.stop(reason)
                return AgentRunResult(last_message=last_message, details=details, state=state)

            step = remaining.pop(0)
            output = await self.executor.execute(step)
            state.usage.iterations += 1
            details.append(output)
            last_message = output

            decision = await self.replanner.replan(query, details, remaining)
            if decision.final_answer:
                details.append(decision.final_answer)
                last_message = decision.final_answer
                state.stop(StopReason.COMPLETED)
                return AgentRunResult(last_message=last_message, details=details, state=state)
            remaining = decision.remaining_steps

        state.stop(StopReason.COMPLETED)
        return AgentRunResult(last_message=last_message, details=details, state=state)

    def run_sync(self, query: str, incident_id: str = "plan") -> AgentRunResult:
        return asyncio.run(self.run(query, incident_id=incident_id))


def _parse_steps(output: str) -> list[str]:
    parsed = _parse_json_object(output)
    if parsed is not None:
        return [str(step).strip() for step in parsed.get("steps", []) if str(step).strip()]

    steps: list[str] = []
    for line in output.splitlines():
        cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        if cleaned:
            steps.append(cleaned)
    return steps


def _parse_json_object(output: str) -> dict | None:
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
