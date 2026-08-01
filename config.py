"""
Global Configuration for Real-time English Call Assistant
"""
import os

class Config:
    # --- App Info ---
    APP_NAME = "English Call Assistant & Overlay"
    VERSION = "1.0.0"
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ICON_PATH_PNG = os.path.join(BASE_DIR, "assets", "app_icon.png")
    ICON_PATH_ICO = os.path.join(BASE_DIR, "assets", "app_icon.ico")

    # --- API Keys ---
    # Optional API keys for ultra-fast cloud services (Gemini, Groq, OpenAI)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # --- Audio Capture Settings ---
    SAMPLE_RATE = 16000  # 16kHz for Speech Recognition
    CHANNELS = 1         # Mono
    CHUNK_SIZE = 1024
    VAD_SILENCE_THRESHOLD_MS = 500  # 500ms silence to detect end of speech

    # --- Language Settings ---
    SOURCE_LANG = "en"
    TARGET_LANG = "vi"

    # --- UI Settings ---
    WINDOW_ALWAYS_ON_TOP = True
    WINDOW_OPACITY = 0.92  # Glass opacity (0.5 to 1.0)
    WINDOW_WIDTH = 520
    WINDOW_HEIGHT = 450
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
