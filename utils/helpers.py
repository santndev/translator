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

def apply_opacity_to_hex(hex_str: str, opacity: float) -> str:
    """Applies an opacity multiplier (0.0 to 1.0) and returns an rgba() string."""
    hex_str = hex_str.strip().lstrip('#')
    if not hex_str: return "rgba(255, 255, 255, 1.0)"

    if len(hex_str) >= 6:
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)

        if len(hex_str) == 8:
            orig_alpha = int(hex_str[6:8], 16) / 255.0
            return f"rgba({r}, {g}, {b}, {orig_alpha * opacity})"
        else:
            return f"rgba({r}, {g}, {b}, {opacity})"

    return "rgba(255, 255, 255, 1.0)"
