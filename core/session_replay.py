"""Thread-safe UI event timeline synchronized to a recorded audio session."""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time


@dataclass(frozen=True)
class ReplayEvent:
    offset_ms: int
    stream: str
    payload: tuple


class SessionReplayTimeline:
    """Capture UI stream events relative to the first recorded PCM chunk."""

    def __init__(self):
        self._lock = threading.RLock()
        self._armed = False
        self._origin: float | None = None
        self._current_events: list[ReplayEvent] = []
        self._last_events: tuple[ReplayEvent, ...] = ()

    def arm(self) -> None:
        with self._lock:
            self._armed = True
            self._origin = None
            self._current_events = []

    def mark_audio_started(self, timestamp: float | None = None) -> None:
        with self._lock:
            if self._armed and self._origin is None:
                self._origin = time.monotonic() if timestamp is None else timestamp

    def record(self, stream: str, *payload, timestamp: float | None = None) -> None:
        with self._lock:
            if not self._armed or self._origin is None:
                return
            occurred_at = time.monotonic() if timestamp is None else timestamp
            offset_ms = max(0, round((occurred_at - self._origin) * 1000))
            self._current_events.append(
                ReplayEvent(offset_ms, stream, tuple(payload))
            )

    def finish(self, has_audio: bool) -> tuple[ReplayEvent, ...]:
        with self._lock:
            if has_audio and self._origin is not None:
                self._last_events = tuple(self._current_events)
            self._armed = False
            self._origin = None
            self._current_events = []
            return self._last_events

    @property
    def last_events(self) -> tuple[ReplayEvent, ...]:
        with self._lock:
            return self._last_events
