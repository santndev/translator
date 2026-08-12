"""Standalone assertions for the Qt dashboard (invoked by pytest subprocess)."""

import os
import tempfile

from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QTest

from gui.components.glanceable_dashboard import (
    GlanceableDashboard,
    conversation_display_text,
)
from gui.overlay_window import OverlayWindow
from config import Config


_TEST_STATE_DIRECTORY = tempfile.TemporaryDirectory()
Config.WINDOW_STATE_PATH = os.path.join(
    _TEST_STATE_DIRECTORY.name, "window_state.json"
)


def make_dashboard() -> GlanceableDashboard:
    widget = GlanceableDashboard()
    widget.resize(840, 560)
    return widget


def settle_scrolls(milliseconds: int = 220):
    """Allow the smooth follower and deferred Qt layout passes to complete."""
    QApplication.processEvents()
    QTest.qWait(milliseconds)
    QApplication.processEvents()


def assert_at_bottom(scroll_bar, label: str = ""):
    """Allow Qt's offscreen layout one transient scrollbar pixel."""
    value = scroll_bar.value()
    maximum = scroll_bar.maximum()
    assert abs(maximum - value) <= 1, label


def verify_grid_positions():
    dashboard = make_dashboard()
    grid = dashboard.layout()
    expected = {
        dashboard.live_region: (0, 0, 1, 2),
        dashboard.translation_context_column: (1, 0, 1, 1),
        dashboard.contextual_translation_region: (1, 1, 1, 1),
        dashboard.keywords_region: (2, 0, 1, 1),
        dashboard.reply_region: (2, 1, 1, 1),
    }
    for widget, position in expected.items():
        assert grid.getItemPosition(grid.indexOf(widget)) == position
    nested = dashboard.translation_context_layout
    assert nested.itemAt(0).widget() is dashboard.translation_region
    assert nested.itemAt(1).widget() is dashboard.context_region
    assert nested.stretch(0) == 1
    assert nested.stretch(1) == 1


def verify_live_stylesheet_is_well_formed():
    dashboard = make_dashboard()
    dashboard.update_window_opacity(0.5)
    stylesheet = dashboard.live_region.styleSheet()

    assert "}}" not in stylesheet
    assert "QFrame#LiveEnglishRegion {" in stylesheet
    assert "QLabel#LiveTitle {" in stylesheet


def verify_independent_bounded_history():
    dashboard = make_dashboard()
    for number in range(4):
        dashboard.update_stream2a(number, f"keyword-{number}")
        dashboard.update_stream1b(number, f"context-{number}")
        dashboard.update_stream2b(
            number,
            f"quick-{number}",
            f"nhanh-{number}",
            f"reply-{number}",
            f"dịch-{number}",
            True,
        )

    assert dashboard.keywords_region.history == ["keyword-1", "keyword-2", "keyword-3"]
    assert dashboard.context_region.history == ["context-1", "context-2", "context-3"]
    assert dashboard.reply_region.history == [
        ("quick-1", "nhanh-1", "reply-1", "dịch-1", True),
        ("quick-2", "nhanh-2", "reply-2", "dịch-2", True),
        ("quick-3", "nhanh-3", "reply-3", "dịch-3", True),
    ]


def verify_pin_buffer_badge_and_release():
    dashboard = make_dashboard()
    dashboard.update_stream2a(1, "first")
    dashboard.keywords_region.pin_button.setChecked(True)
    dashboard.update_stream2a(2, "second")
    dashboard.update_stream2a(2, "second updated")
    dashboard.update_stream2a(3, "third")
    dashboard.update_stream1b(2, "context keeps moving")

    assert dashboard.keywords_region.visible_items == ["first"]
    assert dashboard.keywords_region.history == ["first", "second updated", "third"]
    assert dashboard.keywords_region.pending_count == 2
    assert dashboard.keywords_region.badge.text() == "2 mới"
    assert not dashboard.keywords_region.badge.isHidden()
    assert dashboard.context_region.visible_items == ["context keeps moving"]

    dashboard.keywords_region.pin_button.setChecked(False)
    assert dashboard.keywords_region.visible_items == ["first", "second updated", "third"]
    assert dashboard.keywords_region.pending_count == 0
    assert dashboard.keywords_region.badge.isHidden()


