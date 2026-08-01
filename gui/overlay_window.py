"""
Always-On-Top Glassmorphic Floating Overlay Window
Integrates UnderstandingWidget (Stream 1a, 1b) and SmartReplyWidget (Stream 2a, 2b)
"""
import math
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QGraphicsDropShadowEffect, QApplication, QCheckBox
)

from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap

from config import Config
from gui.components.understanding_widget import UnderstandingWidget
from gui.components.smart_reply_widget import SmartReplyWidget
from utils.logger import logger

import os
import json

class OverlayWindow(QMainWindow):
    # Signals for thread-safe UI updates across all streams
    signal_stream1a = Signal(str, str)   # en_text, vi_trans
    signal_stream1b = Signal(str)        # explanation_text
    signal_stream1c = Signal(str)        # live word-by-word streaming text
    signal_stream2a = Signal(str)        # keywords_text
    signal_stream2b = Signal(str, str)   # response_en, response_vi
    signal_audio_activity = Signal(bool, float)  # is_capturing, volume_energy
    signal_partial_speech = Signal(str)  # live word-by-word streaming text


    def __init__(self):
        super().__init__()
        self.drag_position = QPoint()
        self.is_locked = False
        self.state_file = os.path.join(os.path.dirname(__file__), "..", "window_state.json")
        
        self.init_window_flags()
        self.init_ui()
        self.connect_signals()

    def init_window_flags(self):
        """Sets Window Title, Always-On-Top, and restores saved position & size."""
        self.setWindowTitle("English Call Assistant & Overlay")
        if os.path.exists(Config.ICON_PATH_ICO):
            self.setWindowIcon(QIcon(Config.ICON_PATH_ICO))
        elif os.path.exists(Config.ICON_PATH_PNG):
            self.setWindowIcon(QIcon(Config.ICON_PATH_PNG))

        self.setWindowFlags(
            Qt.Window |
            Qt.WindowStaysOnTopHint
        )
        self.setMinimumSize(420, 320)
        
        # Load saved window position & size if available
        if not self.load_window_state():
            self.resize(Config.WINDOW_WIDTH, getattr(Config, 'WINDOW_HEIGHT', 450))
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.geometry()
                x = (geo.width() - Config.WINDOW_WIDTH) // 2
                y = (geo.height() - getattr(Config, 'WINDOW_HEIGHT', 450)) // 2
                self.move(x, y)

    def save_window_state(self):
        """Saves current window position and size to window_state.json."""
        try:
            state = {
                "x": self.x(),
                "y": self.y(),
                "width": self.width(),
                "height": self.height()
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f)
        except Exception:
            pass

    def load_window_state(self) -> bool:
        """Restores window position and size from window_state.json."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    self.resize(state.get("width", 480), state.get("height", 450))
                    self.move(state.get("x", 100), state.get("y", 100))
                    return True
        except Exception:
            pass
        return False


    def init_ui(self):
        # Main Central Container Widget
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        # Sleek dark slate blue background (#0F172A with 250/255 opacity) for ultra-clear contrast
        self.central_widget.setStyleSheet("""
            QWidget#CentralWidget {
                background-color: rgba(15, 23, 42, 250);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 12px;
            }
        """)
        self.central_widget.setObjectName("CentralWidget")

        # Soft Drop Shadow Effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 6)
        self.central_widget.setGraphicsEffect(shadow)

        # Main Layout
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(12, 10, 12, 12)
        main_layout.setSpacing(8)

        # --- TOP DRAG BAR ---
        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(4, 4, 4, 6)
        self.header_layout.setSpacing(8)

        # Dot Status Indicator + App Title
        self.status_title_box = QWidget(self)
        st_layout = QHBoxLayout(self.status_title_box)
        st_layout.setContentsMargins(2, 0, 4, 0)
        st_layout.setSpacing(6)

        # Mini App Icon Logo
        icon_path = Config.ICON_PATH_PNG if os.path.exists(Config.ICON_PATH_PNG) else Config.ICON_PATH_ICO
        if os.path.exists(icon_path):
            lbl_icon = QLabel(self.status_title_box)
            pix = QPixmap(icon_path).scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl_icon.setPixmap(pix)
            st_layout.addWidget(lbl_icon)

        self.dot_indicator = QLabel("●", self.status_title_box)
        self.dot_indicator.setStyleSheet("color: #10B981; font-size: 10px;")
        st_layout.addWidget(self.dot_indicator)

        self.lbl_title = QLabel("TRANSLATOR", self.status_title_box)
        self.lbl_title.setStyleSheet("color: #F1F5F9; font-weight: 700; font-size: 11px; letter-spacing: 0.5px;")
        st_layout.addWidget(self.lbl_title)

        # Visual Audio Activity Indicator (Shows 🔊 Catching Sound in real-time)
        self.lbl_audio_wave = QLabel("🎙️ Ready", self.status_title_box)
        self.lbl_audio_wave.setStyleSheet("""
            color: #94A3B8;
            font-size: 10px;
            font-weight: 600;
            background: rgba(255, 255, 255, 0.05);
            padding: 2px 6px;
            border-radius: 4px;
        """)
        st_layout.addWidget(self.lbl_audio_wave)
        self.header_layout.addWidget(self.status_title_box)
        self.header_layout.addStretch()

        # Lock Position Toggle Button
        self.btn_lock = QPushButton("🔓", self)
        self.btn_lock.setCheckable(True)
        self.btn_lock.setCursor(Qt.PointingHandCursor)
        self.btn_lock.setToolTip("Lock / Unlock Window Dragging")
        self.btn_lock.setFixedSize(26, 26)
        self.btn_lock.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #A0AEC0;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
                color: #FFFFFF;
            }
            QPushButton:checked {
                background-color: rgba(239, 68, 68, 0.25);
                color: #FCA5A5;
                border: 1px solid rgba(239, 68, 68, 0.5);
            }
        """)
        self.btn_lock.toggled.connect(self.toggle_lock_position)
        self.header_layout.addWidget(self.btn_lock)

        # Window Opacity Slider
        self.lbl_win_op = QLabel("🪟", self)
        self.lbl_win_op.setToolTip("Window Opacity")
        self.lbl_win_op.setStyleSheet("color: #94A3B8; font-size: 11px;")
        self.header_layout.addWidget(self.lbl_win_op)

        self.slider_opacity = QSlider(Qt.Horizontal, self)
        self.slider_opacity.setRange(40, 100)
        self.slider_opacity.setValue(int(Config.WINDOW_OPACITY * 100))
        self.slider_opacity.setFixedWidth(55)
        self.slider_opacity.setCursor(Qt.PointingHandCursor)
        self.slider_opacity.setToolTip("Window Opacity")
        self.slider_opacity.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: rgba(255, 255, 255, 0.15);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #10B981;
                width: 12px;
                height: 12px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #34D399;
            }
        """)
        self.slider_opacity.valueChanged.connect(self.change_opacity)
        self.header_layout.addWidget(self.slider_opacity)

        # Stream Text Opacity Slider (Adjusts text opacity only)
        self.lbl_txt_op = QLabel("🔤", self)
        self.lbl_txt_op.setToolTip("Stream Text Opacity")
        self.lbl_txt_op.setStyleSheet("color: #94A3B8; font-size: 11px;")
        self.header_layout.addWidget(self.lbl_txt_op)

        self.slider_text_opacity = QSlider(Qt.Horizontal, self)
        self.slider_text_opacity.setRange(20, 100)
        self.slider_text_opacity.setValue(100)
        self.slider_text_opacity.setFixedWidth(55)
        self.slider_text_opacity.setCursor(Qt.PointingHandCursor)
        self.slider_text_opacity.setToolTip("Stream Text Opacity")
        self.slider_text_opacity.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: rgba(255, 255, 255, 0.15);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #38BDF8;
                width: 12px;
                height: 12px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #7DD3FC;
            }
        """)
        self.slider_text_opacity.valueChanged.connect(self.change_text_opacity)
        self.header_layout.addWidget(self.slider_text_opacity)

        # Taskbar Icon Visibility Checkbox (Default: Unchecked -> App Icon visible on Taskbar)
        self.chk_hide_taskbar = QCheckBox("Hide Taskbar", self)
        self.chk_hide_taskbar.setChecked(False)
        self.chk_hide_taskbar.setCursor(Qt.PointingHandCursor)
        self.chk_hide_taskbar.setToolTip("Check to hide application icon from Windows Taskbar")
        self.chk_hide_taskbar.setStyleSheet("""
            QCheckBox {
                color: #94A3B8;
                font-size: 10px;
                font-weight: 600;
                spacing: 4px;
                padding: 2px 4px;
            }
            QCheckBox:hover {
                color: #F1F5F9;
            }
            QCheckBox::indicator {
                width: 12px;
                height: 12px;
                border-radius: 3px;
                border: 1px solid rgba(255, 255, 255, 0.25);
                background: rgba(255, 255, 255, 0.08);
            }
            QCheckBox::indicator:hover {
                border-color: #10B981;
            }
            QCheckBox::indicator:checked {
                background-color: #10B981;
                border-color: #10B981;
            }
        """)
        self.chk_hide_taskbar.toggled.connect(self.toggle_hide_taskbar)
        self.header_layout.addWidget(self.chk_hide_taskbar)

        main_layout.addLayout(self.header_layout)

        # --- UNDERSTANDING WIDGET (Stream 1a & 1b) ---
        self.understanding_widget = UnderstandingWidget(self)
        main_layout.addWidget(self.understanding_widget, 1)

        # --- SMART REPLY WIDGET (Stream 2a & 2b) ---
        self.smart_reply_widget = SmartReplyWidget(self)
        main_layout.addWidget(self.smart_reply_widget, 1)


    def connect_signals(self):
        """Connects signals to widget update methods."""
        self.signal_stream1a.connect(self.understanding_widget.update_stream1a)
        self.signal_stream1b.connect(self.understanding_widget.update_stream1b)
        self.signal_stream1c.connect(self.understanding_widget.update_stream1c)
        self.signal_stream2a.connect(self.smart_reply_widget.update_stream2a)
        self.signal_stream2b.connect(self.smart_reply_widget.update_stream2b)
        self.signal_audio_activity.connect(self.on_audio_activity_changed)
        self.signal_partial_speech.connect(self.understanding_widget.update_partial_speech)



    def on_audio_activity_changed(self, is_capturing: bool, volume: float):
        """Updates top bar visual indicator when sound is actively caught."""
        if is_capturing:
            # Active audio caught (Bright Cyan Wave Indicator)
            vol_bars = " 🔊 Listening..." if volume > 500 else " 🎙️ Audio Catching"
            self.lbl_audio_wave.setText(vol_bars)
            self.lbl_audio_wave.setStyleSheet("""
                color: #38BDF8;
                font-size: 10px;
                font-weight: 700;
                background: rgba(56, 189, 248, 0.18);
                border: 1px solid rgba(56, 189, 248, 0.35);
                padding: 2px 6px;
                border-radius: 4px;
            """)
        else:
            # Idle / Quiet
            self.lbl_audio_wave.setText("🎙️ Ready")
            self.lbl_audio_wave.setStyleSheet("""
                color: #94A3B8;
                font-size: 10px;
                font-weight: 600;
                background: rgba(255, 255, 255, 0.05);
                border: none;
                padding: 2px 6px;
                border-radius: 4px;
            """)


    def toggle_lock_position(self, checked: bool):
        self.is_locked = checked
        if checked:
            self.btn_lock.setText("🔒")
        else:
            self.btn_lock.setText("🔓")

    def change_opacity(self, value: int):
        self.setWindowOpacity(value / 100.0)

    def change_text_opacity(self, value: int):
        """Adjusts opacity of text across all streams (Stream 1a, 1b, 1c, 2a, 2b)."""
        opacity = value / 100.0
        if hasattr(self, 'understanding_widget'):
            self.understanding_widget.update_text_opacity(opacity)
        if hasattr(self, 'smart_reply_widget'):
            self.smart_reply_widget.update_text_opacity(opacity)

    def toggle_hide_taskbar(self, hide: bool):
        """Toggles hiding/showing app icon on Windows Taskbar."""
        pos = self.pos()
        size = self.size()
        if hide:
            self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.resize(size)
        self.move(pos)
        self.show()

    # Window Dragging & Resizing Logic
    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = float(self.width())
        h = float(self.height())
        scale = max(0.9, min(1.8, (w / 480.0 + h / 360.0) / 2.0))
        
        if hasattr(self, 'understanding_widget'):
            self.understanding_widget.update_font_scale(scale)
        if hasattr(self, 'smart_reply_widget'):
            self.smart_reply_widget.update_font_scale(scale)
        self.save_window_state()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.is_locked:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self.is_locked:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.save_window_state()

    def closeEvent(self, event):
        self.save_window_state()
        super().closeEvent(event)




