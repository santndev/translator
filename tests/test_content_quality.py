"""Quality guardrails for local content when no cloud model is configured."""

from config import Config
from core.dynamic_ai_generator import DynamicAIGenerator
from core.smart_reply_engine import SmartReplyEngine
from core.translator_engine import TranslatorEngine


def test_local_reply_is_deterministic_and_has_quick_and_full_versions(monkeypatch):
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    engine = SmartReplyEngine()
    question = "How would you improve API latency without harming consistency?"

    first = engine.generate_stream_2b_response(question)
    second = engine.generate_stream_2b_response(question)

    assert first == second
    assert 1 <= len(first["quick_english"].split()) <= 10
    assert len(first["english"]) > len(first["quick_english"])
    assert first["quick_vietnamese"]
    assert first["vietnamese"]


def test_known_keywords_are_bilingual_without_network():
    translator = TranslatorEngine()

    result = translator.format_bilingual_keywords(
        "API ; latency ; consistency ; rollback",
        allow_network=False,
    )

    assert "API — giao diện lập trình" in result
    assert "latency — độ trễ" in result
    assert "consistency — tính nhất quán" in result
    assert "rollback — quay lui" in result


def test_generator_no_longer_changes_reply_randomly(monkeypatch):
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    generator = DynamicAIGenerator()
    statement = "We have completed the deployment and monitoring setup."

    outputs = [generator.generate_all_streams(statement) for _ in range(5)]

    assert all(output == outputs[0] for output in outputs)


def test_informational_update_does_not_force_a_reply(monkeypatch):
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    response = SmartReplyEngine().generate_stream_2b_response(
        "The deployment finished successfully and monitoring is active."
    )

    assert response["should_reply"] is False
    assert response["quick_english"] == ""
    assert "Không cần phản hồi" in response["quick_vietnamese"]
    assert response["english"] == ""


def test_explicit_request_still_recommends_a_reply(monkeypatch):
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    response = SmartReplyEngine().generate_stream_2b_response(
        "Please review the rollback plan and let me know."
    )

    assert response["should_reply"] is True
    assert response["quick_english"]
    assert response["english"]


def test_old_question_does_not_force_reply_to_latest_update(monkeypatch):
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    response = SmartReplyEngine().generate_stream_2b_response(
        "The deployment is complete."
        "\nPrevious context: How will we handle the rollback?"
    )

    assert response["should_reply"] is False


def test_direct_imperative_is_treated_as_requiring_a_reply(monkeypatch):
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    response = SmartReplyEngine().generate_stream_2b_response(
        "Review the incident report before tomorrow."
    )

    assert response["should_reply"] is True


def test_visible_keywords_ignore_previous_context_transport_labels(monkeypatch):
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    result = DynamicAIGenerator().generate_all_streams(
        "Please confirm the delivery timeline."
        "\nPrevious context: Explain the rollback architecture."
    )

    keywords = result["stream_2a"].lower()
    assert "previous" not in keywords
    assert "context" not in keywords
    assert "rollback" not in keywords
    assert "delivery" in keywords


def test_distributed_system_question_gets_relevant_failure_answer(monkeypatch):
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    response = SmartReplyEngine().generate_stream_2b_response(
        "How would you balance consistency and availability in a distributed system?"
    )

    assert response["should_reply"] is True
    assert "idempotent" in response["english"]
    assert "network" in response["english"]
    assert "tính nhất quán" in response["vietnamese"]