def verify_translation_replaces_pending_result():
    dashboard = make_dashboard()
    english = "Can you describe the rollback plan?"
    dashboard.update_stream1a(7, english, "Đang dịch...")
    assert dashboard.translation_region.history == []
    dashboard.update_stream1a(
        7, english, "Bạn có thể mô tả kế hoạch quay lui không?"
    )
    assert dashboard.translation_region.history == [
        (english, "Bạn có thể mô tả kế hoạch quay lui không?")
    ]


def verify_out_of_order_results_follow_utterance_order():
    dashboard = make_dashboard()
    dashboard.update_stream2b(
        12, "quick twelve", "nhanh mười hai", "reply twelve", "dịch mười hai", True
    )
    dashboard.update_stream2b(
        10, "quick ten", "nhanh mười", "reply ten", "dịch mười", True
    )
    dashboard.update_stream2b(
        11, "quick eleven", "nhanh mười một", "reply eleven", "dịch mười một", True
    )
    dashboard.update_stream2b(
        9, "quick old", "nhanh cũ", "too old", "quá cũ", True
    )

    assert dashboard.reply_region.history == [
        ("quick ten", "nhanh mười", "reply ten", "dịch mười", True),
        ("quick eleven", "nhanh mười một", "reply eleven", "dịch mười một", True),
        ("quick twelve", "nhanh mười hai", "reply twelve", "dịch mười hai", True),
    ]
    assert "reply twelve" in dashboard.reply_region.content_label.text()
    assert dashboard.reply_region.content_label.text().index(
        "quick eleven"
    ) < dashboard.reply_region.content_label.text().index("quick twelve")
    assert "reply eleven" not in dashboard.reply_region.content_label.text()


def verify_live_never_freezes():
    dashboard = make_dashboard()
    dashboard.update_stream1c("first live phrase")
    dashboard.update_stream1c("")
    dashboard.update_stream1a(1, "first live phrase", "Đang dịch...")
    dashboard.update_stream1c("current live phrase")

    assert not hasattr(dashboard.live_region, "pin_button")
    assert dashboard.live_region.partial == "current live phrase"
    assert "current live phrase" in dashboard.live_region.content_label.text()
    assert "first live phrase" in dashboard.live_region.content_label.text()


def verify_live_is_rendered_oldest_to_current():
    dashboard = make_dashboard()
    dashboard.update_stream1c("first")
    dashboard.update_stream1c("")
    dashboard.update_stream1a(1, "first", "Đang dịch...")
    dashboard.update_stream1c("second")
    dashboard.update_stream1c("")
    dashboard.update_stream1a(2, "second", "Đang dịch...")
    dashboard.update_stream1c("current")

    rendered = dashboard.live_region.content_label.text()
    assert rendered.index("first") < rendered.index("second") < rendered.index("current")


def verify_live_keeps_a_long_rolling_transcript():
    dashboard = make_dashboard()
    for utterance_id in range(1, 13):
        dashboard.update_stream1a(
            utterance_id,
            f"Complete English sentence number {utterance_id}.",
            "Đang dịch...",
        )

    rendered = dashboard.live_region.content_label.text()
    assert "sentence number 1" in rendered
    assert "sentence number 12" in rendered
    assert len(dashboard.live_region.history) == 12
    assert dashboard.live_region.scroll.verticalScrollBarPolicy() == (
        Qt.ScrollBarAsNeeded
    )


