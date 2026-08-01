from core.session_transcript import SessionTranscript


def test_transcript_combines_async_results_and_exports_utf8(tmp_path):
    transcript = SessionTranscript()
    transcript.record_translation(2, "Tôi sẽ kiểm tra.")
    transcript.record_english(1, "Could you explain the architecture?")
    transcript.record_english(2, "I will check it.")
    transcript.record_contextual_translation(2, "Bạn hỏi kiến trúc; tôi sẽ kiểm tra.")
    transcript.record_assistance(2, {
        "explanation": "Người nói cam kết sẽ kiểm tra.",
        "keywords": "check — kiểm tra",
        "english": "No reply needed.",
        "vietnamese": "Không cần phản hồi.",
        "should_reply": False,
    })

    output = transcript.export(tmp_path / "session.txt", "call.wav")
    content = output.read_text(encoding="utf-8")
    assert "Could you explain the architecture?" in content
    assert "Bạn hỏi kiến trúc; tôi sẽ kiểm tra." in content
    assert "Reply needed: No" in content
    assert "Không cần phản hồi." in content
    assert "Recording: call.wav" in content


def test_transcript_retention_is_bounded():
    transcript = SessionTranscript(max_utterances=2)
    transcript.record_english(1, "first")
    transcript.record_english(2, "second")
    transcript.record_english(3, "third")
    content = transcript.render_text()
    assert "English: first" not in content
    assert "English: second" in content
    assert "English: third" in content
