import pytest

from oncallagent.agent import LLMExecutor, LLMPlanner, LLMReplanner, PlanStep


class FakeChatModel:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.prompts: list[str] = []

    async def chat(self, messages) -> str:
        self.prompts.append(messages[-1].content)
        return self.outputs.pop(0)


class FakeChatAgent:
    async def chat(self, question: str, session_id: str) -> str:
        return f"executed: {question}"


@pytest.mark.anyio
async def test_llm_planner_parses_json_steps() -> None:
    planner = LLMPlanner(FakeChatModel(['{"steps":["query alerts","read runbook"]}']))

    steps = await planner.plan("分析告警")

    assert steps == [PlanStep("query alerts"), PlanStep("read runbook")]


@pytest.mark.anyio
async def test_llm_planner_falls_back_to_nonempty_lines() -> None:
    planner = LLMPlanner(FakeChatModel(["1. query alerts\n2. read runbook"]))

    steps = await planner.plan("分析告警")

    assert steps == [PlanStep("query alerts"), PlanStep("read runbook")]


@pytest.mark.anyio
async def test_llm_executor_delegates_step_to_chat_agent() -> None:
    executor = LLMExecutor(FakeChatAgent())

    output = await executor.execute(PlanStep("query alerts"))

    assert output == "executed: query alerts"


@pytest.mark.anyio
async def test_llm_replanner_parses_final_answer_and_remaining_steps() -> None:
    replanner = LLMReplanner(FakeChatModel(['{"final_answer":"done","remaining_steps":["next"]}']))

    decision = await replanner.replan("分析告警", ["checked"], [])

    assert decision.final_answer == "done"
    assert decision.remaining_steps == [PlanStep("next")]