def verify_live_displays_stable_speaker_badges_and_parallel_partials():
    dashboard = make_dashboard()
    dashboard.update_speaker(1, "YOU")
    dashboard.update_stream1a(1, "I will check that.", "Tôi sẽ kiểm tra.")
    dashboard.update_speaker(2, "REMOTE")
    dashboard.update_stream1a(2, "Thank you.", "Cảm ơn bạn.")
    dashboard.update_speaker_partial("REMOTE", "Could you")
    dashboard.update_speaker_partial("YOU", "Yes")

    rendered = dashboard.live_region.content_label.text()
    assert "[BẠN]" in rendered
    assert "REMOTE" not in rendered
    assert "🔊" in rendered
    assert "Could you" in rendered
    assert "Yes" in rendered
    assert "🎙" not in rendered

    dashboard.update_speaker_partial("YOU", "")
    rendered = dashboard.live_region.content_label.text()
    assert "Could you" in rendered
    assert "🎙" not in rendered


def verify_remote_labels_become_icons_in_conversation_views():
    assert conversation_display_text("TỪ XA: Ý đầu tiên.") == "🔊 Ý đầu tiên."
    assert conversation_display_text("XA: Nhãn bị sót.") == "🔊 Nhãn bị sót."
    dashboard = make_dashboard()
    dashboard.update_contextual_english(
        2, "REMOTE: First point. BẠN: Got it. REMOTE: Second point."
    )
    dashboard.update_contextual_translation(
        2,
        "REMOTE: First point. BẠN: Got it. REMOTE: Second point.",
        "TỪ XA: Ý đầu tiên.",
    )

    contextual_english = dashboard.live_region.context_label.text()
    contextual_vietnamese = (
        dashboard.contextual_translation_region.content_label.text()
    )
    assert "REMOTE" not in contextual_english
    assert contextual_english.count("🔊") == 2
    assert "TỪ XA" not in contextual_vietnamese
    assert "🔊" in contextual_vietnamese


def verify_empty_regions_do_not_show_processing_status():
    dashboard = make_dashboard()
    visible_text = " ".join(
        [dashboard.live_region.content_label.text(),
         dashboard.live_region.context_label.text()]
        + [region.content_label.text() for region in dashboard.regions]
    )
    assert "Đang" not in visible_text


def verify_live_region_is_split_into_equal_realtime_and_context_columns():
    dashboard = make_dashboard()
    dashboard.show()
    settle_scrolls()

    live = dashboard.live_region
    assert live.columns_layout.stretch(0) == 1
    assert live.columns_layout.stretch(2) == 1
    assert live.title_label.text() == "LIVE ENGLISH"
    assert live.context_title_label.text() == "CONTEXT ENGLISH"
    assert abs(live.live_panel.width() - live.context_panel.width()) <= 2
    dashboard.close()


def verify_context_english_updates_and_rejects_stale_results():
    dashboard = make_dashboard()
    dashboard.resize(640, 500)
    dashboard.show()
    old_context = "Earlier English context " + ("with more detail " * 90)
    current_context = "Current English context " + ("with updated detail " * 90)
    dashboard.update_contextual_translation(
        8,
        old_context,
        "Bản dịch mới",
    )
    settle_scrolls()
    context_bar = dashboard.live_region.context_scroll.verticalScrollBar()
    assert context_bar.maximum() > 0
    context_bar.setValue(0)
    dashboard.update_contextual_english(9, current_context)
    dashboard.update_contextual_translation(
        7,
        "This stale result must not replace the current context.",
        "Bản dịch cũ",
    )
    settle_scrolls()

    assert dashboard.live_region.contextual_english == current_context.strip()
    assert "Current English context" in dashboard.live_region.context_label.text()
    assert "stale result" not in dashboard.live_region.context_label.text()
    assert_at_bottom(context_bar)
    dashboard.close()


