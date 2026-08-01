"""
Always-On-Top Glassmorphic Floating Overlay Window
Integrates a fixed-zone glanceable dashboard for all result streams.
"""
import ctypes
import ctypes.wintypes
import json
import math
import os

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QGraphicsDropShadowEffect, QApplication, QCheckBox
)

from PySide6.QtCore import Qt, QPoint, QRect, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap

from config import Config
from gui.components.glanceable_dashboard import GlanceableDashboard
from utils.logger import logger

class OverlayWindow(QMainWindow):
    _WM_NCHITTEST = 0x0084
    _HTLEFT = 10
    _HTRIGHT = 11
    _HTTOP = 12
    _HTTOPLEFT = 13
    _HTTOPRIGHT = 14
    _HTBOTTOM = 15
    _HTBOTTOMLEFT = 16
    _HTBOTTOMRIGHT = 17
    _RESIZE_BORDER = 8

    # Signals for thread-safe UI updates across all streams
    signal_stream1a = Signal(int, str, str)   # utterance_id, en_text, vi_trans
    signal_contextual_english = Signal(int, str)  # id, rolling English context
    signal_stream1a_context = Signal(int, str, str)  # id, combined_en, contextual_vi
    signal_stream1b = Signal(int, str)        # utterance_id, explanation_text
    signal_stream1c = Signal(str)        # live word-by-word streaming text
    signal_stream2a = Signal(int, str)        # utterance_id, keywords_text
    signal_stream2b = Signal(
        int, str, str, str, str, bool
    )  # id, quick_en, quick_vi, full_en, full_vi, should_reply
    signal_audio_activity = Signal(bool, float)  # is_capturing, volume_energy
    signal_partial_speech = Signal(str)  # live word-by-word streaming text
    signal_recording_toggled = Signal(bool)
    signal_replay_requested = Signal()
    signal_export_requested = Signal()


    def __init__(self):
        super().__init__()
        self.drag_position = QPoint()
        self.is_locked = False
        self._geometry_verified_after_show = False
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
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(640, 500)
        
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
                screens = QApplication.screens()
                if not screens:
                    return False

                requested = QRect(
                    int(state.get("x", 100)),
                    int(state.get("y", 100)),
                    int(state.get("width", Config.WINDOW_WIDTH)),
                    int(state.get("height", Config.WINDOW_HEIGHT)),
                )
                target_screen = max(
                    screens,
                    key=lambda screen: self._intersection_area(
                        requested, screen.availableGeometry()
                    ),
                )
                if self._intersection_area(
                    requested, target_screen.availableGeometry()
                ) == 0:
                    target_screen = QApplication.primaryScreen() or target_screen

                bounded = self._bounded_geometry(
                    state, target_screen.availableGeometry()
                )
                self.resize(bounded.size())
                self.move(bounded.topLeft())
                state.update(
                    {
                        "x": bounded.x(),
                        "y": bounded.y(),
                        "width": bounded.width(),
                        "height": bounded.height(),
                    }
                )
                with open(self.state_file, "w", encoding="utf-8") as state_file:
                    json.dump(state, state_file)
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _intersection_area(first: QRect, second: QRect) -> int:
        intersection = first.intersected(second)
        return max(0, intersection.width()) * max(0, intersection.height())

    @staticmethod
    def _bounded_geometry(state: dict, available: QRect) -> QRect:
        """Keep restored geometry visible after monitor or resolution changes."""
        width = max(
            640,
            min(int(state.get("width", Config.WINDOW_WIDTH)), available.width()),
        )
        height = max(
            500,
            min(int(state.get("height", Config.WINDOW_HEIGHT)), available.height()),
        )
        x = max(
            available.left(),
            min(int(state.get("x", available.left())), available.right() - width + 1),
        )
        y = max(
            available.top(),
            min(int(state.get("y", available.top())), available.bottom() - height + 1),
        )
        return QRect(x, y, width, height)

    def ensure_visible_on_screen(self):
        """Revalidate native geometry after the first show event."""
        screens = QApplication.screens()
        if not screens:
            return
        current = self.frameGeometry()
        target_screen = max(
            screens,
            key=lambda screen: self._intersection_area(
                current, screen.availableGeometry()
            ),
        )
        if self._intersection_area(current, target_screen.availableGeometry()) == 0:
            target_screen = QApplication.primaryScreen() or target_screen
        bounded = self._bounded_geometry(
            {
                "x": current.x(),
                "y": current.y(),
                "width": self.width(),
                "height": self.height(),
            },
            target_screen.availableGeometry(),
        )
        self.resize(bounded.size())
        self.move(bounded.topLeft())
        self.save_window_state()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._geometry_verified_after_show:
            self._geometry_verified_after_show = True
            QTimer.singleShot(0, self.ensure_visible_on_screen)


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
        self.lbl_audio_wave = QLabel("🎙 Ready", self.status_title_box)
        self.lbl_audio_wave.setFixedSize(80, 20)
        self.lbl_audio_wave.setAlignment(Qt.AlignCenter)
        self.lbl_audio_wave.setStyleSheet("""
            color: #94A3B8;
            font-size: 10px;
            font-weight: 600;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid transparent;
            border-radius: 4px;
        """)
        st_layout.addWidget(self.lbl_audio_wave)
        self.header_layout.addWidget(self.status_title_box)
        self.header_layout.addStretch()

        # Session tools live in the header so the fixed reading zones never move.
        session_button_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #CBD5E1;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                font-size: 9px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: rgba(56, 189, 248, 0.20); }
            QPushButton:checked {
                background-color: rgba(239, 68, 68, 0.28);
                color: #FCA5A5;
                border-color: rgba(239, 68, 68, 0.65);
            }
            QPushButton:disabled { color: #475569; background-color: transparent; }
        """
        self.btn_record = QPushButton("● REC", self)
        self.btn_record.setObjectName("SessionRecordButton")
        self.btn_record.setCheckable(True)
        self.btn_record.setFixedSize(46, 26)
        self.btn_record.setCursor(Qt.PointingHandCursor)
        self.btn_record.setToolTip("Start / stop recording system audio")
        self.btn_record.setAccessibleName("Record system audio")
        self.btn_record.setStyleSheet(session_button_style)
        self.btn_record.toggled.connect(self.signal_recording_toggled.emit)
        self.header_layout.addWidget(self.btn_record)

        self.btn_replay = QPushButton("▶", self)
        self.btn_replay.setObjectName("SessionReplayButton")
        self.btn_replay.setFixedSize(26, 26)
        self.btn_replay.setCursor(Qt.PointingHandCursor)
        self.btn_replay.setToolTip("Replay the latest recording")
        self.btn_replay.setAccessibleName("Replay latest recording")
        self.btn_replay.setStyleSheet(session_button_style)
        self.btn_replay.setEnabled(False)
        self.btn_replay.clicked.connect(self.signal_replay_requested.emit)
        self.header_layout.addWidget(self.btn_replay)

        self.btn_export = QPushButton("TXT", self)
        self.btn_export.setObjectName("SessionExportButton")
        self.btn_export.setFixedSize(32, 26)
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setToolTip("Export the complete session to a text file")
        self.btn_export.setAccessibleName("Export session as text")
        self.btn_export.setStyleSheet(session_button_style)
        self.btn_export.clicked.connect(self.signal_export_requested.emit)
        self.header_layout.addWidget(self.btn_export)

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

        # Spacer before window controls
        self.header_layout.addSpacing(10)

        # Minimize Button
        self.btn_min = QPushButton("─", self)
        self.btn_min.setFixedSize(24, 24)
        self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.setToolTip("Minimize")
        self.btn_min.setStyleSheet(self._window_btn_style())
        self.btn_min.clicked.connect(self.showMinimized)
        self.header_layout.addWidget(self.btn_min)

        # Maximize/Restore Button
        self.btn_max = QPushButton("◻", self)
        self.btn_max.setFixedSize(24, 24)
        self.btn_max.setCursor(Qt.PointingHandCursor)
        self.btn_max.setToolTip("Maximize")
        self.btn_max.setStyleSheet(self._window_btn_style())
        self.btn_max.clicked.connect(self.toggle_maximize)
        self.header_layout.addWidget(self.btn_max)

        # Close Button
        self.btn_close = QPushButton("✕", self)
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip("Close App")
        self.btn_close.setStyleSheet(self._window_btn_style(hover_color="#EF4444"))
        self.btn_close.clicked.connect(self.close)
        self.header_layout.addWidget(self.btn_close)

        main_layout.addLayout(self.header_layout)

        # Stable zones: live; translation+context/contextual VI; keywords/reply.
        self.dashboard = GlanceableDashboard(self)
        main_layout.addWidget(self.dashboard, 1)


    def connect_signals(self):
        """Connects signals to widget update methods."""
        self.signal_stream1a.connect(self.dashboard.update_stream1a)
        self.signal_contextual_english.connect(
            self.dashboard.update_contextual_english
        )
        self.signal_stream1a_context.connect(
            self.dashboard.update_contextual_translation
        )
        self.signal_stream1b.connect(self.dashboard.update_stream1b)
        self.signal_stream1c.connect(self.dashboard.update_stream1c)
        self.signal_stream2a.connect(self.dashboard.update_stream2a)
        self.signal_stream2b.connect(self.dashboard.update_stream2b)
        self.signal_audio_activity.connect(self.on_audio_activity_changed)
        self.signal_partial_speech.connect(self.dashboard.update_partial_speech)



    def on_audio_activity_changed(self, is_capturing: bool, volume: float):
        """Updates top bar visual indicator when sound is actively caught."""
        if is_capturing:
            # Active audio caught (Bright Cyan Wave Indicator)
            vol_bars = "🔊 Listening" if volume > 500 else "🎙 Catching"
            self.lbl_audio_wave.setText(vol_bars)
            self.lbl_audio_wave.setStyleSheet("""
                color: #38BDF8;
                font-size: 10px;
                font-weight: 700;
                background: rgba(56, 189, 248, 0.18);
                border: 1px solid rgba(56, 189, 248, 0.35);
                border-radius: 4px;
            """)

        else:
            # Idle / Quiet
            self.lbl_audio_wave.setText("🎙 Ready")
            self.lbl_audio_wave.setStyleSheet("""
                color: #94A3B8;
                font-size: 10px;
                font-weight: 600;
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid transparent;
                border-radius: 4px;
            """)

    def set_recording_state(self, active: bool, recording_path: str = ""):
        """Synchronize the header controls with recorder state."""
        self.btn_record.blockSignals(True)
        self.btn_record.setChecked(active)
        self.btn_record.blockSignals(False)
        self.btn_record.setText("■ STOP" if active else "● REC")
        self.btn_record.setToolTip(
            "Stop and save recording" if active else "Start recording system audio"
        )
        if recording_path:
            self.btn_replay.setToolTip(f"Replay latest recording\n{recording_path}")
        self.btn_replay.setEnabled(bool(recording_path) and not active)

    def set_replay_state(self, playing: bool):
        self.btn_replay.setText("■" if playing else "▶")
        self.btn_replay.setEnabled(not playing and not self.btn_record.isChecked())
        self.btn_record.setEnabled(not playing)


    def toggle_lock_position(self, checked: bool):
        self.is_locked = checked
        if checked:
            self.btn_lock.setText("🔒")
        else:
            self.btn_lock.setText("🔓")

    def change_opacity(self, value: int):
        """Adjusts the glassmorphic background opacity, keeping text fully opaque."""
        alpha = int(255 * (value / 100.0))
        opacity_multiplier = value / 100.0
        self.central_widget.setStyleSheet(f"""
            QWidget#CentralWidget {{
                background-color: rgba(15, 23, 42, {alpha});
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 12px;
            }}
        """)

        if hasattr(self, 'dashboard'):
            self.dashboard.update_window_opacity(opacity_multiplier)

    def change_text_opacity(self, value: int):
        """Adjusts opacity of text across all streams (Stream 1a, 1b, 1c, 2a, 2b)."""
        opacity = value / 100.0
        if hasattr(self, 'dashboard'):
            self.dashboard.update_text_opacity(opacity)

    def toggle_hide_taskbar(self, hide: bool):
        """Toggles hiding/showing app icon on Windows Taskbar."""
        pos = self.pos()
        size = self.size()
        if hide:
            self.setWindowFlags(
                Qt.Tool | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint
            )
        else:
            self.setWindowFlags(
                Qt.Window | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint
            )
        self.resize(size)
        self.move(pos)
        self.show()

    # Window Dragging & Resizing Logic
    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = float(self.width())
        h = float(self.height())
        # Preserve tool access without allowing the title bar to overlap at the
        # supported minimum width. The checkbox remains discoverable by tooltip.
        self.chk_hide_taskbar.setText("" if w < 760 else "Hide Taskbar")
        self.lbl_title.setVisible(w >= 850)
        scale = max(0.9, min(1.8, (w / 480.0 + h / 360.0) / 2.0))
        
        if hasattr(self, 'dashboard'):
            self.dashboard.update_font_scale(scale)
        self.save_window_state()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.is_locked:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        event.accept()

    @classmethod
    def _resize_hit_test(
        cls, x: int, y: int, width: int, height: int, border: int | None = None
    ) -> int:
        """Return the Windows edge/corner hit code for a frameless window."""
        edge = cls._RESIZE_BORDER if border is None else border
        left = x < edge
        right = x >= width - edge
        top = y < edge
        bottom = y >= height - edge

        if top and left:
            return cls._HTTOPLEFT
        if top and right:
            return cls._HTTOPRIGHT
        if bottom and left:
            return cls._HTBOTTOMLEFT
        if bottom and right:
            return cls._HTBOTTOMRIGHT
        if left:
            return cls._HTLEFT
        if right:
            return cls._HTRIGHT
        if top:
            return cls._HTTOP
        if bottom:
            return cls._HTBOTTOM
        return 0

    def nativeEvent(self, event_type, message):
        """Enable native edge/corner resizing for the frameless Windows overlay."""
        if os.name == "nt" and not self.is_locked and not self.isMaximized():
            try:
                native_message = ctypes.wintypes.MSG.from_address(int(message))
                if native_message.message == self._WM_NCHITTEST:
                    packed_position = int(native_message.lParam)
                    screen_x = ctypes.c_short(packed_position & 0xFFFF).value
                    screen_y = ctypes.c_short(
                        (packed_position >> 16) & 0xFFFF
                    ).value
                    local_position = self.mapFromGlobal(QPoint(screen_x, screen_y))
                    hit = self._resize_hit_test(
                        local_position.x(),
                        local_position.y(),
                        self.width(),
                        self.height(),
                    )
                    if hit:
                        return True, hit
            except (OSError, TypeError, ValueError):
                pass
        return super().nativeEvent(event_type, message)

    def _window_btn_style(self, hover_color: str = "#3B82F6") -> str:
        """Helper to generate stylesheet for window control buttons."""
        return f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.05);
                color: #A0AEC0;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
                color: white;
            }}
        """

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

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
