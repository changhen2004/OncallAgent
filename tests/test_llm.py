import pytest

from oncallagent.llm import ChatMessage, OpenAICompatibleChatModel


def test_chat_model_builds_openai_compatible_payload() -> None:
    model = OpenAICompatibleChatModel(
        api_key="sk-test",
        model="test-model",
        api_base="https://api.example.com/v1",
    )

    payload = model.build_payload([ChatMessage(role="user", content="hello")])

    assert payload == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "hello"}],
    }


@pytest.mark.anyio
async def test_chat_model_extracts_first_choice_content(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": "answer"}}]}

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            captured["kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, json: dict, headers: dict):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("oncallagent.llm.httpx.AsyncClient", FakeClient)
    model = OpenAICompatibleChatModel(
        api_key="sk-test",
        model="test-model",
        api_base="https://api.example.com/v1/",
    )

    output = await model.chat([ChatMessage(role="user", content="hello")])

    assert output == "answer"
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
