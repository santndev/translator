"""Regression tests for realtime STT readiness and Vosk fallback behavior."""

import threading

from core.audio_capturer import AudioCapturer


class _LoadingSTT:
    is_ready = False

    def transcribe_audio_pcm(self, *_args, **_kwargs):
        raise AssertionError("Whisper must not be called before it is ready")


class _ReadyButEmptySTT:
    is_ready = True

    def transcribe_audio_pcm(self, *_args, **_kwargs):
        return ""


class _ReadyPunctuationSTT:
    is_ready = True

    def transcribe_audio_pcm(self, *_args, **_kwargs):
        return "."


def _capturer_with(stt_engine, callback):
    capturer = AudioCapturer.__new__(AudioCapturer)
    capturer.stt_engine = stt_engine
    capturer.callback = callback
    return capturer


def test_vosk_final_reaches_pipeline_while_whisper_is_loading():
    received = []
    capturer = _capturer_with(
        _LoadingSTT(),
        lambda channel, text, raw: received.append((channel, text, raw)),
    )

    capturer._process_captured_audio(
        "incoming",
        b"\x00" * 4000,
        16000,
        fallback_text="we need a realtime fallback",
    )

    assert received == [
        ("incoming", "we need a realtime fallback", b"\x00" * 4000)
    ]


def test_vosk_final_is_used_when_whisper_returns_empty():
    received = []
    capturer = _capturer_with(
        _ReadyButEmptySTT(),
        lambda channel, text, raw: received.append((channel, text)),
    )

    capturer._process_captured_audio(
        "incoming",
        b"\x00" * 4000,
        16000,
        fallback_text="fallback after empty whisper result",
    )

    assert received == [
        ("incoming", "fallback after empty whisper result")
    ]


def test_punctuation_only_whisper_result_uses_meaningful_vosk_fallback():
    received = []
    capturer = _capturer_with(
        _ReadyPunctuationSTT(),
        lambda channel, text, raw: received.append((channel, text)),
    )

    capturer._process_captured_audio(
        "incoming",
        b"\x00" * 4000,
        16000,
        fallback_text="a meaningful fallback sentence",
    )

    assert received == [("incoming", "a meaningful fallback sentence")]


def test_vad_limits_use_real_device_rate_and_channel_count():
    silence_chunks, max_bytes, minimum_bytes = (
        AudioCapturer._calculate_vad_limits(48000, 2)
    )

    assert silence_chunks == 24
    assert max_bytes == 48000 * 2 * 2 * 8
    assert minimum_bytes == int(48000 * 2 * 2 * 0.45)


def test_processing_can_pause_for_replay_without_stopping_capture():
    partial_updates = []
    activity_updates = []
    capturer = AudioCapturer.__new__(AudioCapturer)
    capturer._processing_enabled = threading.Event()
    capturer._processing_enabled.set()
    capturer.callback_partial_speech = (
        lambda channel, text: partial_updates.append((channel, text))
    )
    capturer.callback_audio_activity = (
        lambda active, volume: activity_updates.append((active, volume))
    )

    capturer.set_processing_enabled(False)
    assert not capturer._processing_enabled.is_set()
    assert partial_updates == [("incoming", "")]
    assert activity_updates == [(False, 0.0)]

    capturer.set_processing_enabled(True)
    assert capturer._processing_enabled.is_set()