def verify_new_content_returns_each_region_to_its_focus_anchor():
    dashboard = make_dashboard()
    dashboard.resize(640, 500)
    dashboard.show()

    for utterance_id in range(1, 21):
        dashboard.update_stream1a(
            utterance_id,
            f"English {utterance_id} " + ("long content " * 14),
            f"Bản dịch {utterance_id} " + ("nội dung dài " * 10),
        )
        dashboard.update_stream2a(
            utterance_id,
            f"keyword-{utterance_id} " + ("description " * 18),
        )
    settle_scrolls()

    live_bar = dashboard.live_region.scroll.verticalScrollBar()
    keyword_bar = dashboard.keywords_region.scroll.verticalScrollBar()
    assert live_bar.maximum() > 0
    assert keyword_bar.maximum() > 0
    live_bar.setValue(0)
    keyword_bar.setValue(keyword_bar.maximum())

    dashboard.update_stream1c("the newest live words")
    dashboard.update_stream2a(21, "newest keyword " + ("detail " * 30))
    settle_scrolls()

    assert_at_bottom(live_bar)
    assert_at_bottom(keyword_bar)
    dashboard.close()


def verify_new_contextual_translation_returns_to_its_focus_anchor():
    dashboard = make_dashboard()
    dashboard.resize(640, 500)
    dashboard.show()
    dashboard.update_contextual_translation(
        1,
        "Long English context",
        "Bản dịch cũ " + ("với rất nhiều nội dung để đọc " * 45),
    )
    settle_scrolls()

    context_bar = (
        dashboard.contextual_translation_region.scroll.verticalScrollBar()
    )
    assert context_bar.maximum() > 0
    context_bar.setValue(context_bar.maximum())
    dashboard.update_contextual_translation(
        2,
        "New English context",
        "Bản dịch theo ngữ cảnh mới " + ("và phần giải thích " * 40),
    )
    settle_scrolls()

    assert_at_bottom(context_bar)
    dashboard.close()


def verify_all_history_regions_follow_top_to_bottom_and_scroll_to_bottom():
    dashboard = make_dashboard()
    dashboard.resize(640, 500)
    dashboard.show()
    long_text = "nội dung mới nhất " * 55
    for utterance_id in range(1, 9):
        dashboard.update_stream1a(
            utterance_id, f"English {utterance_id}", long_text
        )
        dashboard.update_contextual_translation(
            utterance_id, f"Context {utterance_id}", long_text
        )
        dashboard.update_stream1b(utterance_id, long_text)
        dashboard.update_stream2a(
            utterance_id, ", ".join([f"keyword-{utterance_id}"] * 60)
        )
        dashboard.update_stream2b(
            utterance_id,
            f"quick-{utterance_id} " + long_text,
            long_text,
            long_text,
            long_text,
            True,
        )
    # Wait through the short per-sentence pulse so the offscreen Qt layout has
    # reached its final scrollbar range before asserting the bottom anchor.
    settle_scrolls(900)

    for region in dashboard.regions:
        scroll_bar = region.scroll.verticalScrollBar()
        assert scroll_bar.maximum() > 0, region.title
        assert_at_bottom(scroll_bar, region.title)
    dashboard.close()


def verify_bottom_follow_is_smooth_and_pin_stops_it():
    dashboard = make_dashboard()
    dashboard.resize(640, 500)
    dashboard.show()
    region = dashboard.keywords_region
    for utterance_id in range(1, 5):
        dashboard.update_stream2a(
            utterance_id,
            f"keyword-{utterance_id} " + ("long detail " * 100),
        )
    settle_scrolls()

    scroll_bar = region.scroll.verticalScrollBar()
    assert scroll_bar.maximum() > 10
    scroll_bar.setValue(0)
    dashboard.update_stream2a(5, "newest " + ("more detail " * 100))
    QApplication.processEvents()

    assert 0 < scroll_bar.value() < scroll_bar.maximum()
    assert region._main_bottom_follow.is_animating
    settle_scrolls()
    assert_at_bottom(scroll_bar)

    region.set_pinned(True)
    scroll_bar.setValue(0)
    dashboard.update_stream2a(6, "pinned update " + ("detail " * 100))
    settle_scrolls()
    assert scroll_bar.value() == 0
    assert not region._main_bottom_follow.is_animating
    dashboard.close()


