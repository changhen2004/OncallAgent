from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    host: str = "localhost"
    port: int = 8819


class EmbedderConfig(BaseModel):
    host: str = "localhost"
    port: int = 11434
    model: str = "nomic-embed-text"
    dimension: int = 384


class QdrantConfig(BaseModel):
    host: str = "localhost"
    port: int = 6334
    collection: str = "oncallagent"


class PrometheusConfig(BaseModel):
    url: str = "http://localhost:9090"


class OpenAIConfig(BaseModel):
    api_key: str = ""
    model: str = "minimax/minimax-m2.1"
    api_base: str = "https://api.qnaigc.com/v1"


class CLSMcpConfig(BaseModel):
    base_url: str = "http://localhost:3100/sse"
    enabled: bool = True


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    embedder: EmbedderConfig = Field(default_factory=EmbedderConfig)
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)
    prometheus: PrometheusConfig = Field(default_factory=PrometheusConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    cls_mcp: CLSMcpConfig = Field(default_factory=CLSMcpConfig)

    def get_server_addr(self) -> str:
        return f"{self.server.host}:{self.server.port}"

    def get_embedder_addr(self) -> str:
        return f"http://{self.embedder.host}:{self.embedder.port}"

    def get_qdrant_addr(self) -> str:
        return f"{self.qdrant.host}:{self.qdrant.port}"

    def get_prometheus_url(self) -> str:
        return self.prometheus.url or "http://localhost:9090"

    def get_cls_mcp_url(self) -> str:
        return self.cls_mcp.base_url or "http://localhost:3100/sse"


def load_config(config_path: str | Path | None = None) -> AppConfig:
    path = Path(config_path or "config/config.json")
    if not path.exists():
        path = Path("config/config_template.json")
    if not path.exists():
        return AppConfig()

    with path.open("r", encoding="utf-8") as file:
        raw = json.load(file)
    return AppConfig.model_validate(raw)
