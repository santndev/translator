"""Fixed-zone, glanceable dashboard for real-time call assistance."""

from __future__ import annotations

from html import escape
from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from config import Config
from utils.helpers import apply_opacity_to_hex
from utils.helpers import copy_to_clipboard


class HistoryRegion(QFrame):
    """A bounded history view whose presentation can be pinned independently."""

    def __init__(
        self,
        title: str,
        accent: str,
        placeholder: str,
        formatter: Callable[[object, bool], str],
        parent: QWidget | None = None,
        max_history: int = 3,
        copyable: bool = False,
        footer_title: str = "",
        footer_placeholder: str = "",
        max_contextual_history: int = 8,
    ):
        super().__init__(parent)
        self.title = title
        self.accent = accent
        self.placeholder = placeholder
        self.formatter = formatter
        self.max_history = max_history
        self._items: dict[int, object] = {}
        self.is_pinned = False
        self._pending_ids: set[int] = set()
        self._visible_snapshot: list[tuple[int, object]] = []
        self._text_opacity = 1.0
        self._window_opacity = 1.0
        self._font_scale = 1.0
        self._copyable = copyable
        self.footer_title = footer_title
        self.footer_placeholder = footer_placeholder
        self.max_contextual_history = max_contextual_history
        self._contextual_items: dict[int, object] = {}
        self._visible_contextual_snapshot: list[tuple[int, object]] = []
        self.setObjectName("HistoryRegion")
        self._build_ui()
        self._render()
        self._render_contextual()

    @property
    def visible_items(self) -> list[object]:
        entries = self._visible_snapshot if self.is_pinned else self.ordered_entries
        return [item for _, item in entries]

    @property
    def history(self) -> list[object]:
        """Compatibility/read-only view of values ordered by utterance ID."""
        return [item for _, item in self.ordered_entries]

    @property
    def ordered_entries(self) -> list[tuple[int, object]]:
        return sorted(self._items.items())

    @property
    def contextual_history(self) -> list[object]:
        """Contextual translations ordered from oldest to newest."""
        return [item for _, item in self.ordered_contextual_entries]

    @property
    def ordered_contextual_entries(self) -> list[tuple[int, object]]:
        return sorted(self._contextual_items.items())

    @property
    def pending_count(self) -> int:
        return len(self._pending_ids)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(5)
        self.title_label = QLabel(self.title, self)
        self.title_label.setObjectName("RegionTitle")
        header.addWidget(self.title_label)
        header.addStretch()

        self.badge = QLabel("", self)
        self.badge.setObjectName("NewBadge")
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.hide()
        header.addWidget(self.badge)

        if self._copyable:
            self.copy_button = QPushButton("⧉", self)
            self.copy_button.setFixedSize(24, 22)
            self.copy_button.setCursor(Qt.PointingHandCursor)
            self.copy_button.setToolTip("Sao chép câu trả lời đang hiển thị")
            self.copy_button.setAccessibleName("Sao chép câu trả lời")
            self.copy_button.clicked.connect(self._copy_latest)
            header.addWidget(self.copy_button)

        self.pin_button = QPushButton("⌖", self)
        self.pin_button.setCheckable(True)
        self.pin_button.setFixedSize(24, 22)
        self.pin_button.setCursor(Qt.PointingHandCursor)
        self.pin_button.setToolTip("Ghim nội dung đang đọc; ứng dụng vẫn tiếp tục xử lý")
        self.pin_button.setAccessibleName(f"Ghim vùng {self.title}")
        self.pin_button.toggled.connect(self.set_pinned)
        header.addWidget(self.pin_button)
        layout.addLayout(header)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 5px; }"
            "QScrollBar::handle:vertical { background: rgba(255,255,255,0.22);"
            " border-radius: 2px; min-height: 18px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 1, 2, 1)
        self.content_label = QLabel(content)
        self.content_label.setTextFormat(Qt.RichText)
        self.content_label.setWordWrap(True)
        self.content_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        content_layout.addWidget(self.content_label)
        content_layout.addStretch()
        self.scroll.setWidget(content)
        layout.addWidget(self.scroll, 1)

        if self.footer_title:
            self.footer_title_label = QLabel(self.footer_title, self)
            self.footer_title_label.setObjectName("FooterTitle")
            layout.addWidget(self.footer_title_label)

            self.footer_scroll = QScrollArea(self)
            self.footer_scroll.setObjectName("FooterScroll")
            self.footer_scroll.setWidgetResizable(True)
            self.footer_scroll.setFrameShape(QFrame.NoFrame)
            self.footer_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.footer_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            # The contextual translation is the slower, higher-value reading area.
            # Give it more room without changing the dashboard's fixed zone layout.
            self.footer_scroll.setMinimumHeight(110)
            self.footer_scroll.setMaximumHeight(220)
            footer_content = QWidget()
            footer_content.setStyleSheet("background: transparent;")
            footer_layout = QVBoxLayout(footer_content)
            footer_layout.setContentsMargins(0, 0, 2, 0)
            self.footer_label = QLabel(footer_content)
            self.footer_label.setObjectName("FooterContent")
            self.footer_label.setTextFormat(Qt.RichText)
            self.footer_label.setWordWrap(True)
            self.footer_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            footer_layout.addWidget(self.footer_label)
            footer_layout.addStretch()
            self.footer_scroll.setWidget(footer_content)
            layout.addWidget(self.footer_scroll, 2)
        self._apply_style()

    def upsert(self, utterance_id: int, item: object):
        """Insert/update by ID and retain the newest utterances, not completion order."""
        self._items[utterance_id] = item
        retained = sorted(self._items)[-self.max_history :]
        self._items = {key: self._items[key] for key in retained}
        self._pending_ids.intersection_update(
            set(self._items) | set(self._contextual_items)
        )
        if self.is_pinned:
            snapshot_ids = {key for key, _ in self._visible_snapshot}
            if utterance_id in self._items and utterance_id not in snapshot_ids:
                self._pending_ids.add(utterance_id)
            self._update_badge()
            return
        self._render()

    def upsert_contextual(self, utterance_id: int, item: object):
        """Retain a bounded contextual history without moving the fast rows."""
        self._contextual_items[utterance_id] = item
        retained = sorted(self._contextual_items)[-self.max_contextual_history :]
        self._contextual_items = {
            key: self._contextual_items[key] for key in retained
        }
        self._pending_ids.intersection_update(
            set(self._items) | set(self._contextual_items)
        )
        if self.is_pinned:
            snapshot_ids = {
                key for key, _ in self._visible_contextual_snapshot
            }
            if utterance_id in self._contextual_items and utterance_id not in snapshot_ids:
                self._pending_ids.add(utterance_id)
            self._update_badge()
            return
        self._render_contextual()

    def set_pinned(self, pinned: bool):
        if pinned == self.is_pinned:
            return
        if self.pin_button.isChecked() != pinned:
            self.pin_button.blockSignals(True)
            self.pin_button.setChecked(pinned)
            self.pin_button.blockSignals(False)
        self.is_pinned = pinned
        if pinned:
            self._visible_snapshot = list(self.ordered_entries)
            self._visible_contextual_snapshot = list(
                self.ordered_contextual_entries
            )
            self.pin_button.setText("●")
            self.pin_button.setToolTip("Bỏ ghim và chuyển đến nội dung mới nhất")
            self.pin_button.setAccessibleName(f"Bỏ ghim vùng {self.title}")
        else:
            self._visible_snapshot = []
            self._visible_contextual_snapshot = []
            self._pending_ids.clear()
            self.pin_button.setText("⌖")
            self.pin_button.setToolTip("Ghim nội dung đang đọc; ứng dụng vẫn tiếp tục xử lý")
            self.pin_button.setAccessibleName(f"Ghim vùng {self.title}")
        self._update_badge()
        self._render()
        self._render_contextual()
        self._apply_style()

    def _update_badge(self):
        if self.is_pinned and self.pending_count:
            self.badge.setText(f"{self.pending_count} mới")
            self.badge.show()
        else:
            self.badge.hide()

    def _render(self):
        items = self.visible_items
        if not items:
            self.content_label.setText(
                f"<span style='color:#94A3B8'>{escape(self.placeholder)}</span>"
            )
            return
        # Use one reading order everywhere: oldest at the top, newest at bottom.
        rendered = [
            self.formatter(item, index == len(items) - 1)
            for index, item in enumerate(items)
        ]
        self.content_label.setText(
            "<div style='line-height:1.25'>" + "<br><br>".join(rendered) + "</div>"
        )
        QTimer.singleShot(0, self._scroll_main_to_bottom)

    def _render_contextual(self):
        if not self.footer_title:
            return
        contextual_entries = (
            self._visible_contextual_snapshot
            if self.is_pinned
            else self.ordered_contextual_entries
        )
        if not contextual_entries:
            self.footer_label.setText(
                f"<span style='color:#64748B'>{escape(self.footer_placeholder)}</span>"
            )
            return
        font_size = max(13, min(19, round(14 * self._font_scale)))
        rendered = []
        newest_english = ""
        for index, (_, item) in enumerate(contextual_entries):
            english, vietnamese = item
            is_newest = index == len(contextual_entries) - 1
            if is_newest:
                newest_english = english
            alpha = 1.0 if is_newest else 0.58
            vi_color = apply_opacity_to_hex(
                "#FDE68A", self._text_opacity * alpha
            )
            rendered.append(
                f"<span style='color:{vi_color};font-size:{font_size}px;"
                f"font-weight:{650 if is_newest else 450};line-height:1.35'>"
                f"{escape(vietnamese)}</span>"
            )
        self.footer_label.setText(
            "<div>" + "<br><br>".join(rendered) + "</div>"
        )
        self.footer_label.setToolTip(newest_english)
        QTimer.singleShot(0, self._scroll_footer_to_bottom)

    def _scroll_main_to_bottom(self):
        try:
            scroll_bar = self.scroll.verticalScrollBar()
            scroll_bar.setValue(scroll_bar.maximum())
        except RuntimeError:
            # A queued UI callback may run after a short-lived test/widget closes.
            pass

    def _scroll_footer_to_bottom(self):
        try:
            scroll_bar = self.footer_scroll.verticalScrollBar()
            scroll_bar.setValue(scroll_bar.maximum())
        except RuntimeError:
            pass

    def clear(self):
        self._items.clear()
        self._contextual_items.clear()
        self._visible_snapshot = []
        self._visible_contextual_snapshot = []
        self._pending_ids.clear()
        self._update_badge()
        self._render()
        self._render_contextual()

    def _copy_latest(self):
        items = self.visible_items
        if not items:
            return
        item = items[-1]
        text = item[0] if isinstance(item, tuple) else str(item)
        copy_to_clipboard(text)

    def update_text_opacity(self, opacity: float):
        self._text_opacity = opacity
        self._render()
        self._render_contextual()
        self._apply_style()

    def update_window_opacity(self, opacity: float):
        self._window_opacity = opacity
        self._apply_style()

    def update_font_scale(self, scale: float):
        self._font_scale = scale
        self.content_label.setStyleSheet(
            f"font-size: {max(11, min(18, round(12 * scale)))}px;"
        )
        self._render_contextual()

    def _apply_style(self):
        accent = apply_opacity_to_hex(self.accent, self._text_opacity)
        bg_alpha = max(5, round(18 * self._window_opacity))
        border_alpha = max(16, round(55 * self._window_opacity))
        self.setStyleSheet(
            f"""
            QFrame#HistoryRegion {{
                background-color: rgba(255,255,255,{bg_alpha});
                border: 1px solid rgba(255,255,255,{border_alpha});
                border-radius: 8px;
            }}
            QLabel#RegionTitle {{
                color: {accent}; font-size: 9px; font-weight: 700;
                letter-spacing: 0.6px; border: none; background: transparent;
            }}
            QLabel#NewBadge {{
                color: #FDE68A; background: rgba(245,158,11,0.18);
                border: 1px solid rgba(245,158,11,0.35); border-radius: 7px;
                padding: 1px 5px; font-size: 9px; font-weight: 700;
            }}
            QLabel#FooterTitle {{
                color: #FDE68A; font-size: 10px; font-weight: 700;
                border: none; border-top: 1px solid rgba(255,255,255,0.10);
                padding-top: 5px; background: transparent;
            }}
            QLabel#FooterContent {{
                border: none; background: transparent;
            }}
            QScrollArea#FooterScroll {{
                border: none; background: transparent;
            }}
            QPushButton {{
                color: #CBD5E1; background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.10); border-radius: 4px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.14); color: white; }}
            QPushButton:checked {{
                color: #FDE68A; background: rgba(245,158,11,0.18);
                border-color: rgba(245,158,11,0.45);
            }}
            """
        )


