"""
Smart Reply Widget - Minimalist Results Display
- Stream 2a: Flash Keywords (Minimal pill badges/chips)
- Stream 2b: Best English Reply (Clean prominent answer card with subtle 1-click copy action)
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QScrollArea, QSizePolicy, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer
from config import Config
from utils.helpers import copy_to_clipboard

class SmartReplyWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_reply_en = ""
        self.current_scale = 1.0
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # --- FLASH KEYWORDS (Minimal Pill Badges / Chips) ---
        self.keywords_container = QWidget(self)
        self.chips_layout = QHBoxLayout(self.keywords_container)
        self.chips_layout.setContentsMargins(0, 0, 0, 0)
        self.chips_layout.setSpacing(6)

        # Initial placeholder chip
        self._add_chip_badge("⚡ Keywords", "#10B981")
        self.chips_layout.addStretch()

        layout.addWidget(self.keywords_container)

        # --- BEST ENGLISH REPLY CARD ---
        self.reply_card = QFrame(self)
        self.reply_card.setObjectName("ReplyCard")
        self.reply_card.setStyleSheet("""
            QFrame#ReplyCard {
                background-color: rgba(16, 185, 129, 0.07);
                border: 1px solid rgba(16, 185, 129, 0.25);
                border-radius: 10px;
            }
        """)
        card_layout = QVBoxLayout(self.reply_card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(6)

        # Card Header: Subdued Tag + 1-Click Copy Button
        card_header = QHBoxLayout()
        card_header.setContentsMargins(0, 0, 0, 0)
        card_header.setSpacing(8)

        lbl_tag = QLabel("RECOMMENDED REPLY", self.reply_card)
        lbl_tag.setStyleSheet("""
            color: #10B981;
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 0.8px;
        """)
        card_header.addWidget(lbl_tag)

        card_header.addStretch()

        # Sleek 1-Click Copy Action Button
        self.btn_copy = QPushButton("📋 Copy", self.reply_card)
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background-color: rgba(16, 185, 129, 0.15);
                color: #A7F3D0;
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(16, 185, 129, 0.3);
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: rgba(16, 185, 129, 0.4);
            }
        """)
        self.btn_copy.clicked.connect(self.on_copy_clicked)
        card_header.addWidget(self.btn_copy)

        card_layout.addLayout(card_header)

        # Scroll area for reply content if reply is long
        self.reply_scroll = QScrollArea(self.reply_card)
        self.reply_scroll.setWidgetResizable(True)
        self.reply_scroll.setFrameShape(QFrame.NoFrame)
        self.reply_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.reply_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.reply_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: rgba(255, 255, 255, 0.03);
                width: 6px;
                border-radius: 3px;
                margin: 2px 0 2px 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(16, 185, 129, 0.3);
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(16, 185, 129, 0.5);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        reply_content = QWidget()
        reply_content.setStyleSheet("background: transparent;")
        reply_content_layout = QVBoxLayout(reply_content)
        reply_content_layout.setContentsMargins(0, 0, 0, 4)
        reply_content_layout.setSpacing(4)

        # Prominent English Reply
        self.lbl_reply_en = QLabel("Waiting for reply suggestion...", reply_content)
        self.lbl_reply_en.setWordWrap(True)
        self.lbl_reply_en.setStyleSheet(f"""
            color: {getattr(Config, 'COLOR_REPLY_EN', '#68D391')};
            font-size: 13px;
            font-weight: bold;

            padding: 2px 0px;
        """)
        reply_content_layout.addWidget(self.lbl_reply_en)

        # Vietnamese Translation of Response
        self.lbl_reply_vi = QLabel("Dịch nghĩa câu trả lời...", reply_content)
        self.lbl_reply_vi.setWordWrap(True)
        self.lbl_reply_vi.setStyleSheet(f"""
            color: {getattr(Config, 'COLOR_REPLY_VI', '#CBD5E0')};
            font-size: 12px;
            font-style: italic;

            padding: 2px 0px 4px 0px;
        """)
        reply_content_layout.addWidget(self.lbl_reply_vi)

        self.reply_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.reply_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.reply_scroll.setWidgetResizable(True)
        self.reply_scroll.setWidget(reply_content)
        self.reply_scroll.setMinimumHeight(75)

        card_layout.addWidget(self.reply_scroll)

        layout.addWidget(self.reply_card, 1)


    def _clear_chips(self):
        """Removes all items from chips_layout."""
        while self.chips_layout.count():
            item = self.chips_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _add_chip_badge(self, text: str, accent_color: str = "#10B981"):
        """Creates a sleek, minimal pill badge with proportional scaling."""
        chip = QLabel(text, self.keywords_container)
        scale = getattr(self, 'current_scale', 1.0)
        sz_chip = max(10, min(14, int(round(11 * scale))))
        pad_v = max(4, min(6, int(round(4 * scale))))
        pad_h = max(10, min(16, int(round(10 * scale))))
        chip.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(16, 185, 129, 0.12);
                color: #6EE7B7;
                border: 1px solid rgba(16, 185, 129, 0.25);
                border-radius: 9px;
                padding: {pad_v}px {pad_h}px;
                font-size: {sz_chip}px;
                font-weight: 600;
            }}
        """)
        self.chips_layout.addWidget(chip)

    def update_stream2a(self, keywords_text: str):
        """Updates Stream 2a: Flash keywords (< 150ms) as pill badges."""
        self._clear_chips()
        if keywords_text:
            # Parse keywords separated by commas, slashes, or semicolons
            raw_items = keywords_text.replace(';', ',').replace('/', ',').split(',')
            cleaned_items = [k.strip() for k in raw_items if k.strip()]
            if cleaned_items:
                for item in cleaned_items:
                    self._add_chip_badge(item)
            else:
                self._add_chip_badge(keywords_text)
        else:
            self._add_chip_badge("⚡ Keywords")
        self.chips_layout.addStretch()

    def update_stream2b(self, response_en: str, response_vi: str):
        """Updates Stream 2b: Full English response and Vietnamese meaning (< 400ms)."""
        self.current_reply_en = response_en
        self.lbl_reply_en.setText(response_en if response_en else "Waiting for reply suggestion...")
        self.lbl_reply_vi.setText(response_vi if response_vi else "Dịch nghĩa câu trả lời...")

    def update_font_scale(self, scale: float):
        """Scales font sizes based on fit-contain window resize scale factor."""
        self.current_scale = scale
        sz_en = max(12, min(22, int(round(13 * scale))))
        sz_vi = max(11, min(17, int(round(12 * scale))))
        sz_chip = max(10, min(14, int(round(11 * scale))))
        pad_v = max(4, min(6, int(round(4 * scale))))
        pad_h = max(10, min(16, int(round(10 * scale))))

        self.lbl_reply_en.setStyleSheet(f"""
            color: {getattr(Config, 'COLOR_REPLY_EN', '#68D391')};
            font-size: {sz_en}px;
            font-weight: bold;

            padding: 2px 0px;
        """)
        self.lbl_reply_vi.setStyleSheet(f"""
            color: {getattr(Config, 'COLOR_REPLY_VI', '#CBD5E0')};
            font-size: {sz_vi}px;
            font-style: italic;

            padding: 2px 0px 4px 0px;
        """)

        # Dynamically scale existing chip badges in keywords_container
        for i in range(self.chips_layout.count()):
            item = self.chips_layout.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, QLabel):
                widget.setStyleSheet(f"""
                    QLabel {{
                        background-color: rgba(16, 185, 129, 0.12);
                        color: #6EE7B7;
                        border: 1px solid rgba(16, 185, 129, 0.25);
                        border-radius: 9px;
                        padding: {pad_v}px {pad_h}px;
                        font-size: {sz_chip}px;
                        font-weight: 600;
                    }}
                """)

    def update_window_opacity(self, opacity_multiplier: float):
        """Fades out the reply card background and border based on window opacity."""
        bg_alpha = int(255 * 0.07 * opacity_multiplier)
        border_alpha = int(255 * 0.25 * opacity_multiplier)
        self.reply_card.setStyleSheet(f"""
            QFrame#ReplyCard {{
                background-color: rgba(16, 185, 129, {bg_alpha});
                border: 1px solid rgba(16, 185, 129, {border_alpha});
                border-radius: 10px;
            }}
        """)

    def on_copy_clicked(self):

        """Copies the English reply to Windows clipboard."""
        if self.current_reply_en:
            copy_to_clipboard(self.current_reply_en)
            self.btn_copy.setText("✓ Copied!")
            QTimer.singleShot(1500, lambda: self.btn_copy.setText("📋 Copy"))

    def update_text_opacity(self, opacity: float):
        """Updates text opacity safely via CSS RGBA."""
        from utils.helpers import apply_opacity_to_hex

        color_en = apply_opacity_to_hex(getattr(Config, 'COLOR_REPLY_EN', '#68D391'), opacity)
        self.lbl_reply_en.setStyleSheet(f"""
            color: {color_en};
            font-size: {max(12, min(22, int(round(13 * self.current_scale))))}px;
            font-weight: bold;
            padding: 2px 0px;
        """)

        color_vi = apply_opacity_to_hex(getattr(Config, 'COLOR_REPLY_VI', '#CBD5E0'), opacity)
        self.lbl_reply_vi.setStyleSheet(f"""
            color: {color_vi};
            font-size: {max(11, min(17, int(round(12 * self.current_scale))))}px;
            font-style: italic;
            padding: 2px 0px 4px 0px;
        """)

        bg_color = apply_opacity_to_hex("#10B98126", opacity)
        text_color = apply_opacity_to_hex("#10B981", opacity)
        border_color = apply_opacity_to_hex("#10B9814D", opacity)

        for i in range(self.chips_layout.count()):
            item = self.chips_layout.itemAt(i)
            if item.widget() and isinstance(item.widget(), QLabel):
                item.widget().setStyleSheet(f"""
                    QLabel {{
                        background-color: {bg_color};
                        color: {text_color};
                        border: 1px solid {border_color};
                        border-radius: {int(12 * self.current_scale)}px;
                        padding: {int(4 * self.current_scale)}px {int(10 * self.current_scale)}px;
                        font-size: {int(11 * self.current_scale)}px;
                        font-weight: 600;
                    }}
                """)
