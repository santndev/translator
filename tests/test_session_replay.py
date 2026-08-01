from core.session_replay import SessionReplayTimeline


def test_timeline_starts_at_first_audio_and_preserves_event_order():
    timeline = SessionReplayTimeline()
    timeline.arm()
    timeline.record("ignored_before_audio", 1, timestamp=10.0)
    timeline.mark_audio_started(timestamp=10.0)
    timeline.record("signal_stream1c", "hello", timestamp=10.125)
    timeline.record("signal_stream1a", 1, "hello", "xin chào", timestamp=10.5)

    events = timeline.finish(has_audio=True)

    assert [(event.offset_ms, event.stream, event.payload) for event in events] == [
        (125, "signal_stream1c", ("hello",)),
        (500, "signal_stream1a", (1, "hello", "xin chào")),
    ]


def test_empty_recording_does_not_replace_last_replay_timeline():
    timeline = SessionReplayTimeline()
    timeline.arm()
    timeline.mark_audio_started(timestamp=1.0)
    timeline.record("signal_stream1c", "kept", timestamp=1.1)
    first = timeline.finish(has_audio=True)

    timeline.arm()
    timeline.record("signal_stream1c", "ignored", timestamp=2.0)

    assert timeline.finish(has_audio=False) == first
