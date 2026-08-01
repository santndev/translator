"""
Speech-to-Text (STT) Engine
Transcribes spoken audio from WASAPI Loopback / Microphone into English text.
"""
import builtins
import importlib
import threading

import numpy as np
from utils.logger import logger


_WHISPER_IMPORT_LOCK = threading.Lock()

class STTEngine:
    def __init__(self, model_size: str = "tiny.en"):
        self.model_size = model_size
        self._model = None
        self._is_loaded = False
        self._load_error = None
        # Load model asynchronously in background thread so GUI launches instantly
        threading.Thread(target=self.load_model, daemon=True).start()

    @property
    def is_ready(self) -> bool:
        return self._is_loaded and self._model is not None

    @staticmethod
    def _import_whisper_model_class():
        """
        Import Faster-Whisper without PySide's feature import hook.

        PySide replaces ``builtins.__import__`` with ``__feature_import__``.
        Importing the Transformers/AnyIO dependency tree through that hook from
        a worker thread can stall indefinitely while Shiboken inspects modules.
        The normal importer is restored immediately after the guarded import.
        """
        with _WHISPER_IMPORT_LOCK:
            previous_import = builtins.__import__
            uses_pyside_hook = (
                getattr(previous_import, "__name__", "") == "__feature_import__"
            )
            try:
                if uses_pyside_hook:
                    builtins.__import__ = importlib.__import__
                from faster_whisper import WhisperModel
                return WhisperModel
            finally:
                if uses_pyside_hook:
                    builtins.__import__ = previous_import

    def load_model(self):
        """Loads faster-whisper model in background."""
        if self.is_ready:
            return
        try:
            WhisperModel = self._import_whisper_model_class()
            logger.info(f"Loading Faster-Whisper model ({self.model_size}) in background...")
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            self._is_loaded = True
            self._load_error = None
            logger.info("Faster-Whisper model loaded successfully and READY!")
        except Exception as e:
            logger.warning(f"Could not load faster-whisper locally: {e}.")
            self._is_loaded = False
            self._load_error = str(e)


    def transcribe_audio_pcm(self, audio_data: bytes, sample_rate: int = 48000, channels: int = 2) -> str:
        """
        Transcribes raw PCM 16-bit audio bytes to English text using Faster-Whisper.
        Performs 2-channel averaging and 48kHz to 16kHz downsampling for crystal clear STT accuracy.
        """
        if not audio_data or len(audio_data) < 3200:
            return ""

        if not self.is_ready:
            return ""

        if self.is_ready:
            try:
                # 1. Convert bytes to int16 numpy array
                audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
                
                # 2. Stereo to Mono channel averaging if multi-channel
                if len(audio_int16) % 2 == 0:
                    audio_mono = audio_int16.reshape(-1, 2).mean(axis=1)
                else:
                    audio_mono = audio_int16.astype(np.float32)

                # 3. Normalize float32 (-1.0 to 1.0)
                audio_float32 = audio_mono.astype(np.float32) / 32768.0

                # 4. Universal Dynamic Downsampling to 16000Hz for MS Teams / Zoom / Meet / Telegram
                target_rate = 16000
                if sample_rate > target_rate:
                    step = max(1, int(round(sample_rate / float(target_rate))))
                    audio_16k = audio_float32[::step]
                else:
                    audio_16k = audio_float32

                # 5. Transcribe with VAD filter enabled for high precision
                segments, info = self._model.transcribe(
                    audio_16k,
                    language="en",
                    beam_size=1,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=100)
                )
                text = " ".join([seg.text.strip() for seg in segments])
                return text.strip()

            except Exception as e:
                logger.error(f"Whisper transcription error: {e}")
                return ""
        else:
            return ""
