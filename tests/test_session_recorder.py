import struct
import wave

from core.session_recorder import SessionRecorder


def test_recorder_writes_playable_pcm_wav(tmp_path):
    recorder = SessionRecorder(tmp_path)
    pcm = struct.pack("<hhhh", 0, 1000, -1000, 0)
    recorder.start()
    recorder.append(pcm, sample_rate=16000, channels=1)
    output = recorder.stop()

    assert output is not None and output.exists()
    assert recorder.last_recording_path == output
    with wave.open(str(output), "rb") as wav_file:
        assert wav_file.getframerate() == 16000
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.readframes(4) == pcm


def test_recorder_does_not_create_empty_recording(tmp_path):
    recorder = SessionRecorder(tmp_path)
    recorder.start()
    assert recorder.stop() is None
    assert list(tmp_path.glob("*.wav")) == []


def test_recorder_ignores_format_change_within_one_file(tmp_path):
    recorder = SessionRecorder(tmp_path)
    first = struct.pack("<hh", 1, 2)
    recorder.start()
    recorder.append(first, sample_rate=16000, channels=1)
    recorder.append(struct.pack("<hhhh", 3, 4, 5, 6), 48000, 2)
    output = recorder.stop()

    with wave.open(str(output), "rb") as wav_file:
        assert wav_file.getnframes() == 2
        assert wav_file.readframes(2) == first
