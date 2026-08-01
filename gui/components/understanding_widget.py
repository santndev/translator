"""
Understanding Widget - Minimalist Results Display
- Live Subtitle Stack: English spoken transcript + Direct Vietnamese translation
- Context Insight: 1-line subtle italic pill badge
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea, QSizePolicy
from PySide6.QtCore import Qt
from config import Config

class UnderstandingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # --- LIVE SUBTITLE STACK (EN + VI) ---
        self.subtitle_box = QFrame(self)
        self.subtitle_box.setObjectName("SubtitleBox")
        self.subtitle_box.setStyleSheet("""
            QFrame#SubtitleBox {
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }
        """)
        box_layout = QVBoxLayout(self.subtitle_box)
        box_layout.setContentsMargins(4, 4, 4, 4)
        box_layout.setSpacing(0)

        # Sleek QScrollArea to prevent text truncation on long English speech / translations
        self.scroll_area = QScrollArea(self.subtitle_box)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll_area.setStyleSheet("""
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
                background: rgba(255, 255, 255, 0.25);
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.45);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        # Container inside ScrollArea
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        sub_layout = QVBoxLayout(self.scroll_content)
        sub_layout.setContentsMargins(10, 8, 10, 12)
        sub_layout.setSpacing(6)

        # Live Stream 1c (Realtime Word-by-Word Concatenating Stream - Soft Cyan Badge)
        self.lbl_stream1c = QLabel("⚡ Live Stream 1c: Đang chờ giọng nói...", self.scroll_content)
        self.lbl_stream1c.setWordWrap(True)
        self.lbl_stream1c.setStyleSheet("""
            color: #38BDF8;
            font-size: 11px;
            font-weight: 500;
            font-style: italic;
            padding: 1px 0px 3px 0px;
        """)
        sub_layout.addWidget(self.lbl_stream1c)

        # Live English Transcript (Clean stacked text with soft blue accent)
        self.lbl_en_text = QLabel("Listening for English speech...", self.scroll_content)
        self.lbl_en_text.setWordWrap(True)
        self.lbl_en_text.setStyleSheet(f"""
            color: {getattr(Config, 'COLOR_ENGLSH_SUB', '#63B3ED')};
            font-size: 13px;
            font-weight: 600;
            line-height: 1.4;
            padding: 2px 0px;
        """)
        sub_layout.addWidget(self.lbl_en_text)

        # Direct Vietnamese Translation (Soft orange/amber accent)
        self.lbl_vi_trans = QLabel("Bản dịch tiếng Việt...", self.scroll_content)
        self.lbl_vi_trans.setWordWrap(True)
        self.lbl_vi_trans.setStyleSheet(f"""
            color: {getattr(Config, 'COLOR_VIET_SUB', '#F6AD55')};
            font-size: 12px;
            font-weight: 400;
            line-height: 1.4;
            padding: 2px 0px 4px 0px;
        """)
        sub_layout.addWidget(self.lbl_vi_trans)

        self.scroll_area.setWidget(self.scroll_content)
        box_layout.addWidget(self.scroll_area)


        # Dynamic expanding size policy so text region scales with window height
        self.subtitle_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.subtitle_box.setMinimumHeight(120)

        layout.addWidget(self.subtitle_box, 1)


        # --- CONTEXT INSIGHT (1-Line Subtle Italic Pill) ---
        self.pill_insight = QFrame(self)
        self.pill_insight.setStyleSheet("""
            QFrame {
                background-color: rgba(233, 216, 166, 0.08);
                border: 1px solid rgba(233, 216, 166, 0.18);
                border-radius: 10px;
            }
        """)
        pill_layout = QVBoxLayout(self.pill_insight)
        pill_layout.setContentsMargins(10, 5, 10, 5)

        self.lbl_explanation = QLabel("💡 Analyzing context...", self.pill_insight)
        self.lbl_explanation.setWordWrap(True)
        self.lbl_explanation.setStyleSheet(f"""
            color: {getattr(Config, 'COLOR_EXPLANATION', '#E9D8A6')};
            font-size: 10px;
            font-style: italic;
            line-height: 1.4;
            padding: 2px 0px;
        """)
        pill_layout.addWidget(self.lbl_explanation)

        layout.addWidget(self.pill_insight)

    def update_partial_speech(self, partial_text: str):
        """Word-by-word real-time streaming update while speaker is mid-sentence."""
        if partial_text and partial_text.strip():
            self.lbl_en_text.setText(f"🎙️ {partial_text.strip()} ...")
            self.lbl_explanation.setText(f"💡 Đang lắng nghe: '{partial_text.strip()[:60]}...'")

    def update_stream1c(self, text: str):
        """Updates Stream 1c: Independent live word-by-word streaming text."""
        if text and text.strip():
            self.lbl_stream1c.setText(f"⚡ Live Stream 1c: {text.strip()}")

    def update_stream1a(self, english_text: str, vietnamese_trans: str):
        """Updates Stream 1a: Live English transcript and Vietnamese translation."""
        self.lbl_en_text.setText(english_text if english_text else "Listening for English speech...")
        self.lbl_vi_trans.setText(vietnamese_trans if vietnamese_trans else "Bản dịch tiếng Việt...")


    def update_stream1b(self, explanation_text: str):
        """Updates Stream 1b: Context & intent explanation in Vietnamese."""
        if explanation_text:
            text = explanation_text if explanation_text.startswith("💡") else f"💡 {explanation_text}"
            self.lbl_explanation.setText(text)
        else:
            self.lbl_explanation.setText("💡 Analyzing context...")

    def update_font_scale(self, scale: float):
        """Scales font sizes based on fit-contain window resize scale factor."""
        sz_en = max(12, min(22, int(round(13 * scale))))
        sz_vi = max(11, min(17, int(round(12 * scale))))
        sz_exp = max(9, min(14, int(round(10 * scale))))

        self.lbl_en_text.setStyleSheet(f"""
            color: {getattr(Config, 'COLOR_ENGLSH_SUB', '#63B3ED')};
            font-size: {sz_en}px;
            font-weight: 600;
            line-height: 1.4;
            padding: 2px 0px;
        """)
        self.lbl_vi_trans.setStyleSheet(f"""
            color: {getattr(Config, 'COLOR_VIET_SUB', '#F6AD55')};
            font-size: {sz_vi}px;
            font-weight: 400;
            line-height: 1.4;
            padding: 2px 0px 4px 0px;
        """)
        self.lbl_explanation.setStyleSheet(f"""
            color: {getattr(Config, 'COLOR_EXPLANATION', '#E9D8A6')};
            font-size: {sz_exp}px;
            font-style: italic;
            line-height: 1.4;
            padding: 2px 0px;
        """)



