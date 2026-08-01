"""Small, shared Gemini REST client with safe credential handling."""

import json
import threading
import time
import urllib.error
import urllib.request

from config import Config


class GeminiAPIError(RuntimeError):
    """Raised when Gemini cannot return a usable response."""

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


class GeminiCircuitOpenError(GeminiAPIError):
    """Raised immediately while Gemini is in its local-fallback cooldown."""


class GeminiClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        api_base: str | None = None,
        timeout_seconds: float | None = None,
        urlopen=None,
        clock=None,
    ):
        self._api_key_override = api_key
        self.model = model or Config.GEMINI_MODEL
        self.api_base = (api_base or Config.GEMINI_API_BASE).rstrip("/")
        self.timeout_seconds = (
            Config.GEMINI_TIMEOUT_SECONDS
            if timeout_seconds is None
            else timeout_seconds
        )
        self._urlopen = urlopen or urllib.request.urlopen
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._listeners = []
        self._consecutive_failures = 0
        self._open_until = 0.0
        self._status_state = "online" if self.is_configured else "off"
        self._status_message = (
            "Gemini sẵn sàng"
            if self.is_configured
            else "Chưa cấu hình Gemini — đang dùng chế độ local"
        )

    @property
    def api_key(self) -> str:
        return (
            Config.GEMINI_API_KEY
            if self._api_key_override is None
            else self._api_key_override
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def add_status_listener(self, listener, *, emit_current: bool = True):
        """Observe availability changes without coupling this core client to Qt."""
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
        temperature: float | None = None,
        max_output_tokens: int = 1024,
        thinking_level: str = "minimal",
    ) -> str:
        self._ensure_available()
        text = self._generate(
            prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            thinking_level=thinking_level,
        )
        self._record_success()
        return text

    def generate_json(
        self,
        prompt: str,
        *,
        temperature: float | None = None,
        max_output_tokens: int = 1024,
        thinking_level: str = "minimal",
    ) -> dict:
        self._ensure_available()
        raw = self._generate(
            prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            thinking_level=thinking_level,
            response_mime_type="application/json",
        )
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            api_error = GeminiAPIError(
                "Gemini returned invalid JSON", category="response"
            )
            self._record_failure(api_error)
            raise api_error from error
        if not isinstance(value, dict):
            api_error = GeminiAPIError(
                "Gemini JSON response must be an object", category="response"
            )
            self._record_failure(api_error)
            raise api_error
        self._record_success()
        return value

    def _generate(
        self,
        prompt: str,
        *,
        temperature: float | None,
        max_output_tokens: int,
        thinking_level: str,
        response_mime_type: str | None = None,
    ) -> str:
        if not self.is_configured:
            raise GeminiAPIError(
                "Gemini API key is not configured", category="configuration"
            )

        generation_config = {
            "maxOutputTokens": max_output_tokens,
            "thinkingConfig": {"thinkingLevel": thinking_level},
        }
        if temperature is not None:
            generation_config["temperature"] = temperature
        if response_mime_type:
            generation_config["responseMimeType"] = response_mime_type

        payload = json.dumps(
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": generation_config,
            }
        ).encode("utf-8")
        url = f"{self.api_base}/models/{self.model}:generateContent"
        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )
        try:
            with self._urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            try:
                detail = error.read(512).decode("utf-8", errors="replace")
            except Exception:
                detail = ""
            suffix = f": {detail}" if detail else ""
            api_error = GeminiAPIError(
                f"Gemini HTTP {error.code}{suffix}",
                status_code=error.code,
                category=self._http_error_category(error.code),
                retry_after_seconds=self._retry_after_seconds(error),
            )
            self._record_failure(api_error)
            raise api_error from error
        except (urllib.error.URLError, TimeoutError) as error:
            api_error = GeminiAPIError(
                f"Gemini connection failed: {error}", category="connection"
            )
            self._record_failure(api_error)
            raise api_error from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            api_error = GeminiAPIError(
                "Gemini returned an unreadable response", category="response"
            )
            self._record_failure(api_error)
            raise api_error from error

        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts).strip()
        except (KeyError, IndexError, TypeError) as error:
            api_error = GeminiAPIError(
                "Gemini response did not contain generated text",
                category="response",
            )
            self._record_failure(api_error)
            raise api_error from error
        if not text:
            api_error = GeminiAPIError(
                "Gemini returned empty generated text", category="response"
            )
            self._record_failure(api_error)
            raise api_error
        return text

    def _ensure_available(self):
        if not self.is_configured:
            raise GeminiAPIError(
                "Gemini API key is not configured", category="configuration"
            )

        notify = None
        with self._lock:
            now = self._clock()
            if self._open_until > now:
                remaining = max(1, round(self._open_until - now))
                raise GeminiCircuitOpenError(
                    f"Gemini cooldown active for {remaining}s",
                    category="circuit_open",
                    retry_after_seconds=remaining,
                )
            if self._open_until:
                self._open_until = 0.0
                notify = self._set_status_locked(
                    "probing", "Đang thử kết nối lại Gemini"
                )
        self._notify(notify)

    def _record_success(self):
        with self._lock:
            self._consecutive_failures = 0
            self._open_until = 0.0
            notify = self._set_status_locked("online", "Gemini đang hoạt động")
        self._notify(notify)

    def _record_failure(self, error: GeminiAPIError):
        now = self._clock()
        with self._lock:
            self._consecutive_failures += 1
            opens_immediately = error.category in {
                "rate_limit",
                "authorization",
            }
            should_open = opens_immediately or (
                error.category in {"connection", "service", "response"}
                and self._consecutive_failures
                >= max(1, Config.GEMINI_FAILURE_THRESHOLD)
            )
            if should_open:
                default_cooldown = (
                    Config.GEMINI_RATE_LIMIT_COOLDOWN_SECONDS
                    if opens_immediately
                    else Config.GEMINI_RETRY_COOLDOWN_SECONDS
                )
                requested = error.retry_after_seconds or default_cooldown
                cooldown = max(
                    5.0,
                    min(float(requested), Config.GEMINI_MAX_COOLDOWN_SECONDS),
                )
                self._open_until = max(self._open_until, now + cooldown)
                notify = self._set_status_locked(
                    "local",
                    f"Gemini tạm giới hạn — dùng local trong {round(cooldown)} giây",
                )
            else:
                notify = self._set_status_locked(
                    "degraded", "Gemini đang lỗi — câu này dùng chế độ local"
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
                # Status reporting must never fail an AI request or fallback.
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
