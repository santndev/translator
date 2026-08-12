"""Small, validated store for user-selectable application preferences."""

from __future__ import annotations

import json
import os
from pathlib import Path

from config import Config
from utils.logger import logger


class AppSettings:
    """Persist non-secret preferences outside the installed application."""

    def __init__(self, path: str | os.PathLike[str] | None = None):
        self.path = Path(path or Config.APP_SETTINGS_PATH)

    def load_openai_model(self, default: str | None = None) -> str:
        fallback = self._validated_model(default or Config.OPENAI_MODEL)
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return fallback
            return self._validated_model(data.get("openai_model"), fallback)
        except FileNotFoundError:
            return fallback
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            logger.warning(f"Could not load app settings: {error}")
            return fallback

    def save_openai_model(self, model: str) -> None:
        selected = self._validated_model(model)
        data = self._read_existing()
        data["openai_model"] = selected
        self._write(data)

    def load_audio_devices(self) -> tuple[str, str]:
        data = self._read_existing()
        speaker = data.get("speaker_device_name", "")
        microphone = data.get("microphone_device_name", "")
        return (
            speaker if isinstance(speaker, str) else "",
            microphone if isinstance(microphone, str) else "",
        )

    def save_audio_devices(
        self, speaker_device_name: str, microphone_device_name: str
    ) -> None:
        data = self._read_existing()
        data["speaker_device_name"] = speaker_device_name.strip()
        data["microphone_device_name"] = microphone_device_name.strip()
        self._write(data)

    def _write(self, data: dict) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, self.path)
        except OSError as error:
            logger.warning(f"Could not save app settings: {error}")
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _read_existing(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _validated_model(model: object, fallback: str | None = None) -> str:
        if isinstance(model, str) and model in Config.OPENAI_MODEL_OPTIONS:
            return model
        if fallback in Config.OPENAI_MODEL_OPTIONS:
            return fallback
        return Config.OPENAI_MODEL_OPTIONS[0]
