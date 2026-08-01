"""
Main Entry Point for English Call Assistant & Dual-Stream Overlay Window
"""
import sys
import os
import threading
import time

# IMPORT CORE ENGINES FIRST TO PREVENT PYSIDE6 SHIBOKEN IMPORT BUGS WITH VOSK/REQUESTS
from config import Config
from core.audio_capturer import AudioCapturer
from core.translator_engine import TranslatorEngine
from core.smart_reply_engine import SmartReplyEngine
from core.stt_engine import STTEngine
import ctypes
from utils.logger import logger

# THEN IMPORT PYSIDE6
from PySide6.QtWidgets import QApplication, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt, QLockFile, QDir
from PySide6.QtGui import QIcon

from gui.overlay_window import OverlayWindow

# Windows Taskbar App ID setup for icon grouping and taskbar icon display
if sys.platform == "win32":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("translator.englishcallassistant.app.1.0")
    except Exception:
        pass

class AppController:
    def __init__(self):
        # Single Instance Lock Enforcement (Prevent multiple app instances)
        self.lock_file = QLockFile(os.path.join(QDir.tempPath(), "english_call_assistant.lock"))
        if not self.lock_file.tryLock(100):
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


        # Initialize Core Engines
        self.stt_engine = STTEngine(model_size="tiny.en")
        self.translator = TranslatorEngine()
        self.smart_reply = SmartReplyEngine()
        self.audio_capturer = AudioCapturer(
            callback_on_speech=self.on_audio_received,
            stt_engine=self.stt_engine,
            callback_audio_activity=self.on_audio_activity_event,
            callback_partial_speech=self.on_partial_audio_received
        )

    def on_audio_activity_event(self, is_capturing: bool, volume: float):
        """Emits thread-safe signal to update visual audio indicator on top bar."""
        self.overlay.signal_audio_activity.emit(is_capturing, volume)

    def on_partial_audio_received(self, channel_type: str, partial_text: str):
        """Luồng 1c: Independent live word-by-word streaming display."""
        if channel_type == "incoming":
            self.overlay.signal_stream1c.emit(partial_text.strip())



    def process_incoming_speech(self, english_text: str):
        """
        Processes incoming English audio through all 4 streams in parallel threads.
        """
        logger.info(f"Processing Incoming English Speech: '{english_text}'")

        # --- LUỒNG 1A: Dịch Realtime (Live Subtitle - Instant 0ms English Display) ---
        # 1. Emit English transcript IMMEDIATELY (0ms delay)
        self.overlay.signal_stream1a.emit(english_text, "Đang dịch...")

        def run_stream_1a():
            # 2. Fetch Vietnamese translation asynchronously and update line
            vi_trans = self.translator.translate_en_to_vi(english_text)
            logger.info(f"[STREAM 1A] EN: '{english_text}' -> VI: '{vi_trans}'")
            self.overlay.signal_stream1a.emit(english_text, vi_trans)


        # --- LUỒNG 1B: Giải thích Ý nghĩa Tiếng Việt ---
        def run_stream_1b():
            vi_explanation = self.translator.explain_context_vi(english_text)
            logger.info(f"[STREAM 1B] Context: '{vi_explanation}'")
            self.overlay.signal_stream1b.emit(vi_explanation)

        # --- LUỒNG 2A: Từ khóa siêu tốc (< 150ms) ---
        def run_stream_2a():
            keywords = self.smart_reply.generate_stream_2a_keywords(english_text)
            logger.info(f"[STREAM 2A] Keywords: '{keywords}'")
            self.overlay.signal_stream2a.emit(keywords)

        # --- LUỒNG 2B: Câu trả lời Tiếng Anh chuẩn mực (< 400ms) ---
        def run_stream_2b():
            response_dict = self.smart_reply.generate_stream_2b_response(english_text)
            logger.info(f"[STREAM 2B] Reply EN: '{response_dict['english']}' | Reply VI: '{response_dict['vietnamese']}'")
            self.overlay.signal_stream2b.emit(response_dict["english"], response_dict["vietnamese"])

        # Execute parallel workers for minimal latency
        threading.Thread(target=run_stream_1a, daemon=True).start()
        threading.Thread(target=run_stream_1b, daemon=True).start()
        threading.Thread(target=run_stream_2a, daemon=True).start()
        threading.Thread(target=run_stream_2b, daemon=True).start()

    def on_audio_received(self, channel_type: str, text_payload: str, raw_bytes: bytes = None):
        """Callback triggered when audio/speech is captured or injected."""
        if channel_type == "incoming":
            self.process_incoming_speech(text_payload)

    def run(self):
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.activateWindow()
        self.audio_capturer.start_capture()
        logger.info("English Call Assistant is running in LIVE capture mode. Overlay window displayed.")

        sys.exit(self.app.exec())


if __name__ == "__main__":
    controller = AppController()
    controller.run()

