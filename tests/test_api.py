from pathlib import Path
import json

from fastapi.testclient import TestClient

from oncallagent.main import create_app


def make_test_config(tmp_path: Path) -> Path:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"openai": {"api_key": ""}, "prometheus": {"url": "http://127.0.0.1:9"}}),
        encoding="utf-8",
    )
    return path


def test_ping_returns_pong(tmp_path: Path) -> None:
    client = TestClient(create_app(docs_dir=tmp_path, config_path=make_test_config(tmp_path)))

    response = client.get("/ping")

    assert response.status_code == 200
    assert response.json() == {"message": "pong"}


def test_upload_indexes_markdown_for_later_chat(tmp_path: Path) -> None:
    client = TestClient(create_app(docs_dir=tmp_path, config_path=make_test_config(tmp_path)))

    response = client.post(
        "/upload",
        files={
            "file": (
                "latency.md",
                b"# P95 latency\nRestart cache workers when p95 latency is high.",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200
    assert response.json() == {"message": "上传成功"}
    assert (tmp_path / "latency.md").exists()

    chat_response = client.post(
        "/chat",
        json={"question": "p95 latency 怎么处理?", "id": "incident-1"},
    )

    assert chat_response.status_code == 200
    assert "Restart cache workers" in chat_response.json()["message"]


def test_chat_rejects_invalid_payload(tmp_path: Path) -> None:
    client = TestClient(create_app(docs_dir=tmp_path, config_path=make_test_config(tmp_path)))

    response = client.post("/chat", json={"question": "missing id"})

    assert response.status_code == 400
    assert response.json() == {"message": "invalid request"}


def test_upload_rejects_missing_file_with_compatible_message(tmp_path: Path) -> None:
    client = TestClient(create_app(docs_dir=tmp_path, config_path=make_test_config(tmp_path)))

    response = client.post("/upload", files={})

    assert response.status_code == 400
    assert response.json() == {"message": "invalid request: no file provided"}


def test_chat_stream_emits_sse_chunks_and_done(tmp_path: Path) -> None:
    client = TestClient(create_app(docs_dir=tmp_path, config_path=make_test_config(tmp_path)))

    with client.stream(
        "POST",
        "/chatStream",
        json={"question": "当前告警?", "id": "incident-2"},
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert "data:" in body
    assert "data: [DONE]" in body


def test_plan_returns_degraded_report_when_prometheus_unavailable(tmp_path: Path) -> None:
    client = TestClient(
        create_app(
            docs_dir=tmp_path,
            config_path=make_test_config(tmp_path),
            prometheus_url="http://127.0.0.1:9",
        )
    )

    response = client.get("/plan")

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "获取运维信息成功"
    assert "lastmsg" in payload["data"]
    assert isinstance(payload["data"]["msgs"], list)
