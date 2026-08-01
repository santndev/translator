"""Thread-safe WAV recording for captured system audio."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import threading
import wave

from utils.logger import logger


class SessionRecorder:
    """Persist raw PCM chunks from the loopback capture stream to one WAV file."""

    def __init__(self, recordings_dir: Path | str | None = None):
        default_dir = Path.home() / "Documents" / "Translator" / "Recordings"
        self.recordings_dir = Path(recordings_dir or default_dir)
        self._lock = threading.RLock()
        self._writer: wave.Wave_write | None = None
        self._pending_path: Path | None = None
        self._last_recording_path: Path | None = None
        self._format: tuple[int, int] | None = None
        self._frames_written = 0
        self._recording = False

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording

    @property
    def last_recording_path(self) -> Path | None:
        with self._lock:
            return self._last_recording_path

    def start(self) -> None:
        """Arm recording; the WAV is opened when the first PCM chunk arrives."""
        with self._lock:
            if self._recording:
                return
            self.recordings_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            self._pending_path = self.recordings_dir / f"call_{timestamp}.wav"
            self._writer = None
            self._format = None
            self._frames_written = 0
            self._recording = True
            logger.info("Session recording armed.")

    def append(self, pcm_bytes: bytes, sample_rate: int, channels: int) -> None:
        """Append signed 16-bit PCM captured from the system loopback device."""
        if not pcm_bytes:
            return
        with self._lock:
            if not self._recording:
                return
            audio_format = (int(sample_rate), int(channels))
            if self._writer is None:
                if self._pending_path is None:
                    return
                self._writer = wave.open(str(self._pending_path), "wb")
                self._writer.setnchannels(audio_format[1])
                self._writer.setsampwidth(2)
                self._writer.setframerate(audio_format[0])
                self._format = audio_format
            elif self._format != audio_format:
                logger.warning(
                    "Ignored recording chunk with changed audio format: "
                    f"expected={self._format}, received={audio_format}"
                )
                return
            self._writer.writeframesraw(pcm_bytes)
            self._frames_written += len(pcm_bytes)

    def stop(self) -> Path | None:
        """Finalize the active WAV and return it, or None when no audio arrived."""
        with self._lock:
            if not self._recording:
                return self._last_recording_path
            self._recording = False
            writer = self._writer
            output_path = self._pending_path
            self._writer = None
            self._pending_path = None
            self._format = None
            if writer is not None:
                writer.close()
            if output_path is not None and self._frames_written > 0:
                self._last_recording_path = output_path
                logger.info(f"Session recording saved: {output_path}")
            else:
                output_path = None
                logger.info("Session recording stopped before audio was captured.")
            self._frames_written = 0
            return output_path

    def close(self) -> None:
        self.stop()
