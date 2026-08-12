"""Small OpenAI Responses API client with circuit-breaker fallbacks."""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.request

from config import Config


class OpenAIAPIError(RuntimeError):
    """Raised when OpenAI cannot return a usable response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        category: str = "service",
        retry_after_seconds: float | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.category = category
        self.retry_after_seconds = retry_after_seconds


class OpenAICircuitOpenError(OpenAIAPIError):
    """Raised immediately while OpenAI is in its local-fallback cooldown."""


class OpenAIClient:
    """Calls the Responses API without persisting conversation content."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        api_base: str | None = None,
        timeout_seconds: float | None = None,
        urlopen=None,
        clock=None,
    ):
        self._lock = threading.RLock()
        self._api_key_override = api_key
        self._model = model or Config.OPENAI_MODEL
        self.api_base = (api_base or Config.OPENAI_API_BASE).rstrip("/")
        self.timeout_seconds = (
            Config.OPENAI_TIMEOUT_SECONDS
            if timeout_seconds is None
            else timeout_seconds
        )
        self._urlopen = urlopen or urllib.request.urlopen
        self._clock = clock or time.monotonic
        self._listeners = []
        self._consecutive_failures = 0
        self._open_until = 0.0
        self._status_state = "online" if self.is_configured else "off"
        self._status_message = (
            "OpenAI sẵn sàng"
            if self.is_configured
            else "Chưa cấu hình OpenAI"
        )

    @property
    def api_key(self) -> str:
        return (
            Config.TRANSLATOR_OPENAI_API_KEY
            if self._api_key_override is None
            else self._api_key_override
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    @property
    def model(self) -> str:
        with self._lock:
            return self._model

    def set_model(self, model: str) -> None:
        """Switch future requests to a new model and reset stale cooldown state."""
        selected = model.strip() if isinstance(model, str) else ""
        if not selected:
            raise ValueError("OpenAI model must be a non-empty string")
        with self._lock:
            if selected == self._model:
                return
            self._model = selected
            self._consecutive_failures = 0
            self._open_until = 0.0
            state = "online" if self.is_configured else "off"
            message = (
                f"OpenAI {selected} sẵn sàng"
                if self.is_configured
                else "Chưa cấu hình OpenAI"
            )
            notify = self._set_status_locked(state, message)
        self._notify(notify)

    def add_status_listener(self, listener, *, emit_current: bool = True):
        with self._lock:
            self._listeners.append(listener)
            snapshot = (self._status_state, self._status_message)
        if emit_current:
            listener(*snapshot)

    def status_snapshot(self) -> tuple[str, str]:
        with self._lock:
            return self._status_state, self._status_message

    def generate_text(
        self,
        prompt: str,
        *,
        max_output_tokens: int = 256,
        reasoning_effort: str | None = None,
        thinking_level: str | None = None,
        temperature: float | None = None,
    ) -> str:
        del thinking_level, temperature
        self._ensure_available()
        text = self._generate(
            prompt,
            max_output_tokens=max_output_tokens,
            reasoning_effort=reasoning_effort,
            json_schema=None,
        )
        self._record_success()
        return text

    def generate_json(
        self,
        prompt: str,
        *,
        max_output_tokens: int = 512,
        reasoning_effort: str | None = None,
        thinking_level: str | None = None,
        temperature: float | None = None,
        json_schema: dict | None = None,
    ) -> dict:
        del thinking_level, temperature
        self._ensure_available()
        raw = self._generate(
            prompt,
            max_output_tokens=max_output_tokens,
            reasoning_effort=reasoning_effort,
            json_schema=json_schema,
        )
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            api_error = OpenAIAPIError(
                "OpenAI returned invalid JSON", category="response"
            )
            self._record_failure(api_error)
            raise api_error from error
        if not isinstance(value, dict):
            api_error = OpenAIAPIError(
                "OpenAI JSON response must be an object", category="response"
            )
            self._record_failure(api_error)
            raise api_error
        self._record_success()
        return value

    def _generate(
        self,
        prompt: str,
        *,
        max_output_tokens: int,
        reasoning_effort: str | None,
        json_schema: dict | None,
    ) -> str:
        if not self.is_configured:
            raise OpenAIAPIError(
                "OpenAI API key is not configured", category="configuration"
            )

        effort = (reasoning_effort or Config.OPENAI_REASONING_EFFORT).lower()
        if effort not in {
            "none",
            "minimal",
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        }:
            effort = "none"
        model = self.model
        supports_gpt5_controls = bool(
            re.match(r"^gpt-5(?:[.-]|$)", model.lower())
        )
        text_config: dict = {}
        if supports_gpt5_controls:
            text_config["verbosity"] = "low"
        if json_schema is None:
            text_config["format"] = {"type": "text"}
        else:
            text_config["format"] = {
                "type": "json_schema",
                "name": "conversation_assistance",
                "strict": True,
                "schema": json_schema,
            }

        request_payload = {
            "model": model,
            "input": prompt,
            "max_output_tokens": max_output_tokens,
            "text": text_config,
            "store": False,
        }
        if supports_gpt5_controls:
            if re.match(r"^gpt-5(?:-(?:mini|nano))?$", model.lower()):
                if effort == "none":
                    effort = "minimal"
                elif effort in {"xhigh", "max"}:
                    effort = "high"
            request_payload["reasoning"] = {"effort": effort}

        payload = json.dumps(
            request_payload,
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_base}/responses",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self._urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = self._read_error_detail(error)
            suffix = f": {detail}" if detail else ""
            api_error = OpenAIAPIError(
                f"OpenAI HTTP {error.code}{suffix}",
                status_code=error.code,
                category=self._http_error_category(error.code),
                retry_after_seconds=self._retry_after_seconds(error),
            )
            self._record_failure(api_error)
            raise api_error from error
        except (urllib.error.URLError, TimeoutError) as error:
            api_error = OpenAIAPIError(
                f"OpenAI connection failed: {error}", category="connection"
            )
            self._record_failure(api_error)
            raise api_error from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            api_error = OpenAIAPIError(
                "OpenAI returned an unreadable response", category="response"
            )
            self._record_failure(api_error)
            raise api_error from error

        text = self._extract_output_text(data)
        if not text:
            api_error = OpenAIAPIError(
                "OpenAI response did not contain generated text",
                category="response",
            )
            self._record_failure(api_error)
            raise api_error
        return text

    @staticmethod
    def _extract_output_text(data: dict) -> str:
        top_level = data.get("output_text")
        if isinstance(top_level, str) and top_level.strip():
            return top_level.strip()
        parts = []
        for item in data.get("output", []):
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if (
                    isinstance(content, dict)
                    and content.get("type") == "output_text"
                    and isinstance(content.get("text"), str)
                ):
                    parts.append(content["text"])
        return "".join(parts).strip()

    def _ensure_available(self):
        if not self.is_configured:
            raise OpenAIAPIError(
                "OpenAI API key is not configured", category="configuration"
            )
        notify = None
        with self._lock:
            now = self._clock()
            if self._open_until > now:
                remaining = max(1, round(self._open_until - now))
                raise OpenAICircuitOpenError(
                    f"OpenAI cooldown active for {remaining}s",
                    category="circuit_open",
                    retry_after_seconds=remaining,
                )
            if self._open_until:
                self._open_until = 0.0
                notify = self._set_status_locked(
                    "probing", "Đang thử kết nối lại OpenAI"
                )
        self._notify(notify)

    def _record_success(self):
        with self._lock:
            self._consecutive_failures = 0
            self._open_until = 0.0
            notify = self._set_status_locked("online", "OpenAI đang hoạt động")
        self._notify(notify)

    def _record_failure(self, error: OpenAIAPIError):
        now = self._clock()
        with self._lock:
            self._consecutive_failures += 1
            opens_immediately = error.category in {"rate_limit", "authorization"}
            should_open = opens_immediately or (
                error.category in {"connection", "service", "response"}
                and self._consecutive_failures
                >= max(1, Config.OPENAI_FAILURE_THRESHOLD)
            )
            if should_open:
                default_cooldown = (
                    Config.OPENAI_RATE_LIMIT_COOLDOWN_SECONDS
                    if opens_immediately
                    else Config.OPENAI_RETRY_COOLDOWN_SECONDS
                )
                requested = error.retry_after_seconds or default_cooldown
                cooldown = max(
                    5.0,
                    min(float(requested), Config.OPENAI_MAX_COOLDOWN_SECONDS),
                )
                self._open_until = max(self._open_until, now + cooldown)
                notify = self._set_status_locked(
                    "local",
                    f"OpenAI tạm giới hạn — dùng fallback trong {round(cooldown)} giây",
                )
            else:
                notify = self._set_status_locked(
                    "degraded", "OpenAI đang lỗi — câu này dùng fallback"
                )
        self._notify(notify)

    def _set_status_locked(self, state: str, message: str):
        if (state, message) == (self._status_state, self._status_message):
            return None
        self._status_state = state
        self._status_message = message
        return tuple(self._listeners), state, message

    @staticmethod
    def _notify(notification):
        if notification is None:
            return
        listeners, state, message = notification
        for listener in listeners:
            try:
                listener(state, message)
            except Exception:
                continue

    @staticmethod
    def _http_error_category(status_code: int) -> str:
        if status_code == 429:
            return "rate_limit"
        if status_code in {401, 403}:
            return "authorization"
        if status_code >= 500:
            return "service"
        return "request"

    @staticmethod
    def _retry_after_seconds(error: urllib.error.HTTPError) -> float | None:
        value = error.headers.get("Retry-After") if error.headers else None
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _read_error_detail(error: urllib.error.HTTPError) -> str:
        try:
            raw = error.read(2048).decode("utf-8", errors="replace")
            data = json.loads(raw)
            message = data.get("error", {}).get("message", "")
            return str(message).replace("\r", " ").replace("\n", " ")[:300]
        except Exception:
            return ""
