import sys
from PySide6.QtWidgets import QApplication

def copy_to_clipboard(text: str):
    """Copies given text to Windows system clipboard."""
    clipboard = QApplication.clipboard()
    if clipboard:
        clipboard.setText(text)
        return True
    return False

def clean_text(text: str) -> str:
    """Cleans up leading/trailing whitespaces and linebreaks."""
    if not text:
        return ""
    return text.strip()