def verify_contextual_translation_keeps_bounded_scrollable_history():
    dashboard = make_dashboard()
    dashboard.resize(640, 500)
    dashboard.show()
    for utterance_id in range(1, 11):
        dashboard.update_contextual_translation(
            utterance_id,
            f"English context {utterance_id}",
            f"Bản dịch ngữ cảnh {utterance_id} " + ("nội dung dài " * 12),
        )
    settle_scrolls()

    region = dashboard.contextual_translation_region
    assert len(region.history) == 8
    assert region.history[0][1].startswith("Bản dịch ngữ cảnh 3")
    assert region.history[-1][1].startswith("Bản dịch ngữ cảnh 10")
    rendered = region.content_label.text()
    assert "ngữ cảnh 2 " not in rendered
    assert rendered.index("ngữ cảnh 9") < rendered.index("ngữ cảnh 10")
    assert region.scroll.verticalScrollBar().maximum() > 0
    dashboard.close()


def verify_contextual_translation_uses_fixed_third_row():
    dashboard = make_dashboard()
    dashboard.update_stream1a(1, "First phrase", "Cụm đầu")
    dashboard.update_stream1a(2, "Second phrase", "Cụm thứ hai")
    dashboard.update_stream1a(3, "Third phrase", "Cụm thứ ba")
    dashboard.update_contextual_translation(
        3,
        "First phrase Second phrase Third phrase",
        "Bản dịch kết hợp có ngữ cảnh",
    )

    assert len(dashboard.translation_region.history) == 2
    assert dashboard.translation_region.history[-1] == (
        "Third phrase",
        "Cụm thứ ba",
    )
    assert "Bản dịch kết hợp có ngữ cảnh" in (
        dashboard.contextual_translation_region.content_label.text()
    )
    assert dashboard.contextual_translation_region.history == [
        (
            "First phrase Second phrase Third phrase",
            "Bản dịch kết hợp có ngữ cảnh",
        )
    ]
    assert "font-size:14px" not in (
        dashboard.contextual_translation_region.content_label.text()
    )


def verify_each_history_region_has_independent_font_controls_after_pin():
    dashboard = make_dashboard()
    dashboard.update_font_scale(1.0)

    for region in dashboard.regions:
        pin_index = region.header_layout.indexOf(region.pin_button)
        decrease_index = region.header_layout.indexOf(
            region.font_decrease_button
        )
        increase_index = region.header_layout.indexOf(
            region.font_increase_button
        )
        assert decrease_index < increase_index < pin_index
        assert region.font_decrease_button.accessibleName().startswith(
            "Giảm cỡ chữ"
        )
        assert region.font_increase_button.accessibleName().startswith(
            "Tăng cỡ chữ"
        )

    target = dashboard.keywords_region
    untouched = dashboard.context_region
    target.font_increase_button.click()
    assert target._font_scale == 1.1
    assert untouched._font_scale == 1.0
    assert "font-size: 13px" in target.content_label.styleSheet()

    for _ in range(20):
        target.font_increase_button.click()
    assert target._font_scale == target.MAX_FONT_SCALE
    assert not target.font_increase_button.isEnabled()
    assert target.font_decrease_button.isEnabled()

    target.font_decrease_button.click()
    assert target._font_scale < target.MAX_FONT_SCALE
    assert target.font_increase_button.isEnabled()


def verify_frameless_window_resize_hit_regions():
    hit = OverlayWindow._resize_hit_test
    assert hit(0, 0, 800, 600) == OverlayWindow._HTTOPLEFT
    assert hit(799, 599, 800, 600) == OverlayWindow._HTBOTTOMRIGHT
    assert hit(0, 300, 800, 600) == OverlayWindow._HTLEFT
    assert hit(400, 0, 800, 600) == OverlayWindow._HTTOP
    assert hit(400, 300, 800, 600) == 0


