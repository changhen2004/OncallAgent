from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from oncallagent.agent.planner import AgentRunResult
from oncallagent.knowledge.index import KnowledgeIndex
from oncallagent.tools.builtin import PrometheusAlertsTool, simplify_prometheus_alerts


@dataclass(frozen=True)
class PlanReport:
    lastmsg: str
    msgs: list[str]


class PlanAgent(Protocol):
    async def run(self, query: str, incident_id: str = "plan") -> AgentRunResult:
        pass


class PlanService:
    def __init__(
        self,
        prometheus_url: str,
        knowledge: KnowledgeIndex,
        *,
        agent: PlanAgent | None = None,
    ) -> None:
        self.prometheus_url = prometheus_url.rstrip("/")
        self.knowledge = knowledge
        self.agent = agent

    async def plan(self) -> PlanReport:
        try:
            payload = await PrometheusAlertsTool(self.prometheus_url)._query_alerts()
        except httpx.HTTPError as exc:
            if self.agent is not None:
                return await self._run_agent(
                    f"Prometheus 查询失败: {exc.__class__.__name__}。生成降级排障计划。"
                )
            return PlanReport(
                lastmsg="Prometheus 不可用，已生成降级排障建议。",
                msgs=[
                    f"Prometheus 查询失败: {exc.__class__.__name__}",
                    "检查 prometheus.url 配置、网络连通性和 /api/v1/alerts 接口。",
                    "如需知识库增强分析，请先通过 /upload 上传告警处理文档。",
                ],
            )

        if self.agent is not None:
            query = self._query_from_payload(payload)
            if query:
                return await self._run_agent(query)

        return self.plan_from_payload(payload)

    async def _run_agent(self, query: str) -> PlanReport:
        result = await self.agent.run(query, incident_id="plan")
        return PlanReport(lastmsg=result.last_message, msgs=result.details)

    def plan_from_payload(self, payload: dict) -> PlanReport:
        active_alerts = [
            alert for alert in simplify_prometheus_alerts(payload) if alert.state == "firing"
        ]
        if not active_alerts:
            return PlanReport(lastmsg="当前没有 firing 状态告警。", msgs=["无需执行自动排障计划。"])

        msgs: list[str] = []
        for alert in active_alerts:
            alert_name = alert.alert_name or "unknown"
            summary = alert.description or alert_name
            query = f"{alert_name} {summary}"
            matches = self.knowledge.search(query, limit=1)
            if matches:
                msgs.append(f"{alert_name}: 命中文档 {matches[0].filename}，建议按文档处理。")
            else:
                msgs.append(f"{alert_name}: 未命中知识库，先确认实例、指标窗口和最近发布变更。")

        return PlanReport(lastmsg=f"发现 {len(active_alerts)} 个活跃告警。", msgs=msgs)

    def _query_from_payload(self, payload: dict) -> str:
        active_alerts = [
            alert for alert in simplify_prometheus_alerts(payload) if alert.state == "firing"
        ]
        if not active_alerts:
            return ""
        lines = ["分析当前 firing Prometheus 告警并生成可执行排障计划。"]
        for alert in active_alerts:
            alert_name = alert.alert_name or "unknown"
            summary = alert.description or alert_name
            lines.append(f"- {alert_name}: {summary}")
        return "\n".join(lines)
