from __future__ import annotations

from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Protocol

from oncallagent.knowledge import KnowledgeIndex


class AgentChat(Protocol):
    async def chat(self, question: str, session_id: str) -> str:
        pass


class ChatService:
    def __init__(self, knowledge: KnowledgeIndex, agent: AgentChat | None = None) -> None:
        self.knowledge = knowledge
        self.agent = agent
        self._memory: dict[str, list[tuple[str, str]]] = defaultdict(list)

    async def chat(self, question: str, session_id: str) -> str:
        if self.agent is not None:
            return await self.agent.chat(question, session_id)

        results = self.knowledge.search(question)
        if results:
            context = "\n\n".join(result.content.strip() for result in results)
            answer = f"根据知识库检索结果，建议参考以下内容：\n{context}"
        else:
            answer = (
                "当前知识库没有命中相关文档。建议先上传排障手册，"
                "或补充告警名称、服务名、指标和最近变更信息。"
            )

        self._memory[session_id].append((question, answer))
        return answer

    async def stream_chat(self, question: str, session_id: str) -> AsyncIterator[str]:
        answer = await self.chat(question, session_id)
        for chunk in _chunk_text(answer, size=48):
            yield chunk


def _chunk_text(text: str, size: int) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)] or [""]
