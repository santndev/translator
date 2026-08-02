"""Keep the test suite deterministic and prevent accidental paid API calls."""

import pytest

from config import Config


@pytest.fixture(autouse=True)
def disable_real_cloud_credentials(monkeypatch):
    monkeypatch.setattr(Config, "TRANSLATOR_OPENAI_API_KEY", "")
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
