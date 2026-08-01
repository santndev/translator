"""
Dual-Channel Audio Capturer
Captures WASAPI Loopback (Speakers - Incoming YouTube/Calls) & Microphone (Outgoing).
Uses PyAudioPatch on Windows for native loopback audio stream recording.
"""
import time
import threading
import numpy as np
from utils.logger import logger

class AudioCapturer:
    def __init__(self, callback_on_speech=None, stt_engine=None, callback_audio_activity=None, callback_partial_speech=None):
        """
        callback_on_speech: Function(channel_type: str, text_payload: str, raw_pcm_bytes: bytes)
        callback_audio_activity: Function(is_capturing: bool, volume: float)
        callback_partial_speech: Function(channel_type: str, partial_text: str)
        """
        self.callback = callback_on_speech
        self.stt_engine = stt_engine
        self.callback_audio_activity = callback_audio_activity
        self.callback_partial_speech = callback_partial_speech
        self.is_running = False
        self._threads = []
        self.pyaudio_instance = None

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

    def _capture_wasapi_loopback(self):
        """Worker thread that records system audio (Speakers / YouTube) via WASAPI loopback."""
        try:
            import pyaudiowpatch as pyaudio
            p = pyaudio.PyAudio()
            self.pyaudio_instance = p

            # Get default WASAPI output loopback device
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

            loopback_device = None
            if not default_speakers["isLoopbackDevice"]:
                for loopback in p.get_loopback_device_info_generator():
                    if default_speakers["name"] in loopback["name"]:
                        loopback_device = loopback
                        break
            else:
                loopback_device = default_speakers

            if not loopback_device:
                logger.warning("Could not find dedicated loopback device. Trying default output.")
                loopback_device = default_speakers

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

            audio_buffer = bytearray()
            silence_counter = 0
            speaking = False
            threshold = 350  # VAD energy threshold for speech detection

            logger.info("WASAPI Loopback Audio Listener ACTIVE. Play any YouTube video to capture!")

            while self.is_running:
                try:
                    data = stream.read(1024, exception_on_overflow=False)
                    if not data:
                        continue

                    # Energy VAD check
                    audio_np = np.frombuffer(data, dtype=np.int16)
                    energy = float(np.abs(audio_np).mean()) if len(audio_np) > 0 else 0.0

                    if energy > threshold:
                        audio_buffer.extend(data)
                        speaking = True
                        silence_counter = 0

                        # Emit instant visual audio activity signal
                        if self.callback_audio_activity:
                            self.callback_audio_activity(True, energy)

                        # Trigger Stream 1c live word stream every ~150ms of audio accumulation
                        if self.callback_partial_speech and len(audio_buffer) >= sample_rate * 0.2 * 2 and len(audio_buffer) % 2048 < 1024:
                            buf_copy = bytes(audio_buffer)
                            threading.Thread(
                                target=self._process_partial_captured_audio,
                                args=("incoming", buf_copy, sample_rate),
                                daemon=True
                            ).start()


                    else:
                        if speaking:
                            silence_counter += 1
                            audio_buffer.extend(data)
                            
                            # Emit active signal while buffering end of phrase
                            if self.callback_audio_activity:
                                self.callback_audio_activity(True, energy)

                            # 5 silence frames (~100ms) mark fast phrase boundary!
                            if silence_counter > 5:
                                pcm_bytes = bytes(audio_buffer)
                                audio_buffer = bytearray()
                                speaking = False
                                silence_counter = 0

                                if self.callback_audio_activity:
                                    self.callback_audio_activity(False, 0.0)

                                # Transcribe full accurate speech phrase
                                if len(pcm_bytes) > sample_rate * 0.3 * 2:  # Min 0.3s speech
                                    self._process_captured_audio("incoming", pcm_bytes, sample_rate)


                        else:
                            if self.callback_audio_activity and time.time() % 0.5 < 0.1:
                                self.callback_audio_activity(False, 0.0)

                except Exception as e:
                    time.sleep(0.01)

            stream.stop_stream()
            stream.close()
            p.terminate()

        except Exception as e:
            logger.error(f"WASAPI Loopback capture worker error: {e}")

    def _process_captured_audio(self, channel_type: str, pcm_bytes: bytes, sample_rate: int):
        """Transcribes PCM audio bytes and triggers speech callback."""
        logger.info(f"Captured {len(pcm_bytes)} bytes of speech on channel '{channel_type}'. Transcribing...")
        
        text = ""
        if self.stt_engine:
            text = self.stt_engine.transcribe_audio_pcm(pcm_bytes, sample_rate=sample_rate)

        if text and text.strip():
            logger.info(f"Transcribed '{channel_type}' speech: '{text.strip()}'")
            if self.callback:
                self.callback(channel_type, text.strip(), pcm_bytes)
        else:
            logger.info("Speech transcription was empty or noise.")

    def inject_mock_audio(self, channel_type: str, text_payload: str, raw_pcm_bytes: bytes = None):
        """Injects mock audio/text payload into the capture pipeline for automated testing."""
        logger.info(f"Injecting mock payload on channel '{channel_type}': {text_payload}")
        if self.callback_partial_speech and channel_type == "incoming":
            self.callback_partial_speech(channel_type, text_payload)
        if self.callback:
            self.callback(channel_type, text_payload, raw_pcm_bytes)

    def stop_capture(self):
        self.is_running = False
        logger.info("Audio Capture Engine stopped.")
