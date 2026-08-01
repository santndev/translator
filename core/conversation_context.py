"""Bounded rolling context for fragmented real-time speech utterances."""

from collections import deque
import threading
import time


class ConversationContext:
    """Keeps useful recent context without relying on a fixed sentence count."""

    def __init__(
        self,
        max_age_seconds: float = 120.0,
        max_chars: int = 1800,
        max_utterances: int = 24,
    ):
        self.max_age_seconds = max_age_seconds
        self.max_chars = max_chars
        self._entries = deque(maxlen=max_utterances)
        self._lock = threading.Lock()

    def add(self, text: str, now: float | None = None) -> list[str]:
        normalized = text.strip()
        timestamp = time.monotonic() if now is None else now
        with self._lock:
            if normalized:
                self._entries.append((timestamp, normalized))
            self._prune(timestamp)
            return self._bounded_texts()

    def _prune(self, now: float):
        cutoff = now - self.max_age_seconds
        while self._entries and self._entries[0][0] < cutoff:
            self._entries.popleft()

    def _bounded_texts(self) -> list[str]:
        selected = []
        used_chars = 0
        for _, text in reversed(self._entries):
            separator_chars = 1 if selected else 0
            if selected and used_chars + separator_chars + len(text) > self.max_chars:
                break
            if not selected and len(text) > self.max_chars:
                selected.append(text[-self.max_chars :])
                break
            selected.append(text)
            used_chars += separator_chars + len(text)
        return list(reversed(selected))
