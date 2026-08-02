"""
Main Entry Point for English Call Assistant & Dual-Stream Overlay Window
"""
import sys
import os
import time
from datetime import datetime
from pathlib import Path
from itertools import count

# Never inherit the headless Qt backend when launching the real Windows app.
if sys.platform == "win32" and os.getenv("QT_QPA_PLATFORM") == "offscreen":
    os.environ.pop("QT_QPA_PLATFORM", None)

# IMPORT CORE ENGINES FIRST TO PREVENT PYSIDE6 SHIBOKEN IMPORT BUGS WITH VOSK/REQUESTS
from config import Config
from core.ai_provider import AIProviderRouter
from core.audio_capturer import AudioCapturer
from core.conversation_context import ConversationContext
from core.gemini_client import GeminiClient
from core.openai_client import OpenAIClient
from core.latest_task_pool import LatestTaskPool
from core.session_recorder import SessionRecorder
from core.session_replay import ReplayEvent, SessionReplayTimeline
from core.session_transcript import SessionTranscript
from core.translator_engine import TranslatorEngine
from core.smart_reply_engine import SmartReplyEngine
from core.stt_engine import STTEngine
from core.user_profile import UserProfile
import ctypes
from utils.logger import logger

# THEN IMPORT PYSIDE6
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from PySide6.QtCore import QLockFile, QDir, QTimer, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from gui.overlay_window import OverlayWindow

# Windows Taskbar App ID setup for icon grouping and taskbar icon display
if sys.platform == "win32":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("translator.englishcallassistant.app.1.0")
    except Exception:
        pass

