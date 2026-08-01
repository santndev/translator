"""Tests for the slower three-utterance contextual translation path."""

from config import Config
from core.translator_engine import TranslatorEngine


def test_contextual_translation_uses_the_bounded_context_supplied_by_caller(monkeypatch):
    engine = TranslatorEngine()
    captured = []
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(
        engine,
        "translate_en_to_vi",
        lambda text: captured.append(text) or f"translated: {text}",
    )

    result = engine.translate_contextual_en_to_vi(
        ["ignored oldest", "first", "second", "third"]
    )

    assert captured == ["ignored oldest first second third"]
    assert result == "translated: ignored oldest first second third"


def test_contextual_translation_is_readable_but_uses_more_than_three_fragments():
    utterances = [f"fragment-{index}-with-some-content" for index in range(15)]

    selected = TranslatorEngine._select_readable_translation_context(utterances)

    assert 3 < len(selected) <= TranslatorEngine.CONTEXT_TRANSLATION_MAX_UTTERANCES
    assert selected[-1] == utterances[-1]
    assert len(" ".join(selected)) <= TranslatorEngine.CONTEXT_TRANSLATION_MAX_CHARS
