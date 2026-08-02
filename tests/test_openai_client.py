import json
from email.message import Message
from io import BytesIO
import urllib.error

import pytest

from core.ai_provider import AIProviderRouter
from core.openai_client import (
    OpenAIAPIError,
    OpenAICircuitOpenError,
    OpenAIClient,
)


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.data).encode("utf-8")


def response_with_text(text):
    return FakeResponse(
        {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": text}],
                }
            ],
        }
    )


def test_openai_client_uses_responses_structured_output_without_storing_data():
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return response_with_text('{"ok": true}')

    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }
    client = OpenAIClient(api_key="secret-key", urlopen=fake_urlopen)

    assert client.generate_json("test", json_schema=schema) == {"ok": True}
    assert captured["url"].endswith("/v1/responses")
    assert "secret-key" not in captured["url"]
    assert "secret-key" not in json.dumps(captured["body"])
    assert captured["headers"]["Authorization"] == "Bearer secret-key"
    assert captured["body"]["model"] == "gpt-5.6-luna"
    assert captured["body"]["reasoning"] == {"effort": "none"}
    assert captured["body"]["store"] is False
    assert captured["body"]["text"]["verbosity"] == "low"
    assert captured["body"]["text"]["format"]["type"] == "json_schema"
    assert captured["body"]["text"]["format"]["strict"] is True
    assert captured["body"]["text"]["format"]["schema"] == schema


def test_openai_rate_limit_opens_circuit_and_recovers():
    now = [100.0]
    calls = []

    def fake_urlopen(_request, timeout):
        del timeout
        calls.append(now[0])
        if len(calls) == 1:
            headers = Message()
            headers["Retry-After"] = "5"
            raise urllib.error.HTTPError(
                "https://api.openai.com/v1/responses",
                429,
                "Too Many Requests",
                headers,
                BytesIO(b'{"error":{"message":"quota exceeded"}}'),
            )
        return response_with_text("recovered")

    client = OpenAIClient(
        api_key="secret-key", urlopen=fake_urlopen, clock=lambda: now[0]
    )

    with pytest.raises(OpenAIAPIError, match="HTTP 429"):
        client.generate_text("first")
    with pytest.raises(OpenAICircuitOpenError, match="cooldown"):
        client.generate_text("must not reach network")
    assert len(calls) == 1

    now[0] += 6
    assert client.generate_text("probe") == "recovered"


class FakeProvider:
    def __init__(self, name, result=None, error=None, configured=True):
        self.provider_name = name
        self.model = f"{name.lower()}-model"
        self.result = result
        self.error = error
        self.is_configured = configured
        self.calls = 0

    def generate_json(self, _prompt, **_kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def test_provider_router_prefers_openai_then_falls_back_to_gemini():
    openai = FakeProvider("OpenAI", error=RuntimeError("unavailable"))
    gemini = FakeProvider("Gemini", result={"ok": True})
    router = AIProviderRouter(openai_client=openai, gemini_client=gemini)
    statuses = []
    router.add_status_listener(lambda state, message: statuses.append((state, message)))

    assert router.generate_json("test", json_schema={}) == {"ok": True}
    assert openai.calls == 1
    assert gemini.calls == 1
    assert router.status_snapshot()[0] == "degraded"
    assert "Gemini" in router.status_snapshot()[1]
    assert router.active_provider_name == "Gemini"