class LiveEnglishRegion(QFrame):
    """Live transcript beside its slower, contextual English reading view."""

    def __init__(
        self,
        parent: QWidget | None = None,
        max_history: int = 20,
        max_chars: int = 3000,
    ):
        super().__init__(parent)
        self.max_history = max_history
        self.max_chars = max_chars
        self._final_items: dict[int, str] = {}
        self._contextual_item: tuple[int, str] | None = None
        self.partial = ""
        self._text_opacity = 1.0
        self.setObjectName("LiveEnglishRegion")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self.columns_layout = QHBoxLayout()
        self.columns_layout.setContentsMargins(0, 0, 0, 0)
        self.columns_layout.setSpacing(8)

        self.live_panel = QWidget(self)
        live_layout = QVBoxLayout(self.live_panel)
        live_layout.setContentsMargins(0, 0, 0, 0)
        live_layout.setSpacing(4)
        self.title_label = QLabel("LIVE ENGLISH", self)
        self.title_label.setObjectName("LiveTitle")
        live_layout.addWidget(self.title_label)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 2, 0)
        self.content_label = QLabel(scroll_content)
        self.content_label.setTextFormat(Qt.RichText)
        self.content_label.setWordWrap(True)
        self.content_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll_layout.addWidget(self.content_label)
        scroll_layout.addStretch()
        self.scroll.setWidget(scroll_content)
        live_layout.addWidget(self.scroll, 1)

        self.column_divider = QFrame(self)
        self.column_divider.setObjectName("LiveColumnDivider")
        self.column_divider.setFrameShape(QFrame.VLine)

        self.context_panel = QWidget(self)
        context_layout = QVBoxLayout(self.context_panel)
        context_layout.setContentsMargins(0, 0, 0, 0)
        context_layout.setSpacing(4)
        self.context_title_label = QLabel("CONTEXT ENGLISH", self)
        self.context_title_label.setObjectName("ContextEnglishTitle")
        self.context_title_label.setToolTip(
            "Tiếng Anh gần đây đã được gom lại theo ngữ cảnh hội thoại"
        )
        context_layout.addWidget(self.context_title_label)

        self.context_scroll = QScrollArea(self)
        self.context_scroll.setWidgetResizable(True)
        self.context_scroll.setFrameShape(QFrame.NoFrame)
        self.context_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.context_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        context_content = QWidget()
        context_content.setStyleSheet("background: transparent;")
        context_content_layout = QVBoxLayout(context_content)
        context_content_layout.setContentsMargins(0, 0, 2, 0)
        self.context_label = QLabel(context_content)
        self.context_label.setTextFormat(Qt.RichText)
        self.context_label.setWordWrap(True)
        self.context_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        context_content_layout.addWidget(self.context_label)
        context_content_layout.addStretch()
        self.context_scroll.setWidget(context_content)
        context_layout.addWidget(self.context_scroll, 1)

        self.columns_layout.addWidget(self.live_panel, 1)
        self.columns_layout.addWidget(self.column_divider)
        self.columns_layout.addWidget(self.context_panel, 1)
        layout.addLayout(self.columns_layout, 1)
        self._apply_style()
        self._render()
        self._render_contextual()

    @property
    def history(self) -> list[str]:
        return [text for _, text in sorted(self._final_items.items())]

    def update_live(self, text: str):
        text = text.strip()
        if text:
            self.partial = text
        else:
            self.partial = ""
        self._render()

    def update_final(self, utterance_id: int, text: str):
        normalized = text.strip()
        if not normalized:
            return
        self._final_items[utterance_id] = normalized
        retained_ids = sorted(self._final_items)[-self.max_history :]
        self._final_items = {
            key: self._final_items[key] for key in retained_ids
        }
        while (
            len(self._final_items) > 1
            and sum(len(value) for value in self._final_items.values())
            > self.max_chars
        ):
            del self._final_items[min(self._final_items)]
        self._render()

    @property
    def contextual_english(self) -> str:
        return self._contextual_item[1] if self._contextual_item else ""

    def update_contextual(self, utterance_id: int, text: str):
        """Replace the contextual view while rejecting stale async results."""
        normalized = text.strip()
        if not normalized:
            return
        if self._contextual_item and utterance_id < self._contextual_item[0]:
            return
        self._contextual_item = (utterance_id, normalized)
        self._render_contextual()

    def update_partial(self, text: str):
        if text.strip():
            self.partial = text.strip()
            self._render()

    def _render(self):
        current_color = apply_opacity_to_hex("#E0F2FE", self._text_opacity)
        old_color = apply_opacity_to_hex("#94A3B8", self._text_opacity * 0.72)
        parts = []
        history = self.history
        for index, text in enumerate(history):
            is_latest_final = index == len(history) - 1 and not self.partial
            color = current_color if is_latest_final else old_color
            weight = 650 if is_latest_final else 450
            parts.append(
                f"<span style='color:{color};font-weight:{weight}'>"
                f"{escape(text)}</span>"
            )
        if self.partial:
            parts.append(
                f"<span style='color:{current_color};font-weight:650'>"
                f"🎙 {escape(self.partial)} …</span>"
            )
        elif not history:
            parts.append(f"<span style='color:{old_color}'>Đang chờ giọng nói…</span>")
        self.content_label.setText("<br><br>".join(parts))
        # LIVE has a stable focus anchor at the bottom. Speech must remain visible
        # even if the user briefly inspected older text; other regions provide pin.
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        try:
            scroll_bar = self.scroll.verticalScrollBar()
            scroll_bar.setValue(scroll_bar.maximum())
        except RuntimeError:
            # A queued UI callback may run after a short-lived test/widget closes.
            pass

    def _render_contextual(self):
        current_color = apply_opacity_to_hex("#BAE6FD", self._text_opacity)
        if not self._contextual_item:
            placeholder_color = apply_opacity_to_hex(
                "#94A3B8", self._text_opacity * 0.72
            )
            self.context_label.setText(
                f"<span style='color:{placeholder_color}'>"
                "Đang tích lũy ngữ cảnh…</span>"
            )
            return
        self.context_label.setText(
            f"<span style='color:{current_color};font-weight:550;line-height:1.3'>"
            f"{escape(self._contextual_item[1])}</span>"
        )
        QTimer.singleShot(0, self._scroll_context_to_bottom)

    def _scroll_context_to_bottom(self):
        try:
            scroll_bar = self.context_scroll.verticalScrollBar()
            scroll_bar.setValue(scroll_bar.maximum())
        except RuntimeError:
            pass

    def clear(self):
        self._final_items.clear()
        self._contextual_item = None
        self.partial = ""
        self._render()
        self._render_contextual()

    def update_text_opacity(self, opacity: float):
        self._text_opacity = opacity
        self._render()
        self._render_contextual()

    def update_window_opacity(self, opacity: float):
        alpha = max(8, round(28 * opacity))
        self.setStyleSheet(
            f"QFrame#LiveEnglishRegion {{ background: rgba(56,189,248,{alpha});"
            " border: 1px solid rgba(56,189,248,0.25); border-radius: 8px; }"
            "QLabel { border:none; background:transparent; }"
            "QScrollArea { border:none; background:transparent; }"
            "QLabel#LiveTitle { color:#38BDF8; font-size:9px; font-weight:700; }"
            "QLabel#ContextEnglishTitle { color:#7DD3FC; font-size:9px; font-weight:700; }"
            "QFrame#LiveColumnDivider { color:rgba(255,255,255,0.14); }"
        )

    def update_font_scale(self, scale: float):
        self.content_label.setStyleSheet(
            f"font-size: {max(12, min(20, round(13 * scale)))}px;"
        )
        self.context_label.setStyleSheet(
            f"font-size: {max(12, min(20, round(13 * scale)))}px;"
        )

    def _apply_style(self):
        self.update_window_opacity(1.0)


