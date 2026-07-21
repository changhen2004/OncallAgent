from oncallagent.agent import PlanExecuteReplanAgent, PlanStep, ReplanDecision
from oncallagent.harness import StopReason


class FakePlanner:
    async def plan(self, query: str) -> list[PlanStep]:
        return [PlanStep(description="check alerts"), PlanStep(description="query docs")]


class FakeExecutor:
    async def execute(self, step: PlanStep) -> str:
        return f"done: {step.description}"


class FakeReplanner:
    async def replan(self, query: str, completed: list[str], remaining: list[PlanStep]) -> ReplanDecision:
        if remaining:
            return ReplanDecision(remaining_steps=remaining, final_answer="")
        return ReplanDecision(remaining_steps=[], final_answer="final report")


def test_plan_execute_replan_returns_last_message_and_details() -> None:
    agent = PlanExecuteReplanAgent(FakePlanner(), FakeExecutor(), FakeReplanner(), max_iterations=20)

    result = agent.run_sync("分析告警")

    assert result.last_message == "final report"
    assert result.details == ["done: check alerts", "done: query docs", "final report"]
    assert result.state.stop_reason == StopReason.COMPLETED


class InfiniteReplanner:
    async def replan(self, query: str, completed: list[str], remaining: list[PlanStep]) -> ReplanDecision:
        return ReplanDecision(remaining_steps=[PlanStep(description="again")], final_answer="")


def test_plan_execute_replan_stops_at_iteration_budget() -> None:
    agent = PlanExecuteReplanAgent(FakePlanner(), FakeExecutor(), InfiniteReplanner(), max_iterations=2)

    result = agent.run_sync("分析告警")

    assert result.state.stop_reason == StopReason.BUDGET_EXCEEDED
    assert result.last_message == "done: again"
