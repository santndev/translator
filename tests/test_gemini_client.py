import json
from email.message import Message
from io import BytesIO
import urllib.error

import pytest

from core.dynamic_ai_generator import DynamicAIGenerator
from core.gemini_client import (
    GeminiAPIError,
    GeminiCircuitOpenError,
    GeminiClient,
)
from core.translator_engine import TranslatorEngine


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.data).encode("utf-8")


def test_client_uses_current_model_and_keeps_key_out_of_url_and_body():
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "candidates": [
                    {"content": {"parts": [{"text": '{"ok": true}'}]}}
                ]
            }
        )

    client = GeminiClient(api_key="secret-key", urlopen=fake_urlopen)

    assert client.generate_json("test") == {"ok": True}
    assert captured["url"].endswith(
        "/models/gemini-3.1-flash-lite:generateContent"
    )
    assert "secret-key" not in captured["url"]
    assert "secret-key" not in json.dumps(captured["body"])
    assert captured["headers"]["X-goog-api-key"] == "secret-key"
    assert (
        captured["body"]["generationConfig"]["responseMimeType"]
        == "application/json"
    )
    assert (
        captured["body"]["generationConfig"]["thinkingConfig"]["thinkingLevel"]
        == "minimal"
    )
    assert "temperature" not in captured["body"]["generationConfig"]


def test_client_rejects_response_without_generated_text():
    client = GeminiClient(
        api_key="secret-key",
        urlopen=lambda *_args, **_kwargs: FakeResponse({"candidates": []}),
    )

    with pytest.raises(GeminiAPIError, match="generated text"):
        client.generate_text("test")


def test_rate_limit_opens_circuit_and_recovers_after_retry_window():
    now = [100.0]
    calls = []
    statuses = []

    def fake_urlopen(_request, timeout):
        del timeout
        calls.append(now[0])
        if len(calls) == 1:
            headers = Message()
            headers["Retry-After"] = "30"
            raise urllib.error.HTTPError(
                "https://example.test",
                429,
                "Too Many Requests",
                headers,
                BytesIO(b'{"error":"quota exceeded"}'),
            )
        return FakeResponse(
            {"candidates": [{"content": {"parts": [{"text": "recovered"}]}}]}
        )

    client = GeminiClient(
        api_key="secret-key",
        urlopen=fake_urlopen,
        clock=lambda: now[0],
    )
    client.add_status_listener(
        lambda state, message: statuses.append((state, message))
    )

    with pytest.raises(GeminiAPIError, match="HTTP 429"):
        client.generate_text("first")
    assert client.status_snapshot()[0] == "local"

    with pytest.raises(GeminiCircuitOpenError, match="cooldown"):
        client.generate_text("must not reach network")
    assert len(calls) == 1

    now[0] += 31
    assert client.generate_text("probe") == "recovered"
    assert len(calls) == 2
    assert client.status_snapshot()[0] == "online"
    assert [state for state, _ in statuses] == [
        "online",
        "local",
        "probing",
        "online",
    ]


class FakeGemini:
    is_configured = True
    model = "fake-model"

    def __init__(self, result=None, text=""):
        self.result = result
        self.text = text
        self.prompts = []

    def generate_json(self, prompt, **_kwargs):
        self.prompts.append(prompt)
        return self.result

    def generate_text(self, prompt, **_kwargs):
        self.prompts.append(prompt)
        return self.text


def test_generator_normalizes_no_reply_and_uses_latest_utterance_prompt():
    fake = FakeGemini(
        result={
            "stream_1b": "Đây là một cập nhật.",
            "stream_2a": "deployment; monitoring",
            "stream_2b_quick_en": "Thanks.",
            "stream_2b_quick_vi": "Cảm ơn.",
            "stream_2b_en": "Thank you for the update.",
            "stream_2b_vi": "Cảm ơn bạn đã cập nhật.",
            "stream_2b_should_reply": False,
        }
    )

    result = DynamicAIGenerator(fake).generate_all_streams(
        "Deployment is complete.\nPrevious context: Can you review it?"
    )

    assert result["stream_2b_should_reply"] is False
    assert result["stream_2b_en"] == ""
    assert "LATEST utterance" in fake.prompts[0]
    assert "never answer an older question" in fake.prompts[0]


def test_generator_suppresses_speculative_reply_to_meeting_narration():
    fake = FakeGemini(
        result={
            "stream_1b": "Người nói đang trình bày đề xuất.",
            "stream_2a": "proposal; meeting; engineering",
            "stream_2b_quick_en": "That sounds good.",
            "stream_2b_quick_vi": "Nghe ổn đấy.",
            "stream_2b_en": "I agree with that approach.",
            "stream_2b_vi": "Tôi đồng ý với cách tiếp cận đó.",
            "stream_2b_should_reply": True,
        }
    )

    result = DynamicAIGenerator(fake).generate_all_streams(
        "There is a proposal to split this meeting into four reviews."
    )

    assert result["stream_2b_should_reply"] is False
    assert result["stream_2b_en"] == ""


def test_generator_keeps_reply_for_direct_cloud_request():
    fake = FakeGemini(
        result={
            "stream_1b": "Người nói yêu cầu xác nhận.",
            "stream_2a": "confirm; timeline",
            "stream_2b_quick_en": "Yes, I will confirm it.",
            "stream_2b_quick_vi": "Vâng, tôi sẽ xác nhận.",
            "stream_2b_en": "Yes, I will confirm the timeline today.",
            "stream_2b_vi": "Vâng, hôm nay tôi sẽ xác nhận tiến độ.",
            "stream_2b_should_reply": True,
        }
    )

    result = DynamicAIGenerator(fake).generate_all_streams(
        "Please confirm the delivery timeline."
    )

    assert result["stream_2b_should_reply"] is True
    assert result["stream_2b_en"]


def test_contextual_translation_uses_shared_gemini_client():
    fake = FakeGemini(text="Đây là bản dịch liền mạch theo ngữ cảnh.")
    engine = TranslatorEngine(gemini_client=fake)

    result = engine.translate_contextual_en_to_vi(
        ["It sanitizes the input.", "Then it executes the prepared statement."]
    )

    assert result == "Đây là bản dịch liền mạch theo ngữ cảnh."
    assert "prepared statement" in fake.prompts[0]
    assert "fixed glossary" in fake.prompts[0]
