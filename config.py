"""
Global Configuration for Real-time English Call Assistant
"""
import os
import sys

class Config:
    # --- App Info ---
    APP_NAME = "English Call Assistant & Overlay"
    VERSION = "1.0.3"
    # PyInstaller exposes bundled read-only resources through _MEIPASS. Runtime
    # state must live outside Program Files so standard Windows users can write it.
    BASE_DIR = getattr(
        sys,
        "_MEIPASS",
        os.path.dirname(os.path.abspath(__file__)),
    )
    LOCAL_APP_DATA = os.getenv(
        "LOCALAPPDATA",
        os.path.join(os.path.expanduser("~"), "AppData", "Local"),
    )
    DATA_DIR = os.path.join(LOCAL_APP_DATA, "Translator")
    LOG_DIR = os.path.join(DATA_DIR, "Logs")
    WINDOW_STATE_PATH = os.path.join(DATA_DIR, "window_state.json")
    ICON_PATH_PNG = os.path.join(BASE_DIR, "assets", "app_icon.png")
    ICON_PATH_ICO = os.path.join(BASE_DIR, "assets", "app_icon.ico")
    VOSK_MODEL_PATH = os.path.join(
        BASE_DIR, "models", "vosk-model-small-en-us-0.15"
    )
    WHISPER_MODEL_PATH = os.path.join(
        BASE_DIR, "models", "faster-whisper-tiny.en"
    )

    # --- API Keys ---
    # Optional API keys for ultra-fast cloud services (Gemini, Groq, OpenAI)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    GEMINI_API_BASE = os.getenv(
        "GEMINI_API_BASE",
        "https://generativelanguage.googleapis.com/v1beta",
    ).rstrip("/")
    GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "6"))
    GEMINI_FAILURE_THRESHOLD = int(
        os.getenv("GEMINI_FAILURE_THRESHOLD", "2")
    )
    GEMINI_RETRY_COOLDOWN_SECONDS = float(
        os.getenv("GEMINI_RETRY_COOLDOWN_SECONDS", "30")
    )
    GEMINI_RATE_LIMIT_COOLDOWN_SECONDS = float(
        os.getenv("GEMINI_RATE_LIMIT_COOLDOWN_SECONDS", "120")
    )
    GEMINI_MAX_COOLDOWN_SECONDS = float(
        os.getenv("GEMINI_MAX_COOLDOWN_SECONDS", "300")
    )
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # --- Audio Capture Settings ---
    SAMPLE_RATE = 16000  # 16kHz for Speech Recognition
    CHANNELS = 1         # Mono
    CHUNK_SIZE = 1024
    VAD_SILENCE_THRESHOLD_MS = 500  # 500ms silence to detect end of speech
    MAX_UTTERANCE_SECONDS = float(
        os.getenv("TRANSLATOR_MAX_UTTERANCE_SECONDS", "6")
    )
    CAPTURE_MICROPHONE = os.getenv(
        "TRANSLATOR_CAPTURE_MICROPHONE", "1"
    ).strip().lower() not in {"0", "false", "no", "off"}
    MICROPHONE_VAD_THRESHOLD_MIN = float(
        os.getenv("TRANSLATOR_MICROPHONE_VAD_THRESHOLD_MIN", "180")
    )
    MICROPHONE_DUCK_WHEN_REMOTE = os.getenv(
        "TRANSLATOR_MICROPHONE_DUCK_WHEN_REMOTE", "1"
    ).strip().lower() not in {"0", "false", "no", "off"}
    MICROPHONE_DUCK_HOLD_SECONDS = float(
        os.getenv("TRANSLATOR_MICROPHONE_DUCK_HOLD_SECONDS", "0.8")
    )

    # --- Language Settings ---
    SOURCE_LANG = "en"
    TARGET_LANG = "vi"

    # --- UI Settings ---
    WINDOW_ALWAYS_ON_TOP = True
    WINDOW_OPACITY = 0.92  # Glass opacity (0.5 to 1.0)
    WINDOW_WIDTH = 840
    WINDOW_HEIGHT = 620
    FONT_FAMILY = "Segoe UI"
    FONT_SIZE_SUBTITLE = 13
    FONT_SIZE_EXPLANATION = 12
    FONT_SIZE_KEYWORDS = 12
    FONT_SIZE_REPLY = 13

    # --- Colors ---
    COLOR_BG = "rgba(20, 24, 33, 235)"
    COLOR_BORDER = "rgba(60, 75, 100, 180)"
    COLOR_TEXT_PRIMARY = "#FFFFFF"
    COLOR_TEXT_SECONDARY = "#A0AEC0"
    COLOR_ENGLSH_SUB = "#63B3ED"    # Soft blue
    COLOR_VIET_SUB = "#F6AD55"       # Soft orange
    COLOR_EXPLANATION = "#E9D8A6"    # Cream yellow
    COLOR_KEYWORDS = "#9AE6B4"       # Mint green
    COLOR_REPLY_EN = "#68D391"       # Soft green
    COLOR_REPLY_VI = "#CBD5E0"       # Light gray
