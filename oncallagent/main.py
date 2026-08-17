from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from oncallagent.services.chat import ChatService
from oncallagent.infra.config import load_config
from oncallagent.infra.factory import (
    build_optional_chat_agent,
    build_optional_embedder,
    build_optional_external_indexer,
    build_optional_lazy_store,
    build_optional_plan_agent,
    build_optional_vector_store,
)
from oncallagent.knowledge.index import KnowledgeIndex
from oncallagent.services.plan import PlanService


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    id: str = Field(min_length=1)


def create_app(
    *,
    docs_dir: str | Path = "docs/runbooks",
    config_path: str | Path | None = None,
    prometheus_url: str | None = None,
    enable_external_indexing: bool = True,
) -> FastAPI:
    config = load_config(config_path)
    embedder = build_optional_embedder(config) if enable_external_indexing else None
    vector_store = (
        build_optional_vector_store(config, embedder) if enable_external_indexing else None
    )
    external_indexer = build_optional_external_indexer(
        config, enabled=enable_external_indexing, embedder=embedder, vector_store=vector_store
    )
    knowledge = KnowledgeIndex(
        docs_dir, external_indexer=external_indexer, vector_store=vector_store
    )

    # Lazily-initialised PostgreSQL store (None → in-memory-only fallback).
    lazy_store = build_optional_lazy_store(config)
    chat_agent = build_optional_chat_agent(config, knowledge, storage=lazy_store)
    chat_service = ChatService(knowledge, agent=chat_agent, storage=lazy_store)
    plan_agent = build_optional_plan_agent(config, chat_agent, storage=lazy_store)
    plan_service = PlanService(
        prometheus_url or config.prometheus.url,
        knowledge,
        agent=plan_agent,
    )

    # Lifespan: only used to close the pool on shutdown.
    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        if enable_external_indexing:
            await knowledge.reindex_external()
        yield
        if lazy_store is not None:
            await lazy_store.close()

    app = FastAPI(title="OnCallAgent", version="0.1.0", lifespan=_lifespan)
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
