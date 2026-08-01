"""Standalone assertions for the Qt dashboard (invoked by pytest subprocess)."""

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRect, Qt

from gui.components.glanceable_dashboard import GlanceableDashboard
from gui.overlay_window import OverlayWindow


def make_dashboard() -> GlanceableDashboard:
    widget = GlanceableDashboard()
    widget.resize(840, 560)
    return widget


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
    assert nested.stretch(1) == 2


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


def verify_live_region_is_split_into_equal_realtime_and_context_columns():
    dashboard = make_dashboard()
    dashboard.show()
    QApplication.processEvents()

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
    QApplication.processEvents()
    context_bar = dashboard.live_region.context_scroll.verticalScrollBar()
    assert context_bar.maximum() > 0
    context_bar.setValue(0)
    dashboard.update_contextual_english(9, current_context)
    dashboard.update_contextual_translation(
        7,
        "This stale result must not replace the current context.",
        "Bản dịch cũ",
    )
    QApplication.processEvents()

    assert dashboard.live_region.contextual_english == current_context.strip()
    assert "Current English context" in dashboard.live_region.context_label.text()
    assert "stale result" not in dashboard.live_region.context_label.text()
    assert context_bar.value() == context_bar.maximum()
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
    QApplication.processEvents()

    live_bar = dashboard.live_region.scroll.verticalScrollBar()
    keyword_bar = dashboard.keywords_region.scroll.verticalScrollBar()
    assert live_bar.maximum() > 0
    assert keyword_bar.maximum() > 0
    live_bar.setValue(0)
    keyword_bar.setValue(keyword_bar.maximum())

    dashboard.update_stream1c("the newest live words")
    dashboard.update_stream2a(21, "newest keyword " + ("detail " * 30))
    QApplication.processEvents()

    assert live_bar.value() == live_bar.maximum()
    assert keyword_bar.value() == keyword_bar.maximum()
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
    QApplication.processEvents()

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
    QApplication.processEvents()

    assert context_bar.value() == context_bar.maximum()
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
    QApplication.processEvents()

    for region in dashboard.regions:
        scroll_bar = region.scroll.verticalScrollBar()
        assert scroll_bar.maximum() > 0, region.title
        assert scroll_bar.value() == scroll_bar.maximum(), region.title
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
    QApplication.processEvents()

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
    assert "font-size:14px" in (
        dashboard.contextual_translation_region.content_label.text()
    )


def verify_frameless_window_resize_hit_regions():
    hit = OverlayWindow._resize_hit_test
    assert hit(0, 0, 800, 600) == OverlayWindow._HTTOPLEFT
    assert hit(799, 599, 800, 600) == OverlayWindow._HTBOTTOMRIGHT
    assert hit(0, 300, 800, 600) == OverlayWindow._HTLEFT
    assert hit(400, 0, 800, 600) == OverlayWindow._HTTOP
    assert hit(400, 300, 800, 600) == 0


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
    verify_live_region_is_split_into_equal_realtime_and_context_columns()
    verify_context_english_updates_and_rejects_stale_results()
    verify_new_content_returns_each_region_to_its_focus_anchor()
    verify_new_contextual_translation_returns_to_its_focus_anchor()
    verify_all_history_regions_follow_top_to_bottom_and_scroll_to_bottom()
    verify_contextual_translation_keeps_bounded_scrollable_history()
    verify_contextual_translation_uses_fixed_third_row()
    verify_frameless_window_resize_hit_regions()
    verify_no_reply_recommendation_is_rendered()
    verify_overlay_signals_preserve_ids()
    verify_offscreen_window_state_is_clamped()
    verify_session_controls_have_stable_states_and_accessible_names()
    app.processEvents()
    print("All glanceable dashboard checks passed.")