def verify_interactive_controls_override_resize_edges():
    overlay = OverlayWindow()
    overlay.save_window_state = lambda: None
    overlay.resize(800, 600)
    overlay.show()
    edge_button = QPushButton("test", overlay)
    edge_button.setGeometry(792, 200, 8, 24)
    edge_button.show()
    edge_button.raise_()
    QApplication.processEvents()

    point = edge_button.mapTo(overlay, QPoint(2, 10))
    assert OverlayWindow._resize_hit_test(
        point.x(), point.y(), overlay.width(), overlay.height()
    ) == OverlayWindow._HTRIGHT
    assert overlay._is_interactive_child_at(point)

    region_button = overlay.dashboard.reply_region.font_increase_button
    region_point = region_button.mapTo(
        overlay, region_button.rect().center()
    )
    assert overlay._is_interactive_child_at(region_point)
    overlay.close()


def verify_native_hit_test_coordinates_survive_negative_monitor_origin():
    overlay = OverlayWindow()
    overlay.save_window_state = lambda: None
    overlay.resize(800, 600)
    overlay.move(392, -755)
    overlay.show()
    QApplication.processEvents()

    button = overlay.dashboard.contextual_translation_region.pin_button
    expected_client = button.mapTo(overlay, button.rect().center())
    screen_position = button.mapToGlobal(button.rect().center())
    native_client = overlay._native_client_position(
        int(overlay.winId()), screen_position
    )

    assert native_client == expected_client
    assert overlay._is_interactive_child_at(native_client)
    overlay.close()


def verify_new_content_pulses_without_changing_history_semantics():
    dashboard = make_dashboard()
    region = dashboard.translation_region
    dashboard.update_stream1a(1, "First", "Câu đầu")
    assert region._main_pulse.item_id == 1
    assert "class='new-content-pulse'" in region.content_label.text()
    assert "new-content-pulse" not in region.title_label.styleSheet()

    dashboard.update_stream1a(2, "Second", "Câu thứ hai")
    assert region._main_pulse.item_id == 2
    assert region.history == [
        ("First", "Câu đầu"),
        ("Second", "Câu thứ hai"),
    ]
    assert dashboard.live_region._final_pulse.item_id == 2
    rendered = region.content_label.text()
    first_position = rendered.index("Câu đầu")
    second_position = rendered.index("Câu thứ hai")
    pulse_position = rendered.index("class='new-content-pulse'")
    assert first_position < pulse_position < second_position

    dashboard.update_stream1b(2, "Ngữ cảnh mới")
    dashboard.update_stream2a(2, "keyword mới")
    dashboard.update_stream2b(
        2,
        "Quick reply",
        "Trả lời nhanh",
        "Full reply",
        "Trả lời đầy đủ",
        True,
    )
    dashboard.update_contextual_translation(
        2,
        "First Second",
        "Bản dịch mới có ngữ cảnh",
    )
    pulsing_labels = [
        dashboard.context_region.content_label,
        dashboard.keywords_region.content_label,
        dashboard.reply_region.content_label,
        dashboard.contextual_translation_region.content_label,
        dashboard.live_region.context_label,
    ]
    assert all(
        "class='new-content-pulse'" in label.text()
        for label in pulsing_labels
    )

    QTest.qWait(900)
    QApplication.processEvents()
    assert region._main_pulse.item_id is None
    assert "class='new-content-pulse'" not in region.content_label.text()
    assert dashboard.live_region._final_pulse.item_id is None
    assert "class='new-content-pulse'" not in (
        dashboard.live_region.content_label.text()
    )
    assert all(
        "class='new-content-pulse'" not in label.text()
        for label in pulsing_labels
    )


