import json

from core.app_settings import AppSettings


def test_app_settings_round_trips_selected_model(tmp_path):
    path = tmp_path / "app_settings.json"
    settings = AppSettings(path)

    settings.save_openai_model("gpt-4.1-nano")

    assert settings.load_openai_model() == "gpt-4.1-nano"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "openai_model": "gpt-4.1-nano"
    }


def test_app_settings_ignores_unknown_or_corrupt_models(tmp_path):
    path = tmp_path / "app_settings.json"
    path.write_text('{"openai_model":"unknown-model"}', encoding="utf-8")
    settings = AppSettings(path)

    assert settings.load_openai_model("gpt-4.1-mini") == "gpt-4.1-mini"

    path.write_text("not-json", encoding="utf-8")
    assert settings.load_openai_model("gpt-5.6-luna") == "gpt-5.6-luna"


def test_app_settings_round_trips_audio_devices_without_losing_model(tmp_path):
    path = tmp_path / "app_settings.json"
    settings = AppSettings(path)
    settings.save_openai_model("gpt-4.1-nano")

    settings.save_audio_devices("Speakers (USB)", "Microphone (USB)")

    assert settings.load_audio_devices() == (
        "Speakers (USB)",
        "Microphone (USB)",
    )
    assert settings.load_openai_model() == "gpt-4.1-nano"
