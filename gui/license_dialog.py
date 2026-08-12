"""About, license, privacy, and third-party notices for Translator."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QTextBrowser, QVBoxLayout

from config import Config


class LicenseDialog(QDialog):
    """A self-contained, readable license notice available from the app UI."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About Translator {Config.VERSION}")
        self.setMinimumSize(620, 500)
        if Config.ICON_PATH_ICO:
            self.setWindowIcon(QIcon(Config.ICON_PATH_ICO))

        layout = QVBoxLayout(self)
        title = QLabel(f"Translator  •  phiên bản {Config.VERSION}")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #E2E8F0;")
        layout.addWidget(title)

        browser = QTextBrowser(self)
        browser.setOpenExternalLinks(True)
        browser.setHtml(self._license_html())
        browser.setStyleSheet("""
            QTextBrowser { background: #0F172A; color: #CBD5E1; border: 1px solid #334155;
                           border-radius: 8px; padding: 10px; }
        """)
        layout.addWidget(browser, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    @staticmethod
    def _license_html():
        return """
        <h3>License agreement</h3>
        <p>Translator is proprietary software. You may install and use it on
        devices you own or control, subject to the terms supplied with your
        purchase or distribution package. You may not redistribute, sell,
        reverse engineer, or remove copyright and attribution notices without
        written permission from the application owner.</p>
        <p>This software is provided “as is”, without warranties to the maximum
        extent permitted by applicable law. The application is an assistance
        tool, not a substitute for professional interpretation or advice.</p>
        <h3>Privacy and recording</h3>
        <p>Audio, transcripts, recordings, and exports may contain sensitive
        information. Obtain consent before recording or processing a call.
        Local speech recognition and local files remain on this device. When
        enabled, selected conversation context is sent to the configured AI
        provider under that provider’s terms and privacy policy. API keys are
        read from your Windows user environment and are not bundled by this app.</p>
        <h3>Third-party software</h3>
        <p>Translator uses PySide6/Qt, Vosk, faster-whisper, NumPy, Requests,
        pyaudiowpatch, and pytest. Their respective licenses and notices apply
        to those components. See the project distribution package for the
        complete dependency metadata.</p>
        <p>Author: <a href="mailto:solesantn@gmail.com">solesantn@gmail.com</a><br>
        Copyright © 2026 Translator. All rights reserved.</p>
        """
