"""Tests for the slower bounded contextual translation path."""

from config import Config
from core.translator_engine import TranslatorEngine


def test_contextual_translation_fallback_outputs_only_newest_turn(monkeypatch):
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

    assert captured == ["third"]
    assert result == "translated: third"


def test_contextual_translation_is_readable_but_uses_more_than_three_fragments():
    utterances = [f"fragment-{index}-with-some-content" for index in range(15)]

    selected = TranslatorEngine._select_readable_translation_context(utterances)

    assert 3 < len(selected) <= TranslatorEngine.CONTEXT_TRANSLATION_MAX_UTTERANCES
    assert selected[-1] == utterances[-1]
    assert len(" ".join(selected)) <= TranslatorEngine.CONTEXT_TRANSLATION_MAX_CHARS
