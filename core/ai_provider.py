"""Provider router: OpenAI first, Gemini second, then caller-owned local mode."""

from __future__ import annotations

import threading

from core.gemini_client import GeminiClient
from core.openai_client import OpenAIClient


class AIProviderUnavailableError(RuntimeError):
    """Raised after all configured cloud providers failed."""


class AIProviderRouter:
    """Keep provider choice and failover outside product-content logic."""

    def __init__(self, openai_client=None, gemini_client=None):
        self.openai = openai_client or OpenAIClient()
        self.gemini = gemini_client or GeminiClient()
        self._lock = threading.RLock()
        self._listeners = []
        self._status_state, self._status_message = self._initial_status()

    @property
    def is_configured(self) -> bool:
        return any(provider.is_configured for provider in self._providers())

    @property
    def model(self) -> str:
        providers = self._configured_providers()
        return providers[0].model if providers else "local"

    @property
    def provider_name(self) -> str:
        return self.active_provider_name

    @property
    def active_provider_name(self) -> str:
        with self._lock:
            return self._active_provider_name

    def add_status_listener(self, listener, *, emit_current: bool = True):
        with self._lock:
            self._listeners.append(listener)
            snapshot = (self._status_state, self._status_message)
        if emit_current:
            listener(*snapshot)

    def status_snapshot(self) -> tuple[str, str]:
        with self._lock:
            return self._status_state, self._status_message

    def generate_text(self, prompt: str, **kwargs) -> str:
        return self._call("generate_text", prompt, kwargs)

    def generate_json(self, prompt: str, **kwargs) -> dict:
        return self._call("generate_json", prompt, kwargs)

    def _call(self, method_name: str, prompt: str, kwargs: dict):
        providers = self._configured_providers()
        if not providers:
            self._set_status(
                "off",
                "Chưa cấu hình AI online — đang dùng local",
                active_provider_name="Local",
            )
            raise AIProviderUnavailableError("No cloud AI provider is configured")

        failures = []
        primary_name = self._provider_name(providers[0])
        for provider in providers:
            provider_name = self._provider_name(provider)
            provider_kwargs = dict(kwargs)
            if provider_name == "Gemini":
                provider_kwargs.pop("json_schema", None)
                provider_kwargs.pop("reasoning_effort", None)
            try:
                result = getattr(provider, method_name)(prompt, **provider_kwargs)
                if provider_name == primary_name:
                    self._set_status(
                        "online",
                        f"{provider_name} đang hoạt động",
                        active_provider_name=provider_name,
                    )
                else:
                    self._set_status(
                        "degraded",
                        f"{primary_name} không sẵn sàng — đang dùng {provider_name}",
                        active_provider_name=provider_name,
                    )
                return result
            except Exception as error:
                failures.append(f"{provider_name}: {type(error).__name__}")

        self._set_status(
            "local",
            "AI online không sẵn sàng — đang dùng local",
            active_provider_name="Local",
        )
        raise AIProviderUnavailableError("; ".join(failures))

    def _providers(self) -> tuple[object, object]:
        return self.openai, self.gemini

    def _configured_providers(self) -> list[object]:
        return [provider for provider in self._providers() if provider.is_configured]

    def _initial_status(self) -> tuple[str, str]:
        configured = self._configured_providers()
        if configured:
            name = self._provider_name(configured[0])
            self._active_provider_name = name
            return "online", f"{name} sẵn sàng"
        self._active_provider_name = "Local"
        return "off", "Chưa cấu hình AI online — đang dùng local"

    def _set_status(
        self,
        state: str,
        message: str,
        *,
        active_provider_name: str,
    ):
        with self._lock:
            if (
                state,
                message,
                active_provider_name,
            ) == (
                self._status_state,
                self._status_message,
                self._active_provider_name,
            ):
                return
            self._status_state = state
            self._status_message = message
            self._active_provider_name = active_provider_name
            listeners = tuple(self._listeners)
        for listener in listeners:
            try:
                listener(state, message)
            except Exception:
                continue

    @staticmethod
    def _provider_name(provider) -> str:
        return getattr(provider, "provider_name", provider.__class__.__name__.replace("Client", ""))
