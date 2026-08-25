from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
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
from oncallagent.storage.store import LazyPostgresStore


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    id: str = Field(min_length=1)


@dataclass(frozen=True)
class _AppComponents:
    knowledge: KnowledgeIndex
    chat_service: ChatService
    plan_service: PlanService
    lazy_store: LazyPostgresStore | None
    enable_external_indexing: bool


def _build_components(
    *,
    docs_dir: str | Path,
    config_path: str | Path | None,
    prometheus_url: str | None,
    enable_external_indexing: bool,
) -> _AppComponents:
    config = load_config(config_path)
    embedder = build_optional_embedder(config) if enable_external_indexing else None
    vector_store = (
        build_optional_vector_store(config, embedder) if enable_external_indexing else None
    )
    external_indexer = build_optional_external_indexer(
        config,
        enabled=enable_external_indexing,
        embedder=embedder,
        vector_store=vector_store,
    )
    knowledge = KnowledgeIndex(
        docs_dir,
        external_indexer=external_indexer,
        vector_store=vector_store,
    )

    lazy_store = build_optional_lazy_store(config)
    chat_agent = build_optional_chat_agent(config, knowledge, storage=lazy_store)
    chat_service = ChatService(knowledge, agent=chat_agent, storage=lazy_store)
    plan_agent = build_optional_plan_agent(config, chat_agent, storage=lazy_store)
    plan_service = PlanService(
        prometheus_url or config.prometheus.url,
        knowledge,
        agent=plan_agent,
    )
    return _AppComponents(
        knowledge=knowledge,
        chat_service=chat_service,
        plan_service=plan_service,
        lazy_store=lazy_store,
        enable_external_indexing=enable_external_indexing,
    )


def create_app(
    *,
    docs_dir: str | Path = "docs/runbooks",
    config_path: str | Path | None = None,
    prometheus_url: str | None = None,
    enable_external_indexing: bool = True,
) -> FastAPI:
    components = _build_components(
        docs_dir=docs_dir,
        config_path=config_path,
        prometheus_url=prometheus_url,
        enable_external_indexing=enable_external_indexing,
    )

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        if components.enable_external_indexing:
            await components.knowledge.reindex_external()
        yield
        if components.lazy_store is not None:
            await components.lazy_store.close()

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
        message = await components.knowledge.save_upload(file)
        return {"message": message}

    @app.post("/chat")
    async def chat(request: ChatRequest) -> dict[str, str]:
        message = await components.chat_service.chat(request.question, request.id)
        return {"message": message}

    @app.post("/chatStream")
    async def chat_stream(request: ChatRequest) -> StreamingResponse:
        async def events() -> AsyncIterator[str]:
            async for chunk in components.chat_service.stream_chat(
                request.question, request.id
            ):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/plan")
    async def plan() -> dict:
        report = await components.plan_service.plan()
        return {
            "message": "获取运维信息成功",
            "data": {"lastmsg": report.lastmsg, "msgs": report.msgs},
        }

    return app


app = create_app()