class GlanceableDashboard(QWidget):
    """Fixed visual zones whose processing results remain independent."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._text_opacity = 1.0
        self.live_region = LiveEnglishRegion(self)
        self.translation_region = HistoryRegion(
            "DỊCH TIẾNG VIỆT", "#F6AD55", "Đang chờ bản dịch…",
            self._format_translation, self, max_history=2,
        )
        self.contextual_translation_region = HistoryRegion(
            "DỊCH THEO NGỮ CẢNH · HỘI THOẠI GẦN ĐÂY",
            "#FDE68A",
            "Đang tích lũy ngữ cảnh hội thoại…",
            self._format_contextual_translation,
            self,
            max_history=8,
        )
        self.reply_region = HistoryRegion(
            "RECOMMENDED REPLY", "#68D391", "Đang chờ gợi ý trả lời…",
            self._format_reply, self, copyable=True,
        )
        self.keywords_region = HistoryRegion(
            "KEYWORDS", "#6EE7B7", "Đang chờ từ khóa…",
            self._format_keywords, self,
        )
        self.context_region = HistoryRegion(
            "NGỮ CẢNH / Ý ĐỊNH", "#E9D8A6", "Đang phân tích ngữ cảnh…",
            self._format_context, self,
        )

        # This column represents the second requested swap: context/intent takes
        # the former contextual-translation subarea below the fast translation.
        self.translation_context_column = QWidget(self)
        translation_context_layout = QVBoxLayout(
            self.translation_context_column
        )
        translation_context_layout.setContentsMargins(0, 0, 0, 0)
        translation_context_layout.setSpacing(8)
        translation_context_layout.addWidget(self.translation_region, 1)
        translation_context_layout.addWidget(self.context_region, 2)
        self.translation_context_layout = translation_context_layout

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)
        layout.addWidget(self.live_region, 0, 0, 1, 2)
        layout.addWidget(self.translation_context_column, 1, 0)
        layout.addWidget(self.contextual_translation_region, 1, 1)
        layout.addWidget(self.keywords_region, 2, 0)
        layout.addWidget(self.reply_region, 2, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(0, 2)
        layout.setRowStretch(1, 3)
        layout.setRowStretch(2, 2)

    @property
    def regions(self):
        return (
            self.translation_region,
            self.contextual_translation_region,
            self.reply_region,
            self.keywords_region,
            self.context_region,
        )

    def update_stream1c(self, text: str):
        self.live_region.update_live(text)

    def update_partial_speech(self, text: str):
        self.live_region.update_partial(text)

    def update_stream1a(
        self, utterance_id: int, english_text: str, vietnamese_trans: str
    ):
        self.live_region.update_final(utterance_id, english_text)
        item = (english_text.strip(), vietnamese_trans.strip())
        self.translation_region.upsert(utterance_id, item)

    def update_stream1b(self, utterance_id: int, explanation_text: str):
        if explanation_text.strip():
            self.context_region.upsert(utterance_id, explanation_text.strip())

    def update_contextual_english(
        self, utterance_id: int, combined_english: str
    ):
        self.live_region.update_contextual(utterance_id, combined_english)

    def update_contextual_translation(
        self, utterance_id: int, combined_english: str, vietnamese_trans: str
    ):
        self.live_region.update_contextual(utterance_id, combined_english)
        if vietnamese_trans.strip():
            self.contextual_translation_region.upsert(
                utterance_id,
                (combined_english.strip(), vietnamese_trans.strip()),
            )

    def update_stream2a(self, utterance_id: int, keywords_text: str):
        if keywords_text.strip():
            self.keywords_region.upsert(utterance_id, keywords_text.strip())

    def update_stream2b(
        self,
        utterance_id: int,
        quick_en: str,
        quick_vi: str,
        response_en: str,
        response_vi: str,
        should_reply: bool,
    ):
        self.reply_region.upsert(
            utterance_id,
            (
                quick_en.strip(),
                quick_vi.strip(),
                response_en.strip(),
                response_vi.strip(),
                should_reply,
            ),
        )

    def update_font_scale(self, scale: float):
        self.live_region.update_font_scale(scale)
        for region in self.regions:
            region.update_font_scale(scale)

    def update_text_opacity(self, opacity: float):
        self._text_opacity = opacity
        self.live_region.update_text_opacity(opacity)
        for region in self.regions:
            region.update_text_opacity(opacity)
        self._render_all()

    def update_window_opacity(self, opacity: float):
        self.live_region.update_window_opacity(opacity)
        for region in self.regions:
            region.update_window_opacity(opacity)

    def clear_for_replay(self):
        """Reset visible streams so replay can rebuild them chronologically."""
        self.live_region.clear()
        for region in self.regions:
            region.set_pinned(False)
            region.clear()

    def _render_all(self):
        self.translation_region._render()
        self.contextual_translation_region._render()
        self.reply_region._render()
        self.keywords_region._render()
        self.context_region._render()

    def _format_translation(self, item: object, newest: bool) -> str:
        _, vietnamese = item
        alpha = 1.0 if newest else 0.58
        vi_color = apply_opacity_to_hex(Config.COLOR_VIET_SUB, self._text_opacity * alpha)
        return (
            f"<span style='color:{vi_color};font-weight:{650 if newest else 450}'>"
            f"{escape(vietnamese)}</span>"
        )

    def _format_contextual_translation(
        self, item: object, newest: bool
    ) -> str:
        _, vietnamese = item
        alpha = 1.0 if newest else 0.58
        vi_color = apply_opacity_to_hex("#FDE68A", self._text_opacity * alpha)
        return (
            f"<span style='color:{vi_color};font-size:14px;"
            f"font-weight:{650 if newest else 450};line-height:1.35'>"
            f"{escape(vietnamese)}</span>"
        )

    def _format_reply(self, item: object, newest: bool) -> str:
        quick_en, quick_vi, english, vietnamese, should_reply = item
        alpha = 1.0 if newest else 0.55
        en_color = apply_opacity_to_hex(Config.COLOR_REPLY_EN, self._text_opacity * alpha)
        vi_color = apply_opacity_to_hex(Config.COLOR_REPLY_VI, self._text_opacity * alpha)
        if not should_reply:
            return (
                f"<span style='color:{vi_color};font-size:9px;font-weight:700'>"
                "KHÔNG CẦN PHẢN HỒI</span><br>"
                f"<span style='color:{vi_color};font-style:italic'>"
                f"{escape(quick_vi)}</span>"
            )
        quick_label = (
            f"<span style='color:{en_color};font-size:9px;font-weight:700'>"
            "TRẢ LỜI NHANH</span><br>"
        )
        quick = (
            f"<span style='color:{en_color};font-weight:700'>"
            f"{escape(quick_en)}</span><br>"
            f"<span style='color:{vi_color};font-style:italic'>"
            f"{escape(quick_vi)}</span>"
        )
        if not newest:
            return quick
        return (
            quick_label
            + quick
            + f"<br><br><span style='color:{vi_color};font-size:9px;"
            "font-weight:700'>TRẢ LỜI ĐẦY ĐỦ</span><br>"
            f"<span style='color:{en_color};font-weight:{700 if newest else 500}'>"
            f"{escape(english)}</span><br>"
            f"<span style='color:{vi_color};font-style:italic'>{escape(vietnamese)}</span>"
        )

    def _format_keywords(self, item: object, newest: bool) -> str:
        alpha = 1.0 if newest else 0.52
        color = apply_opacity_to_hex(Config.COLOR_KEYWORDS, self._text_opacity * alpha)
        keywords = [
            escape(value.strip())
            for value in str(item).replace(";", ",").replace("/", ",").split(",")
            if value.strip()
        ]
        return (
            f"<span style='color:{color};font-weight:{650 if newest else 450}'>"
            + "  ·  ".join(keywords)
            + "</span>"
        )

    def _format_context(self, item: object, newest: bool) -> str:
        alpha = 1.0 if newest else 0.52
        color = apply_opacity_to_hex(Config.COLOR_EXPLANATION, self._text_opacity * alpha)
        return (
            f"<span style='color:{color};font-style:italic;"
            f"font-weight:{600 if newest else 400}'>{escape(str(item))}</span>"
        )