def verify_no_reply_recommendation_is_rendered():
    dashboard = make_dashboard()
    dashboard.update_stream2b(
        1,
        "",
        "Không cần phản hồi ngay — tiếp tục lắng nghe.",
        "",
        "",
        False,
    )

    rendered = dashboard.reply_region.content_label.text()
    assert "KHÔNG CẦN PHẢN HỒI" in rendered
    assert "tiếp tục lắng nghe" in rendered


def verify_overlay_signals_preserve_ids():
    overlay = OverlayWindow()
    overlay.signal_stream2a.emit(22, "newer")
    overlay.signal_stream2a.emit(21, "older completed later")
    overlay.signal_stream1a.emit(22, "English", "Đang dịch...")
    overlay.signal_stream1a.emit(22, "English", "Tiếng Việt")
    overlay.signal_contextual_english.emit(
        22, "Immediate rolling English context"
    )
    overlay.signal_stream1a_context.emit(
        22, "Immediate rolling English context", "Bản dịch theo ngữ cảnh"
    )
    QApplication.processEvents()

    assert overlay.dashboard.keywords_region.history == [
        "older completed later",
        "newer",
    ]
    assert overlay.dashboard.translation_region.history == [
        ("English", "Tiếng Việt")
    ]
    assert "Bản dịch theo ngữ cảnh" in (
        overlay.dashboard.contextual_translation_region.content_label.text()
    )
    assert overlay.dashboard.live_region.contextual_english == (
        "Immediate rolling English context"
    )

    overlay.signal_ai_status.emit(
        "online", "OpenAI", "OpenAI đang hoạt động"
    )
    QApplication.processEvents()
    assert overlay.lbl_ai_status.text() == "OPENAI"

    overlay.signal_ai_status.emit(
        "degraded", "Gemini", "OpenAI tạm giới hạn — đang dùng Gemini"
    )
    QApplication.processEvents()
    assert overlay.lbl_ai_status.text() == "GEMINI"
    assert "tạm giới hạn" in overlay.lbl_ai_status.toolTip()

    overlay.signal_ai_status.emit(
        "local", "Local", "AI online không sẵn sàng — đang dùng local"
    )
    QApplication.processEvents()
    assert overlay.lbl_ai_status.text() == "LOCAL"


def verify_offscreen_window_state_is_clamped():
    available = QRect(0, 0, 1920, 1080)
    restored = OverlayWindow._bounded_geometry(
        {"x": 432, "y": -855, "width": 1151, "height": 747},
        available,
    )

    assert restored.top() == 0
    assert restored.left() == 432
    assert available.contains(restored)


def verify_session_controls_have_stable_states_and_accessible_names():
    overlay = OverlayWindow()
    assert overlay.btn_record.accessibleName() == "Record system audio"
    assert overlay.btn_replay.accessibleName() == "Replay latest recording"
    assert not overlay.btn_replay.isEnabled()

    overlay.set_recording_state(True)
    assert overlay.btn_record.isChecked()
    assert "STOP" in overlay.btn_record.text()

    overlay.set_recording_state(False, "C:/recordings/call.wav")
    assert not overlay.btn_record.isChecked()
    assert overlay.btn_replay.isEnabled()
    requested_actions = []
    overlay.signal_replay_action.connect(requested_actions.append)
    overlay.btn_replay.click()
    overlay.set_replay_state("pause")
    assert overlay.btn_replay.text() == "⏸"
    assert overlay.btn_replay.accessibleName() == "Pause replay"
    overlay.btn_replay.click()
    overlay.set_replay_state("stop")
    assert overlay.btn_replay.text() == "■"
    assert overlay.btn_replay.accessibleName() == "Stop replay"
    overlay.btn_replay.click()
    overlay.set_replay_state("play")
    assert overlay.btn_replay.text() == "▶"
    assert requested_actions == ["play", "pause", "stop"]


