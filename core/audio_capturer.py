"""
Dual-Channel Audio Capturer
Captures WASAPI Loopback (Speakers - Incoming YouTube/Calls) & Microphone (Outgoing).
Uses PyAudioPatch on Windows for native loopback audio stream recording.
"""
import time
import threading
import math
import numpy as np
import json
import os
import vosk
from config import Config
from utils.logger import logger

class AudioCapturer:
    def __init__(
        self,
        callback_on_speech=None,
        stt_engine=None,
        callback_audio_activity=None,
        callback_partial_speech=None,
        callback_recording_audio=None,
        speaker_device_name: str = "",
        microphone_device_name: str = "",
    ):
        """
        callback_on_speech: Function(channel_type: str, text_payload: str, raw_pcm_bytes: bytes)
        callback_audio_activity: Function(is_capturing: bool, volume: float)
        callback_partial_speech: Function(channel_type: str, partial_text: str)
        callback_recording_audio: Function(pcm_bytes: bytes, sample_rate: int, channels: int)
        """
        self.callback = callback_on_speech
        self.stt_engine = stt_engine
        self.callback_audio_activity = callback_audio_activity
        self.callback_partial_speech = callback_partial_speech
        self.callback_recording_audio = callback_recording_audio
        self._processing_enabled = threading.Event()
        self._processing_enabled.set()
        self.is_running = False
        self._threads = []
        self.pyaudio_instance = None
        self._active_stream = None
        self._microphone_pyaudio = None
        self._microphone_stream = None
        self._loopback_ready = threading.Event()
        self._remote_audio_until = 0.0
        self._device_lock = threading.RLock()
        self._device_generation = 0
        self._speaker_device_name = speaker_device_name.strip()
        self._microphone_device_name = microphone_device_name.strip()
        
        # Initialize Vosk Model for Zero-Latency Stream 1c
        vosk.SetLogLevel(-1) # Disable verbose logs
        from config import Config
        model_path = Config.VOSK_MODEL_PATH
        try:
            if os.path.exists(model_path):
                self.vosk_model = vosk.Model(model_path)
                logger.info("Vosk streaming STT model loaded successfully.")
            else:
                self.vosk_model = None
                logger.warning(f"Vosk model not found at {model_path}.")
        except Exception as e:
            logger.warning(f"Could not load Vosk model: {e}")
            self.vosk_model = None

    def _process_partial_captured_audio(self, channel_type: str, pcm_bytes: bytes, sample_rate: int):
        """Transcribes partial PCM audio for live word-by-word streaming."""
        if not self.stt_engine or not self.callback_partial_speech:
            return
        partial_text = self.stt_engine.transcribe_audio_pcm(pcm_bytes, sample_rate=sample_rate)
        if partial_text and partial_text.strip():
            self.callback_partial_speech(channel_type, partial_text.strip())



    def start_capture(self):
        """Starts real Windows WASAPI Loopback and Microphone capture threads."""
        if self.is_running:
            return
        self.is_running = True
        logger.info("Starting Real-time Audio Capture Engine (WASAPI Loopback + Microphone)...")

        # Launch WASAPI loopback worker thread
        t_loopback = threading.Thread(target=self._capture_wasapi_loopback, daemon=True)
        t_loopback.start()
        self._threads.append(t_loopback)

        if Config.CAPTURE_MICROPHONE:
            t_microphone = threading.Thread(
                target=self._capture_microphone,
                name="microphone-capture",
                daemon=True,
            )
            t_microphone.start()
            self._threads.append(t_microphone)
        else:
            logger.info(
                "Microphone capture disabled by "
                "TRANSLATOR_CAPTURE_MICROPHONE."
            )

    def _capture_microphone(self):
        """Capture the local user's microphone without taking down loopback."""
        restart_count = 0
        while self.is_running:
            try:
                self._run_microphone_session()
                return
            except Exception as error:
                restart_count += 1
                logger.warning(
                    "Microphone capture unavailable "
                    f"(attempt {restart_count}): {error}"
                )
            finally:
                stream = self._microphone_stream
                self._microphone_stream = None
                if stream is not None:
                    try:
                        stream.stop_stream()
                    except Exception:
                        pass
                    try:
                        stream.close()
                    except Exception:
                        pass
                # The microphone deliberately shares the loopback PyAudio host.
                # Its owner is responsible for terminating that host.
                self._microphone_pyaudio = None
            if self.is_running:
                time.sleep(min(5.0, 0.5 * restart_count))

    def _run_microphone_session(self):
        """Run one local microphone VAD/STT session."""
        try:
            import pyaudiowpatch as pyaudio

            if not self._loopback_ready.wait(timeout=8.0):
                raise RuntimeError("WASAPI host did not become ready")
            p = self.pyaudio_instance
            if p is None:
                raise RuntimeError("WASAPI host was reset")
            self._microphone_pyaudio = p
            generation, _speaker_name, microphone_name = (
                self._device_selection_snapshot()
            )
            default_device = p.get_default_input_device_info()
            device = self._find_named_device(
                p,
                microphone_name,
                input_device=True,
                fallback=default_device,
            )
            if int(device.get("maxInputChannels", 0)) < 1:
                raise RuntimeError("default input device has no input channel")

            sample_rate = int(device["defaultSampleRate"])
            channels = 1
            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=device["index"],
                frames_per_buffer=1024,
            )
            self._microphone_stream = stream
            logger.info(
                "Microphone Audio Listener ACTIVE: "
                f"'{device['name']}' ({sample_rate}Hz)"
            )

            audio_buffer = bytearray()
            silence_counter = 0
            speaking = False
            latest_vosk_text = ""
            vosk_final_parts = []
            noise_floor = 40.0
            threshold = 112.0
            silence_limit, max_bytes, min_bytes = self._calculate_vad_limits(
                sample_rate, channels
            )
            recognizer = (
                vosk.KaldiRecognizer(self.vosk_model, 16000)
                if getattr(self, "vosk_model", None)
                else None
            )
            read_errors = 0
            remote_ducking = False

            while self.is_running:
                try:
                    if generation != self._current_device_generation():
                        raise RuntimeError("microphone selection changed")
                    if stream.get_read_available() < 1024:
                        time.sleep(0.005)
                        continue
                    data = stream.read(1024, exception_on_overflow=False)
                    read_errors = 0
                    if not data:
                        continue

                    if not self._processing_enabled.is_set():
                        audio_buffer.clear()
                        silence_counter = 0
                        speaking = False
                        latest_vosk_text = ""
                        vosk_final_parts = []
                        if recognizer:
                            recognizer.Reset()
                        time.sleep(0.005)
                        continue

                    if self._should_duck_microphone():
                        audio_buffer.clear()
                        silence_counter = 0
                        speaking = False
                        latest_vosk_text = ""
                        vosk_final_parts = []
                        if not remote_ducking:
                            if recognizer:
                                recognizer.Reset()
                            if self.callback_partial_speech:
                                self.callback_partial_speech("outgoing", "")
                        remote_ducking = True
                        continue
                    remote_ducking = False

                    audio_np = np.frombuffer(data, dtype=np.int16)
                    energy = (
                        float(np.abs(audio_np).mean())
                        if len(audio_np) > 0
                        else 0.0
                    )
                    if not speaking:
                        noise_floor = 0.98 * noise_floor + 0.02 * min(
                            energy, 1000.0
                        )
                    threshold = min(
                        700.0,
                        max(
                            Config.MICROPHONE_VAD_THRESHOLD_MIN,
                            noise_floor * 3.2,
                        ),
                    )

                    if recognizer and self.callback_partial_speech:
                        audio_16k = self._pcm_to_16k_mono(
                            audio_np, sample_rate, channels
                        )
                        if recognizer.AcceptWaveform(audio_16k):
                            result = json.loads(recognizer.Result())
                            final_text = result.get("text", "").strip()
                            if final_text and (
                                not vosk_final_parts
                                or vosk_final_parts[-1] != final_text
                            ):
                                vosk_final_parts.append(final_text)
                            latest_vosk_text = " ".join(vosk_final_parts)
                        else:
                            partial = json.loads(
                                recognizer.PartialResult()
                            ).get("partial", "").strip()
                            latest_vosk_text = " ".join(
                                [*vosk_final_parts, partial]
                            ).strip()
                        if latest_vosk_text:
                            self.callback_partial_speech(
                                "outgoing", latest_vosk_text
                            )

                    if energy > threshold:
                        audio_buffer.extend(data)
                        speaking = True
                        silence_counter = 0
                    elif speaking:
                        audio_buffer.extend(data)
                        silence_counter += 1

                    if speaking and (
                        silence_counter >= silence_limit
                        or len(audio_buffer) >= max_bytes
                    ):
                        pcm_bytes = bytes(audio_buffer)
                        fallback_text = latest_vosk_text
                        audio_buffer.clear()
                        silence_counter = 0
                        speaking = False
                        latest_vosk_text = ""
                        vosk_final_parts = []
                        if self.callback_partial_speech:
                            self.callback_partial_speech("outgoing", "")
                        if recognizer:
                            recognizer.Reset()
                        if len(pcm_bytes) >= min_bytes:
                            self._process_captured_audio(
                                "outgoing",
                                pcm_bytes,
                                sample_rate,
                                channels=channels,
                                fallback_text=fallback_text,
                            )
                except Exception as error:
                    read_errors += 1
                    if read_errors >= 20:
                        raise RuntimeError(
                            "microphone stream failed repeatedly"
                        ) from error
                    time.sleep(0.01)
        except Exception as error:
            raise RuntimeError(f"microphone session failed: {error}") from error

    def _capture_wasapi_loopback(self):
        """Keep the loopback session alive across stalled streams/device resets."""
        restart_count = 0
        while self.is_running:
            try:
                self._run_wasapi_loopback_session()
                return
            except Exception as error:
                restart_count += 1
                logger.warning(
                    "Restarting WASAPI loopback session "
                    f"(attempt {restart_count}): {error}"
                )
                if self.callback_audio_activity:
                    self.callback_audio_activity(False, 0.0)
            finally:
                self._loopback_ready.clear()
                stream = self._active_stream
                self._active_stream = None
                if stream is not None:
                    try:
                        stream.stop_stream()
                    except Exception:
                        pass
                    try:
                        stream.close()
                    except Exception:
                        pass
                if self.pyaudio_instance is not None:
                    try:
                        self.pyaudio_instance.terminate()
                    except Exception:
                        pass
                    self.pyaudio_instance = None
            if self.is_running:
                time.sleep(min(2.0, 0.25 * restart_count))

    def _run_wasapi_loopback_session(self):
        """Record one WASAPI session; raise when it stalls so caller reconnects."""
        try:
            import pyaudiowpatch as pyaudio
            p = pyaudio.PyAudio()
            self.pyaudio_instance = p

            # Get default WASAPI output loopback device
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            generation, speaker_name, _microphone_name = (
                self._device_selection_snapshot()
            )
            default_speakers = p.get_device_info_by_index(
                wasapi_info["defaultOutputDevice"]
            )
            selected_speakers = self._find_named_device(
                p,
                speaker_name,
                output_device=True,
                host_api_index=int(wasapi_info["index"]),
                fallback=default_speakers,
            )

            loopback_device = None
            if not selected_speakers["isLoopbackDevice"]:
                for loopback in p.get_loopback_device_info_generator():
                    if self._device_names_match(
                        selected_speakers["name"], loopback["name"]
                    ):
                        loopback_device = loopback
                        break
            else:
                loopback_device = selected_speakers

            if not loopback_device:
                raise RuntimeError(
                    f"No loopback endpoint for '{selected_speakers['name']}'"
                )

            logger.info(f"Connected WASAPI Loopback Device: '{loopback_device['name']}' ({int(loopback_device['defaultSampleRate'])}Hz)")

            sample_rate = int(loopback_device['defaultSampleRate'])
            channels = int(loopback_device['maxInputChannels']) or 1

            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=loopback_device["index"],
                frames_per_buffer=1024
            )
            self._active_stream = stream
            self._loopback_ready.set()

            audio_buffer = bytearray()
            silence_counter = 0
            speaking = False
            latest_vosk_text = ""
            vosk_final_parts = []
            noise_floor = 40.0
            threshold = 112.0
            (
                silence_chunks_threshold,
                max_utterance_bytes,
                minimum_utterance_bytes,
            ) = self._calculate_vad_limits(
                sample_rate,
                channels,
            )
            read_error_count = 0
            monitor_started = time.monotonic()
            monitor_peak = 0.0
            
            # Initialize Vosk Recognizer at 16000Hz
            vosk_recognizer = vosk.KaldiRecognizer(self.vosk_model, 16000) if getattr(self, 'vosk_model', None) else None

            logger.info("WASAPI Loopback Audio Listener ACTIVE. Play any YouTube video to capture!")

            while self.is_running:
                try:
                    if generation != self._current_device_generation():
                        raise RuntimeError("speaker selection changed")
                    available_frames = stream.get_read_available()
                    if available_frames < 1024:
                        now = time.monotonic()
                        if now - monitor_started >= 10.0:
                            logger.info(
                                "WASAPI audio monitor: no frames available; "
                                "waiting for output audio"
                            )
                            monitor_started = now
                        time.sleep(0.005)
                        continue
                    data = stream.read(1024, exception_on_overflow=False)
                    read_error_count = 0
                    if not data:
                        continue

                    if self.callback_recording_audio:
                        try:
                            self.callback_recording_audio(data, sample_rate, channels)
                        except Exception as error:
                            logger.warning(f"Could not append recording audio: {error}")

                    if not self._processing_enabled.is_set():
                        audio_buffer = bytearray()
                        silence_counter = 0
                        speaking = False
                        latest_vosk_text = ""
                        vosk_final_parts = []
                        if vosk_recognizer:
                            vosk_recognizer.Reset()
                        time.sleep(0.005)
                        continue

                    # Energy VAD check
                    audio_np = np.frombuffer(data, dtype=np.int16)
                    energy = float(np.abs(audio_np).mean()) if len(audio_np) > 0 else 0.0
                    monitor_peak = max(monitor_peak, energy)
                    if not speaking:
                        noise_floor = 0.98 * noise_floor + 0.02 * min(
                            energy, 1000.0
                        )
                    threshold = min(350.0, max(90.0, noise_floor * 2.8))

                    # Zero-Latency Stream 1c using Vosk
                    is_phrase_boundary = False
                    if vosk_recognizer and self.callback_partial_speech:
                        # Convert to 16kHz mono
                        audio_16k_bytes = self._pcm_to_16k_mono(
                            audio_np, sample_rate, channels
                        )
                        
                        is_phrase_boundary = vosk_recognizer.AcceptWaveform(audio_16k_bytes)
                        if is_phrase_boundary:
                            res = json.loads(vosk_recognizer.Result())
                            final_text = res.get("text", "").strip()
                            if final_text:
                                if not vosk_final_parts or vosk_final_parts[-1] != final_text:
                                    vosk_final_parts.append(final_text)
                                latest_vosk_text = " ".join(vosk_final_parts)
                                self.callback_partial_speech(
                                    "incoming", latest_vosk_text
                                )
                        else:
                            partial = json.loads(vosk_recognizer.PartialResult())
                            partial_str = partial.get("partial", "").strip()
                            if partial_str:
                                latest_vosk_text = " ".join(
                                    [*vosk_final_parts, partial_str]
                                ).strip()
                                self.callback_partial_speech(
                                    "incoming", latest_vosk_text
                                )

                    if energy > threshold:
                        self._mark_remote_audio_active()
                        audio_buffer.extend(data)
                        speaking = True
                        silence_counter = 0

                        # Emit instant visual audio activity signal
                        if self.callback_audio_activity:
                            self.callback_audio_activity(True, energy)
                    else:
                        if speaking:
                            silence_counter += 1
                            audio_buffer.extend(data)
                            
                            # Emit active signal while buffering end of phrase
                            if self.callback_audio_activity:
                                self.callback_audio_activity(True, energy)
                                
                    # A Vosk boundary is useful for live text, but is too eager to
                    # define a semantic utterance. Flush after a real pause or a
                    # correctly calculated eight-second safety bound.
                    force_flush = len(audio_buffer) >= max_utterance_bytes
                    if (
                        speaking
                        and silence_counter >= silence_chunks_threshold
                    ) or force_flush:
                        pcm_bytes = bytes(audio_buffer)
                        vosk_fallback_text = latest_vosk_text
                        audio_buffer = bytearray()
                        speaking = False
                        silence_counter = 0
                        latest_vosk_text = ""
                        vosk_final_parts = []
                        
                        # Emit empty string to tell UnderstandingWidget to push current phrase to rolling buffer
                        if self.callback_partial_speech:
                            self.callback_partial_speech("incoming", "")
                            
                        if vosk_recognizer:
                            vosk_recognizer.Reset()

                        if self.callback_audio_activity:
                            self.callback_audio_activity(False, 0.0)

                        # Transcribe full accurate speech phrase
                        if len(pcm_bytes) >= minimum_utterance_bytes:
                            self._process_captured_audio(
                                "incoming",
                                pcm_bytes,
                                sample_rate,
                                channels=channels,
                                fallback_text=vosk_fallback_text,
                            )

                    elif not speaking:
                        if self.callback_audio_activity and time.time() % 0.5 < 0.1:
                            self.callback_audio_activity(False, 0.0)

                    if time.monotonic() - monitor_started >= 10.0:
                        logger.info(
                            "WASAPI audio monitor: "
                            f"peak={monitor_peak:.0f}, vad_threshold={threshold:.0f}"
                        )
                        monitor_started = time.monotonic()
                        monitor_peak = 0.0

                except Exception as e:
                    read_error_count += 1
                    if read_error_count == 1 or read_error_count % 10 == 0:
                        logger.warning(
                            f"WASAPI stream read error ({read_error_count}): {e}"
                        )
                    if read_error_count >= 20:
                        raise RuntimeError(
                            "WASAPI stream failed repeatedly"
                        ) from e
                    time.sleep(0.01)

        except Exception as e:
            raise RuntimeError(f"WASAPI loopback session failed: {e}") from e

    def _process_captured_audio(
        self,
        channel_type: str,
        pcm_bytes: bytes,
        sample_rate: int,
        channels: int = 1,
        fallback_text: str = "",
    ):
        """Transcribes PCM audio bytes and triggers speech callback."""
        logger.info(f"Captured {len(pcm_bytes)} bytes of speech on channel '{channel_type}'. Transcribing...")
        
        text = ""
        stt_ready = bool(
            self.stt_engine
            and getattr(self.stt_engine, "is_ready", False)
        )
        if stt_ready:
            text = self.stt_engine.transcribe_audio_pcm(
                pcm_bytes,
                sample_rate=sample_rate,
                channels=channels,
            )

        text = self._normalize_transcript(text)
        normalized_fallback = self._normalize_transcript(fallback_text)

        if not text and normalized_fallback:
            text = normalized_fallback
            reason = "Whisper returned no text" if stt_ready else "Whisper is still loading"
            logger.info(f"{reason}; using Vosk final transcript: '{text}'")

        if text and text.strip():
            if channel_type == "outgoing" and len(text.split()) < 2:
                logger.info(
                    "Ignored one-token microphone fragment; insufficient "
                    f"context value and high echo risk: '{text}'"
                )
                return
            logger.info(f"Transcribed '{channel_type}' speech: '{text.strip()}'")
            if self.callback:
                self.callback(channel_type, text.strip(), pcm_bytes)
        else:
            logger.info("Speech transcription was empty or noise.")

    @staticmethod
    def _normalize_transcript(text: str) -> str:
        """Reject punctuation-only and non-semantic speech fragments."""
        normalized = " ".join((text or "").strip().split())
        if not normalized or not any(character.isalnum() for character in normalized):
            return ""
        filler = normalized.lower().strip(".,!?… ")
        if filler in {"uh", "um", "hmm", "mm", "ah", "er"}:
            return ""
        return normalized

    @staticmethod
    def _calculate_vad_limits(
        sample_rate: int, channels: int
    ) -> tuple[int, int, int]:
        silence_chunks = max(
            1,
            math.ceil(
                Config.VAD_SILENCE_THRESHOLD_MS
                * sample_rate
                / 1000
                / 1024
            ),
        )
        bytes_per_second = sample_rate * channels * 2
        return (
            silence_chunks,
            int(bytes_per_second * Config.MAX_UTTERANCE_SECONDS),
            int(bytes_per_second * 0.45),
        )

    @staticmethod
    def _pcm_to_16k_mono(
        audio: np.ndarray, sample_rate: int, channels: int
    ) -> bytes:
        """Create Vosk-compatible 16 kHz mono int16 PCM."""
        source_channels = max(1, int(channels))
        usable = len(audio) // source_channels * source_channels
        if source_channels > 1 and usable:
            mono = audio[:usable].reshape(-1, source_channels).mean(
                axis=1
            ).astype(np.int16)
        else:
            mono = audio.astype(np.int16, copy=False)
        step = max(1, int(round(sample_rate / 16000.0)))
        return mono[::step].tobytes()

    def _mark_remote_audio_active(self, now: float | None = None) -> None:
        timestamp = time.monotonic() if now is None else now
        self._remote_audio_until = max(
            self._remote_audio_until,
            timestamp + Config.MICROPHONE_DUCK_HOLD_SECONDS,
        )

    def _should_duck_microphone(self, now: float | None = None) -> bool:
        if not Config.MICROPHONE_DUCK_WHEN_REMOTE:
            return False
        timestamp = time.monotonic() if now is None else now
        return timestamp < self._remote_audio_until

    def inject_mock_audio(self, channel_type: str, text_payload: str, raw_pcm_bytes: bytes = None):
        """Injects mock audio/text payload into the capture pipeline for automated testing."""
        logger.info(f"Injecting mock payload on channel '{channel_type}': {text_payload}")
        if self.callback_partial_speech and channel_type == "incoming":
            self.callback_partial_speech(channel_type, text_payload)
        if self.callback:
            self.callback(channel_type, text_payload, raw_pcm_bytes)

    def set_processing_enabled(self, enabled: bool) -> None:
        """Pause/resume STT while capture remains alive (used during replay)."""
        if enabled:
            self._processing_enabled.set()
        else:
            self._processing_enabled.clear()
            if self.callback_partial_speech:
                self.callback_partial_speech("incoming", "")
                self.callback_partial_speech("outgoing", "")
            if self.callback_audio_activity:
                self.callback_audio_activity(False, 0.0)
        logger.info(f"Audio speech processing {'enabled' if enabled else 'paused'}.")

    @staticmethod
    def list_audio_devices() -> dict[str, list[dict]]:
        """Return selectable Windows WASAPI endpoints without loopback duplicates."""
        result = {"speakers": [], "microphones": []}
        try:
            import pyaudiowpatch as pyaudio

            host = pyaudio.PyAudio()
            try:
                wasapi = host.get_host_api_info_by_type(pyaudio.paWASAPI)
                host_index = int(wasapi["index"])
                default_output = int(wasapi["defaultOutputDevice"])
                default_input = int(wasapi["defaultInputDevice"])
                for index in range(host.get_device_count()):
                    device = host.get_device_info_by_index(index)
                    if int(device.get("hostApi", -1)) != host_index:
                        continue
                    if device.get("isLoopbackDevice"):
                        continue
                    entry = {
                        "index": int(device["index"]),
                        "name": str(device["name"]).strip(),
                    }
                    if int(device.get("maxOutputChannels", 0)) > 0:
                        result["speakers"].append(
                            {**entry, "default": int(device["index"]) == default_output}
                        )
                    if int(device.get("maxInputChannels", 0)) > 0:
                        result["microphones"].append(
                            {**entry, "default": int(device["index"]) == default_input}
                        )
            finally:
                host.terminate()
        except Exception as error:
            logger.warning(f"Could not enumerate WASAPI audio devices: {error}")
        return result

    @staticmethod
    def resolve_device_name(devices: list[dict], preferred_name: str) -> str:
        """Resolve a saved name, falling back to the current Windows default."""
        preferred = preferred_name.strip()
        if preferred:
            for device in devices:
                if device.get("name") == preferred:
                    return preferred
        for device in devices:
            if device.get("default"):
                return str(device.get("name", ""))
        return str(devices[0].get("name", "")) if devices else ""

    def select_devices(self, speaker_name: str, microphone_name: str) -> None:
        """Reconnect active capture sessions to newly selected endpoints."""
        with self._device_lock:
            selected = (speaker_name.strip(), microphone_name.strip())
            current = (
                self._speaker_device_name,
                self._microphone_device_name,
            )
            if selected == current:
                return
            self._speaker_device_name, self._microphone_device_name = selected
            self._device_generation += 1
        self._loopback_ready.clear()
        logger.info(
            "Audio devices changed: "
            f"speaker='{selected[0]}', microphone='{selected[1]}'"
        )

    def _device_selection_snapshot(self) -> tuple[int, str, str]:
        with self._device_lock:
            return (
                self._device_generation,
                self._speaker_device_name,
                self._microphone_device_name,
            )

    def _current_device_generation(self) -> int:
        with self._device_lock:
            return self._device_generation

    @classmethod
    def _find_named_device(
        cls,
        host,
        preferred_name: str,
        *,
        input_device: bool = False,
        output_device: bool = False,
        host_api_index: int | None = None,
        fallback: dict,
    ) -> dict:
        for index in range(host.get_device_count()):
            device = host.get_device_info_by_index(index)
            if host_api_index is not None and int(
                device.get("hostApi", -1)
            ) != host_api_index:
                continue
            if input_device and int(device.get("maxInputChannels", 0)) < 1:
                continue
            if output_device and int(device.get("maxOutputChannels", 0)) < 1:
                continue
            if cls._device_names_match(preferred_name, device.get("name", "")):
                return device
        return fallback

    @staticmethod
    def _device_names_match(first: str, second: str) -> bool:
        def normalize(value: str) -> str:
            cleaned = str(value).replace("[Loopback]", "").strip().casefold()
            return " ".join(cleaned.split())

        return bool(first) and normalize(first) == normalize(second)

    def stop_capture(self):
        self.is_running = False
        for stream in (self._active_stream, self._microphone_stream):
            if stream is not None:
                try:
                    stream.stop_stream()
                except Exception:
                    pass
        logger.info("Audio Capture Engine stopped.")
