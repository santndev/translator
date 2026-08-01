"""Complete in-memory transcript and UTF-8 text export for one app session."""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from pathlib import Path
import os
import threading


class SessionTranscript:
    """Accumulate asynchronous stream results by utterance without UI truncation."""

    def __init__(self, max_utterances: int | None = None):
        self.max_utterances = (
            None if max_utterances is None else max(1, int(max_utterances))
        )
        self.started_at = datetime.now()
        self._items: OrderedDict[int, dict[str, object]] = OrderedDict()
        self._lock = threading.RLock()

    def record_english(self, utterance_id: int, english: str) -> None:
        self._update(utterance_id, english=english)

    def record_translation(self, utterance_id: int, vietnamese: str) -> None:
        self._update(utterance_id, vietnamese=vietnamese)

    def record_contextual_translation(
        self, utterance_id: int, contextual_vietnamese: str
    ) -> None:
        self._update(
            utterance_id, contextual_vietnamese=contextual_vietnamese
        )

    def record_assistance(self, utterance_id: int, bundle: dict) -> None:
        self._update(
            utterance_id,
            context_intent=bundle.get("explanation", ""),
            keywords=bundle.get("keywords", ""),
            reply_english=bundle.get("english", ""),
            reply_vietnamese=bundle.get("vietnamese", ""),
            should_reply=bool(bundle.get("should_reply", True)),
        )

    def _update(self, utterance_id: int, **fields: object) -> None:
        with self._lock:
            item = self._items.setdefault(int(utterance_id), {})
            item.update(fields)
            while (
                self.max_utterances is not None
                and len(self._items) > self.max_utterances
            ):
                self._items.popitem(last=False)

    def render_text(self, recording_path: Path | str | None = None) -> str:
        with self._lock:
            snapshot = [
                (key, dict(value))
                for key, value in sorted(self._items.items())
            ]
        lines = [
            "ENGLISH CALL ASSISTANT — SESSION EXPORT",
            f"Session started: {self.started_at:%Y-%m-%d %H:%M:%S}",
            f"Exported: {datetime.now():%Y-%m-%d %H:%M:%S}",
            f"Recording: {recording_path or 'None'}",
            "",
        ]
        for utterance_id, item in snapshot:
            should_reply = item.get("should_reply")
            reply_status = (
                "Pending"
                if should_reply is None
                else ("Yes" if should_reply else "No")
            )
            lines.extend(
                [
                    f"[{utterance_id:03d}]",
                    f"English: {item.get('english', '')}",
                    f"Vietnamese: {item.get('vietnamese', '')}",
                    "Contextual Vietnamese: "
                    f"{item.get('contextual_vietnamese', '')}",
                    f"Context / Intent: {item.get('context_intent', '')}",
                    f"Keywords: {item.get('keywords', '')}",
                    f"Reply needed: {reply_status}",
                    f"Recommended reply (EN): {item.get('reply_english', '')}",
                    f"Recommended reply (VI): {item.get('reply_vietnamese', '')}",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    def export(self, path: Path | str, recording_path: Path | str | None = None) -> Path:
        """Atomically write the current session as UTF-8 text."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".tmp")
        temporary.write_text(self.render_text(recording_path), encoding="utf-8")
        os.replace(temporary, destination)
        return destination
