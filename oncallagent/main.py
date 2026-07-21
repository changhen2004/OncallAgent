from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from oncallagent.chat import ChatService
from oncallagent.config import load_config
from oncallagent.factory import build_optional_chat_agent, build_optional_external_indexer
from oncallagent.knowledge import KnowledgeIndex
from oncallagent.plan import PlanService


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    id: str = Field(min_length=1)


def create_app(
    *,
    docs_dir: str | Path = "docs/runbooks",
    config_path: str | Path | None = None,
    prometheus_url: str | None = None,
    enable_external_indexing: bool = False,
) -> FastAPI:
    config = load_config(config_path)
    external_indexer = build_optional_external_indexer(
        config, enabled=enable_external_indexing
    )
    knowledge = KnowledgeIndex(docs_dir, external_indexer=external_indexer)
    chat_agent = build_optional_chat_agent(config, knowledge)
    chat_service = ChatService(knowledge, agent=chat_agent)
    plan_service = PlanService(prometheus_url or config.prometheus.url, knowledge)

    app = FastAPI(title="OnCallAgent", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Origin", "Content-Length", "Content-Type", "Authorization"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"message": "invalid request"})

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"message": "pong"}

    @app.post("/upload")
    async def upload(file: UploadFile | None = File(default=None)):
        if file is None:
            return JSONResponse(
                status_code=400,
                content={"message": "invalid request: no file provided"},
            )
        message = await knowledge.save_upload(file)
        return {"message": message}

    @app.post("/chat")
    async def chat(request: ChatRequest) -> dict[str, str]:
        message = await chat_service.chat(request.question, request.id)
        return {"message": message}

    @app.post("/chatStream")
    async def chat_stream(request: ChatRequest) -> StreamingResponse:
        async def events() -> AsyncIterator[str]:
            async for chunk in chat_service.stream_chat(request.question, request.id):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/plan")
    async def plan() -> dict:
        report = await plan_service.plan()
        return {
            "message": "获取运维信息成功",
            "data": {"lastmsg": report.lastmsg, "msgs": report.msgs},
        }

    return app


app = create_app()