def verify_ai_model_selector_changes_only_on_user_selection():
    overlay = OverlayWindow(selected_ai_model="gpt-4.1-nano")
    assert overlay.combo_ai_model.currentData() == "gpt-4.1-nano"
    assert overlay.combo_ai_model.accessibleName() == "Chọn model OpenAI"
    assert overlay.combo_ai_model.count() == 4

    changes = []
    overlay.signal_ai_model_changed.connect(changes.append)
    overlay.set_selected_ai_model("gpt-4.1-mini")
    assert changes == []

    overlay.combo_ai_model.setCurrentIndex(
        overlay.combo_ai_model.findData("gpt-5-nano")
    )
    QApplication.processEvents()
    assert changes == ["gpt-5-nano"]
    assert "gpt-5-nano" in overlay.combo_ai_model.toolTip()


def verify_audio_device_menu_lists_and_emits_selected_endpoints():
    overlay = OverlayWindow()
    speakers = [
        {"name": "Monitor", "default": False},
        {"name": "USB Speakers", "default": True},
    ]
    microphones = [
        {"name": "USB Microphone", "default": True},
        {"name": "Webcam Microphone", "default": False},
    ]
    overlay.set_audio_devices(
        speakers,
        microphones,
        "USB Speakers",
        "USB Microphone",
    )

    assert overlay.btn_audio_devices.accessibleName() == (
        "Chọn loa và microphone"
    )
    assert len(overlay.speaker_device_menu.actions()) == 2
    assert len(overlay.microphone_device_menu.actions()) == 2
    assert "USB Speakers" in overlay.btn_audio_devices.toolTip()

    changes = []
    overlay.signal_audio_devices_changed.connect(
        lambda speaker, microphone: changes.append((speaker, microphone))
    )
    monitor_action = next(
        action
        for action in overlay.speaker_device_menu.actions()
        if action.data() == "Monitor"
    )
    monitor_action.trigger()
    QApplication.processEvents()
    assert changes == [("Monitor", "USB Microphone")]


if __name__ == "__main__":
    app = QApplication.instance() or QApplication([])
    verify_grid_positions()
    verify_live_stylesheet_is_well_formed()
    verify_independent_bounded_history()
    verify_pin_buffer_badge_and_release()
    verify_translation_replaces_pending_result()
    verify_out_of_order_results_follow_utterance_order()
    verify_live_never_freezes()
    verify_live_is_rendered_oldest_to_current()
    verify_live_keeps_a_long_rolling_transcript()
    verify_live_displays_stable_speaker_badges_and_parallel_partials()
    verify_live_region_is_split_into_equal_realtime_and_context_columns()
    verify_context_english_updates_and_rejects_stale_results()
    verify_new_content_returns_each_region_to_its_focus_anchor()
    verify_new_contextual_translation_returns_to_its_focus_anchor()
    verify_all_history_regions_follow_top_to_bottom_and_scroll_to_bottom()
    verify_bottom_follow_is_smooth_and_pin_stops_it()
    verify_contextual_translation_keeps_bounded_scrollable_history()
    verify_contextual_translation_uses_fixed_third_row()
    verify_each_history_region_has_independent_font_controls_after_pin()
    verify_frameless_window_resize_hit_regions()
    verify_interactive_controls_override_resize_edges()
    verify_native_hit_test_coordinates_survive_negative_monitor_origin()
    verify_new_content_pulses_without_changing_history_semantics()
    verify_no_reply_recommendation_is_rendered()
    verify_overlay_signals_preserve_ids()
    verify_offscreen_window_state_is_clamped()
    verify_session_controls_have_stable_states_and_accessible_names()
    verify_ai_model_selector_changes_only_on_user_selection()
    verify_audio_device_menu_lists_and_emits_selected_endpoints()
    verify_remote_labels_become_icons_in_conversation_views()
    verify_empty_regions_do_not_show_processing_status()
    app.processEvents()
    print("All glanceable dashboard checks passed.")
