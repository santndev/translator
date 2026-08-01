from core.session_replay import ReplayEvent
from main import AppController


class _Signal:
    def __init__(self):
        self.payloads = []

    def emit(self, *payload):
        self.payloads.append(payload)


class _Overlay:
    def __init__(self):
        self.signal_stream1c = _Signal()
        self.signal_stream1a = _Signal()


class _Player:
    def position(self):
        return 150


def test_replay_controller_emits_only_events_due_at_audio_position():
    controller = AppController.__new__(AppController)
    controller.overlay = _Overlay()
    controller._replay_player = _Player()
    controller._replay_event_index = 0
    controller._replay_events = (
        ReplayEvent(25, "signal_stream1c", ("hello",)),
        ReplayEvent(150, "signal_stream1a", (1, "hello", "xin chào")),
        ReplayEvent(300, "signal_stream1c", ("later",)),
    )

    controller._emit_due_replay_events()

    assert controller.overlay.signal_stream1c.payloads == [("hello",)]
    assert controller.overlay.signal_stream1a.payloads == [
        (1, "hello", "xin chào")
    ]
    assert controller._replay_event_index == 2
