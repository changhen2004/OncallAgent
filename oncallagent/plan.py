from __future__ import annotations

from dataclasses import dataclass

import httpx

from oncallagent.knowledge import KnowledgeIndex
from oncallagent.tools import PrometheusAlertsTool, simplify_prometheus_alerts


@dataclass(frozen=True)
class PlanReport:
    lastmsg: str
    msgs: list[str]


class PlanService:
    def __init__(self, prometheus_url: str, knowledge: KnowledgeIndex) -> None:
        self.prometheus_url = prometheus_url.rstrip("/")
        self.knowledge = knowledge

    async def plan(self) -> PlanReport:
        try:
            payload = await PrometheusAlertsTool(self.prometheus_url)._query_alerts()
        except httpx.HTTPError as exc:
            return PlanReport(
                lastmsg="Prometheus 不可用，已生成降级排障建议。",
                msgs=[
                    f"Prometheus 查询失败: {exc.__class__.__name__}",
                    "检查 prometheus.url 配置、网络连通性和 /api/v1/alerts 接口。",
                    "如需知识库增强分析，请先通过 /upload 上传告警处理文档。",
                ],
            )

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
