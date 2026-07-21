import json
from pathlib import Path

from oncallagent.config import load_config


def test_load_config_applies_go_compatible_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"server": {"host": "0.0.0.0"}}), encoding="utf-8")

    cfg = load_config(config_path)

    assert cfg.server.host == "0.0.0.0"
    assert cfg.server.port == 8819
    assert cfg.embedder.host == "localhost"
    assert cfg.embedder.port == 11434
    assert cfg.embedder.model == "nomic-embed-text"
    assert cfg.embedder.dimension == 384
    assert cfg.qdrant.collection == "oncallagent"
    assert cfg.openai.model == "minimax/minimax-m2.1"
    assert cfg.prometheus.url == "http://localhost:9090"
    assert cfg.cls_mcp.base_url == "http://localhost:3100/sse"
    assert cfg.cls_mcp.enabled is True


def test_config_address_helpers(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "missing.json")

    assert cfg.get_server_addr() == "localhost:8819"
    assert cfg.get_embedder_addr() == "http://127.0.0.1:11434"
    assert cfg.get_qdrant_addr() == "127.0.0.1:6334"
    assert cfg.get_prometheus_url() == "http://localhost:9090"
    assert cfg.get_cls_mcp_url() == "http://localhost:3100/sse"