class AppController:
    ACTIVATION_SERVER_NAME = "english_call_assistant_activation"

    def __init__(self):
        # Single Instance Lock Enforcement (Prevent multiple app instances)
        self.lock_file = QLockFile(os.path.join(QDir.tempPath(), "english_call_assistant.lock"))
        if not self.lock_file.tryLock(100):
            self.lock_file.removeStaleLockFile()
            if not self.lock_file.tryLock(100):
                self._request_existing_activation()
                logger.warning("Another instance of English Call Assistant is already running. Exiting.")
                sys.exit(0)

        self.app = QApplication(sys.argv)
        self.app.setApplicationName("English Call Assistant")

        # Set App Icon
        if os.path.exists(Config.ICON_PATH_ICO):
            self.app.setWindowIcon(QIcon(Config.ICON_PATH_ICO))
        elif os.path.exists(Config.ICON_PATH_PNG):
            self.app.setWindowIcon(QIcon(Config.ICON_PATH_PNG))

        self.app.setQuitOnLastWindowClosed(True)
        self.overlay = OverlayWindow()
        self._setup_activation_server()
        self._utterance_ids = count(1)
        self._conversation_context = ConversationContext()
        self._task_pool = LatestTaskPool(max_workers=4)
        self._recorder = SessionRecorder()
        self._replay_timeline = SessionReplayTimeline()
        self._session_transcript = SessionTranscript()
        self._replay_active = False
        self._replay_started = False
        self._replay_events: tuple[ReplayEvent, ...] = ()
        self._replay_event_index = 0
        self._shutdown_started = False
        self.app.aboutToQuit.connect(self._shutdown)

        self._replay_audio_output = QAudioOutput(self.app)
        self._replay_player = QMediaPlayer(self.app)
        self._replay_player.setAudioOutput(self._replay_audio_output)
        self._replay_player.playbackStateChanged.connect(
            self._on_replay_state_changed
        )
        self._replay_player.errorOccurred.connect(self._on_replay_error)
        self._replay_timer = QTimer(self.app)
        self._replay_timer.setInterval(25)
        self._replay_timer.timeout.connect(self._emit_due_replay_events)

        self.overlay.signal_recording_toggled.connect(
            self._handle_recording_toggled
        )
        self.overlay.signal_replay_action.connect(self._handle_replay_action)
        self.overlay.signal_export_requested.connect(self._export_session)


        # Initialize Core Engines
        self.stt_engine = STTEngine(model_size="tiny.en")
        # All AI streams share provider circuits. OpenAI is preferred when its
        # key is configured; Gemini and local logic remain graceful fallbacks.
        self.openai_client = OpenAIClient()
        self.gemini_client = GeminiClient()
        self.ai_client = AIProviderRouter(
            openai_client=self.openai_client,
            gemini_client=self.gemini_client,
        )
        self.ai_client.add_status_listener(
            lambda state, message: self.overlay.signal_ai_status.emit(
                state,
                self.ai_client.active_provider_name,
                message,
            )
        )
        self.user_profile = UserProfile.load()
        self.translator = TranslatorEngine(ai_client=self.ai_client)
        self.smart_reply = SmartReplyEngine(
            ai_client=self.ai_client,
            user_profile=self.user_profile,
        )
        self.audio_capturer = AudioCapturer(
            callback_on_speech=self.on_audio_received,
            stt_engine=self.stt_engine,
            callback_audio_activity=self.on_audio_activity_event,
            callback_partial_speech=self.on_partial_audio_received,
            callback_recording_audio=self._on_recording_audio,
        )

    @classmethod
    def _request_existing_activation(cls):
        socket = QLocalSocket()
        socket.connectToServer(cls.ACTIVATION_SERVER_NAME)
        if socket.waitForConnected(500):
            socket.write(b"activate")
            socket.waitForBytesWritten(500)
            socket.disconnectFromServer()

    def _setup_activation_server(self):
        QLocalServer.removeServer(self.ACTIVATION_SERVER_NAME)
        self.activation_server = QLocalServer(self.app)
        if not self.activation_server.listen(self.ACTIVATION_SERVER_NAME):
            logger.warning(
                f"Could not start activation server: "
                f"{self.activation_server.errorString()}"
            )
            return
        self.activation_server.newConnection.connect(
            self._activate_from_secondary_instance
        )

    def _activate_from_secondary_instance(self):
        while self.activation_server.hasPendingConnections():
            connection = self.activation_server.nextPendingConnection()
            connection.disconnectFromServer()
        if self.overlay.isMinimized():
            self.overlay.showNormal()
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.activateWindow()
        logger.info("Existing app window activated by a second launch request.")

    def on_audio_activity_event(self, is_capturing: bool, volume: float):
        """Emits thread-safe signal to update visual audio indicator on top bar."""
        self.overlay.signal_audio_activity.emit(is_capturing, volume)

    def on_partial_audio_received(self, channel_type: str, partial_text: str):
        """Luồng 1c: Independent live word-by-word streaming display."""
        speaker = self._speaker_for_channel(channel_type)
        self._emit_stream(
            "signal_speaker_partial", speaker, partial_text.strip()
        )

    def _emit_stream(self, signal_name: str, *payload):
        """Emit a UI stream and retain it when a recording timeline is active."""
        getattr(self.overlay, signal_name).emit(*payload)
        self._replay_timeline.record(signal_name, *payload)

    def _on_recording_audio(
        self, pcm_bytes: bytes, sample_rate: int, channels: int
    ):
        received_at = time.monotonic()
        if self._recorder.append(pcm_bytes, sample_rate, channels):
            self._replay_timeline.mark_audio_started(received_at)



    @staticmethod
    def _speaker_for_channel(channel_type: str) -> str:
        if channel_type == "outgoing":
            return "YOU"
        if channel_type == "incoming":
            return "REMOTE"
        return "UNKNOWN"

    def process_speech(self, english_text: str, channel_type: str):
        """
        Process one speaker turn through bounded latest-result worker streams.

        Local speech contributes to translation and conversation context, but
        never triggers a reply suggestion to the user's own words.
        """
        speaker = self._speaker_for_channel(channel_type)
        logger.info(f"Processing {speaker} English Speech: '{english_text}'")
        utterance_id = next(self._utterance_ids)
        self._session_transcript.record_english(
            utterance_id, english_text, speaker=speaker
        )
        self._emit_stream("signal_speaker", utterance_id, speaker)
        context_label = "BẠN" if speaker == "YOU" else speaker
        translation_context = self._conversation_context.add(
            f"{context_label}: {english_text}"
        )
        previous_context = translation_context[:-1]
        analysis_context = english_text
        if previous_context:
            analysis_context += "\nPrevious context: " + " ".join(previous_context)

        # --- LUỒNG 1A: Dịch Realtime (Live Subtitle - Instant 0ms English Display) ---
        # 1. Emit English transcript IMMEDIATELY (0ms delay)
        self._emit_stream(
            "signal_stream1a", utterance_id, english_text, ""
        )
        # Keep the contextual English view local and immediate. It must not wait
        # for the slower contextual Vietnamese translation/network path.
        self._emit_stream(
            "signal_contextual_english",
            utterance_id,
            " ".join(translation_context),
        )

        def publish_translation(vi_trans: str):
            self._session_transcript.record_translation(utterance_id, vi_trans)
            logger.info(f"[STREAM 1A] EN: '{english_text}' -> VI: '{vi_trans}'")
            self._emit_stream(
                "signal_stream1a", utterance_id, english_text, vi_trans
            )

        self._task_pool.submit_latest(
            "translation",
            utterance_id,
            lambda: self.translator.translate_en_to_vi(english_text),
            publish_translation,
        )

        if len(translation_context) >= 2:
            combined_english = " ".join(translation_context)

            def publish_contextual_translation(contextual_vi: str):
                self._session_transcript.record_contextual_translation(
                    utterance_id, contextual_vi
                )
                logger.info(
                    f"[STREAM 1A CONTEXT] EN: '{combined_english}' "
                    f"-> VI: '{contextual_vi}'"
                )
                self._emit_stream(
                    "signal_stream1a_context",
                    utterance_id,
                    combined_english,
                    contextual_vi,
                )

            self._task_pool.submit_latest(
                "contextual_translation",
                utterance_id,
                lambda: self.translator.translate_contextual_en_to_vi(
                    translation_context
                ),
                publish_contextual_translation,
            )

        if speaker != "REMOTE":
            # A local turn makes an in-flight reply for the previous remote
            # turn obsolete, but it should not consume a worker just to cancel.
            self._task_pool.invalidate("assistance", utterance_id)
            return

        def prepare_assistance() -> dict:
            bundle = self.smart_reply.generate_stream_bundle(analysis_context)
            fast_bilingual = self.translator.format_bilingual_keywords(
                bundle["keywords"], allow_network=False
            )
            bundle["keywords"] = fast_bilingual
            return bundle

        def publish_assistance(bundle: dict):
            self._session_transcript.record_assistance(utterance_id, bundle)
            vi_explanation = bundle["explanation"]
            logger.info(f"[STREAM 1B] Context: '{vi_explanation}'")
            self._emit_stream("signal_stream1b", utterance_id, vi_explanation)
            fast_bilingual = bundle["keywords"]
            logger.info(f"[STREAM 2A] Keywords: '{fast_bilingual}'")
            self._emit_stream("signal_stream2a", utterance_id, fast_bilingual)
            logger.info(
                f"[STREAM 2B] Reply EN: '{bundle['english']}' | "
                f"Reply VI: '{bundle['vietnamese']}'"
            )
            self._emit_stream(
                "signal_stream2b",
                utterance_id,
                bundle["quick_english"],
                bundle["quick_vietnamese"],
                bundle["english"],
                bundle["vietnamese"],
                bundle["should_reply"],
            )

        self._task_pool.submit_latest(
            "assistance",
            utterance_id,
            prepare_assistance,
            publish_assistance,
        )

    def process_incoming_speech(self, english_text: str):
        """Backward-compatible entry point used by existing tests/tools."""
        self.process_speech(english_text, "incoming")

    def on_audio_received(self, channel_type: str, text_payload: str, raw_bytes: bytes = None):
        """Callback triggered when audio/speech is captured or injected."""
        if channel_type in {"incoming", "outgoing"}:
            self.process_speech(text_payload, channel_type)

    def _handle_recording_toggled(self, enabled: bool):
        try:
            if enabled:
                self._recorder.start()
                self._replay_timeline.arm()
                self.overlay.set_recording_state(True)
                return
            saved_path = self._recorder.stop()
            self._replay_events = self._replay_timeline.finish(
                has_audio=saved_path is not None
            )
            latest = saved_path or self._recorder.last_recording_path
            self.overlay.set_recording_state(False, str(latest or ""))
        except Exception as error:
            logger.exception(f"Could not change recording state: {error}")
            self.overlay.set_recording_state(
                self._recorder.is_recording,
                str(self._recorder.last_recording_path or ""),
            )
            QMessageBox.warning(
                self.overlay, "Recording error", f"Could not record audio:\n{error}"
            )

    def _handle_replay_action(self, action: str):
        if action == "play":
            self._start_replay()
        elif action == "pause":
            self._pause_replay()
        elif action == "stop":
            self._finish_replay(flush_remaining=False, stop_player=True)

    def _start_replay(self):
        recording_path = self._recorder.last_recording_path
        if not recording_path or not recording_path.exists():
            self.overlay.set_recording_state(False)
            QMessageBox.information(
                self.overlay, "Replay", "No completed recording is available yet."
            )
            return
        self._replay_started = False
        self._replay_active = True
        self._replay_events = self._replay_timeline.last_events
        self._replay_event_index = 0
        self.audio_capturer.set_processing_enabled(False)
        self.overlay.dashboard.clear_for_replay()
        self.overlay.set_replay_state("pause")
        self._replay_player.setSource(QUrl.fromLocalFile(str(recording_path)))
        self._replay_player.play()
        QTimer.singleShot(3000, self._verify_replay_started)
        logger.info(f"Replaying session recording: {recording_path}")

    def _verify_replay_started(self):
        if self._replay_active and not self._replay_started:
            logger.warning("Replay did not start within three seconds.")
            self._finish_replay(flush_remaining=False, stop_player=True)
            QMessageBox.warning(
                self.overlay,
                "Replay error",
                "Audio playback did not start. Check the Windows output device.",
            )

    def _on_replay_state_changed(self, state):
        if not self._replay_active:
            return
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._replay_started = True
            self._replay_timer.start()
        elif (
            state == QMediaPlayer.PlaybackState.StoppedState
            and self._replay_started
        ):
            self._finish_replay(flush_remaining=True, stop_player=False)

    def _pause_replay(self):
        if not self._replay_active:
            return
        self._replay_player.pause()
        self._replay_timer.stop()
        self.overlay.set_replay_state("stop")
        logger.info("Session replay paused.")

    def _emit_due_replay_events(self):
        position_ms = self._replay_player.position()
        while self._replay_event_index < len(self._replay_events):
            event = self._replay_events[self._replay_event_index]
            if event.offset_ms > position_ms + 25:
                break
            getattr(self.overlay, event.stream).emit(*event.payload)
            self._replay_event_index += 1

    def _emit_remaining_replay_events(self):
        while self._replay_event_index < len(self._replay_events):
            event = self._replay_events[self._replay_event_index]
            getattr(self.overlay, event.stream).emit(*event.payload)
            self._replay_event_index += 1

    def _on_replay_error(self, error, error_string: str):
        if not self._replay_active:
            return
        logger.warning(f"Replay failed ({error}): {error_string}")
        self._finish_replay(flush_remaining=False, stop_player=False)
        QMessageBox.warning(
            self.overlay, "Replay error", error_string or "Could not replay audio."
        )

    def _finish_replay(self, flush_remaining: bool, stop_player: bool):
        if not self._replay_active:
            self.overlay.set_replay_state("play")
            return
        self._replay_active = False
        self._replay_started = False
        self._replay_timer.stop()
        if stop_player:
            self._replay_player.stop()
        if flush_remaining:
            self._emit_remaining_replay_events()
        self.audio_capturer.set_processing_enabled(True)
        self.overlay.set_replay_state("play")
        self.overlay.set_recording_state(
            False, str(self._recorder.last_recording_path or "")
        )
        logger.info("Session replay stopped.")

    def _export_session(self):
        export_dir = Path.home() / "Documents" / "Translator" / "Exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        suggested = export_dir / f"session_{datetime.now():%Y%m%d_%H%M%S}.txt"
        selected, _ = QFileDialog.getSaveFileName(
            self.overlay,
            "Export complete session",
            str(suggested),
            "Text files (*.txt)",
        )
        if not selected:
            return
        try:
            output_path = self._session_transcript.export(
                selected, self._recorder.last_recording_path
            )
            logger.info(f"Session transcript exported: {output_path}")
            self.overlay.btn_export.setToolTip(f"Last export\n{output_path}")
        except Exception as error:
            logger.exception(f"Could not export session transcript: {error}")
            QMessageBox.warning(
                self.overlay, "Export error", f"Could not export session:\n{error}"
            )

    def run(self):
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.activateWindow()
        self.audio_capturer.start_capture()
        logger.info("English Call Assistant is running in LIVE capture mode. Overlay window displayed.")

        sys.exit(self.app.exec())

    def _shutdown(self):
        if self._shutdown_started:
            return
        self._shutdown_started = True
        if self._replay_active:
            self._finish_replay(flush_remaining=False, stop_player=True)
        self._recorder.close()
        self.audio_capturer.stop_capture()
        self._task_pool.shutdown()


if __name__ == "__main__":
    controller = AppController()
    controller.run()
