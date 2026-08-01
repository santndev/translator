"""
Understanding Widget - Minimalist Results Display
- Live Subtitle Stack: English spoken transcript + Direct Vietnamese translation
- Context Insight: Rolling buffer explanation
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QSizePolicy
from PySide6.QtCore import Qt
from config import Config

class UnderstandingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.stream1c_buffer = []
        self.current_partial_1c = ""
        
        self.stream1a_buffer = []  # list of (en_text, vi_text)
        self.current_partial_en = ""
        
        self.stream1b_buffer = []  # list of explanation strings
        self.current_partial_exp = ""

        self.color_en = getattr(Config, 'COLOR_ENGLSH_SUB', '#63B3ED')
        self.color_vi = getattr(Config, 'COLOR_VIET_SUB', '#F6AD55')
        self.color_exp = getattr(Config, 'COLOR_EXPLANATION', '#E9D8A6')
        self.color_1c = '#E0F2FE'  
        self.color_1c_pending = '#7DD3FC' 

        self.sz_en = 13
        self.sz_vi = 12
        self.sz_exp = 10
        self.sz_1c = 13

        self.init_ui()

    def _create_scroll_area(self, parent):
        scroll_area = QScrollArea(parent)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
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
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.45); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent; border: none;")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(10, 8, 10, 8)
        content_layout.setSpacing(4)
        content_layout.setAlignment(Qt.AlignTop)
        
        lbl = QLabel("", scroll_content)
        lbl.setTextFormat(Qt.RichText)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        content_layout.addWidget(lbl)
        
        scroll_area.setWidget(scroll_content)
        return scroll_area, lbl

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Main glassmorphic container
        self.main_box = QFrame(self)
        self.main_box.setObjectName("MainBox")
        self.main_box.setStyleSheet("""
            QFrame#MainBox {
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }
        """)
        main_layout = QHBoxLayout(self.main_box)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(8)

        self.scroll_1c, self.lbl_1c = self._create_scroll_area(self.main_box)
        self.scroll_1a, self.lbl_1a = self._create_scroll_area(self.main_box)
        self.scroll_1b, self.lbl_1b = self._create_scroll_area(self.main_box)

        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.scroll_1c, 1)

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        
        right_layout.addWidget(self.scroll_1a, 2)

        line_h = QFrame(self.main_box)
        line_h.setFrameShape(QFrame.HLine)
        line_h.setStyleSheet("background-color: rgba(255, 255, 255, 0.05); border: none; max-height: 1px;")
        right_layout.addWidget(line_h)

        right_layout.addWidget(self.scroll_1b, 1)

        main_layout.addLayout(left_layout, 3)
        
        line_v = QFrame(self.main_box)
        line_v.setFrameShape(QFrame.VLine)
        line_v.setStyleSheet("background-color: rgba(255, 255, 255, 0.05); border: none; max-width: 1px;")
        main_layout.addWidget(line_v)
        
        main_layout.addLayout(right_layout, 7)

        layout.addWidget(self.main_box)
        
        self.update_font_scale(1.0)

    def _scroll_to_bottom(self, scroll_area):
        vsb = scroll_area.verticalScrollBar()
        if vsb:
            vsb.setValue(vsb.maximum())

    def _render_stream1c(self):
        html_parts = []
        for line in self.stream1c_buffer:
            html_parts.append(f"<span style='color: {self.color_1c}; font-size: {self.sz_1c}px; font-weight: 500;'>{line}</span>")
            
        if self.current_partial_1c:
            html_parts.append(f"<span style='color: {self.color_1c_pending}; font-size: {self.sz_1c}px; font-weight: 500;'>{self.current_partial_1c} ...</span>")
            
        if not html_parts:
            html = f"<span style='color: {self.color_1c_pending}; font-size: {self.sz_1c}px;'>Đang chờ giọng nói...</span>"
        else:
            html = "<br><br>".join(html_parts)
            
        self.lbl_1c.setText(html)

    def _render_stream1a(self):
        html_parts = []
        for i, (en, vi) in enumerate(self.stream1a_buffer):
            pair_html = f"<span style='color: {self.color_en}; font-size: {self.sz_en}px; font-weight: 600;'>{en}</span>"
            if vi:
                pair_html += f"<br><span style='color: {self.color_vi}; font-size: {self.sz_vi}px; font-weight: 400;'>{vi}</span>"
            html_parts.append(pair_html)
        
        if self.current_partial_en:
            html_parts.append(f"<span style='color: {self.color_en}; font-size: {self.sz_en}px; font-weight: 600;'>{self.current_partial_en}</span>")
            
        if not html_parts:
            html = f"<span style='color: {self.color_en}; font-size: {self.sz_en}px;'>Listening for English speech...</span>"
        else:
            html = "<br><br>".join(html_parts)
            
        self.lbl_1a.setText(html)

    def _render_stream1b(self):
        html_parts = []
        for exp in self.stream1b_buffer:
            html_parts.append(f"<span style='color: {self.color_exp}; font-size: {self.sz_exp}px; font-style: italic;'>{exp}</span>")
            
        if self.current_partial_exp:
            html_parts.append(f"<span style='color: {self.color_exp}; font-size: {self.sz_exp}px; font-style: italic;'>{self.current_partial_exp}</span>")
            
        if not html_parts:
            html = f"<span style='color: {self.color_exp}; font-size: {self.sz_exp}px; font-style: italic;'>💡 Analyzing context...</span>"
        else:
            html = "<br><br>".join(html_parts)
            
        self.lbl_1b.setText(html)

    def update_partial_speech(self, partial_text: str):
        if partial_text and partial_text.strip():
            self.current_partial_en = f"🎙️ {partial_text.strip()} ..."
            self.current_partial_exp = f"💡 Đang lắng nghe: '{partial_text.strip()[:60]}...'"
            self._render_stream1a()
            self._render_stream1b()

    def update_stream1c(self, text: str):
        if text == "":
            if self.current_partial_1c:
                self.stream1c_buffer.append(self.current_partial_1c)
                self.current_partial_1c = ""
            if len(self.stream1c_buffer) > 3:
                self.stream1c_buffer.pop(0)
        else:
            self.current_partial_1c = text

        self._render_stream1c()
        self._scroll_to_bottom(self.scroll_1c)

    def update_stream1a(self, english_text: str, vietnamese_trans: str):
        self.current_partial_en = ""
        if self.stream1a_buffer and self.stream1a_buffer[-1][0] == english_text:
            self.stream1a_buffer[-1] = (english_text, vietnamese_trans)
        else:
            self.stream1a_buffer.append((english_text, vietnamese_trans))
            if len(self.stream1a_buffer) > 3:
                self.stream1a_buffer.pop(0)
        
        self._render_stream1a()
        self._scroll_to_bottom(self.scroll_1a)

    def update_stream1b(self, explanation_text: str):
        self.current_partial_exp = ""
        if explanation_text:
            text = explanation_text if explanation_text.startswith("💡") else f"💡 {explanation_text}"
            self.stream1b_buffer.append(text)
            if len(self.stream1b_buffer) > 3:
                self.stream1b_buffer.pop(0)
                
        self._render_stream1b()
        self._scroll_to_bottom(self.scroll_1b)

    def update_font_scale(self, scale: float):
        self.sz_en = max(12, min(22, int(round(13 * scale))))
        self.sz_vi = max(11, min(17, int(round(12 * scale))))
        self.sz_exp = max(9, min(14, int(round(10 * scale))))
        self.sz_1c = max(11, min(18, int(round(13 * scale))))

        self._render_stream1c()
        self._render_stream1a()
        self._render_stream1b()
