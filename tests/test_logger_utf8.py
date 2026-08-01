"""Windows redirected output must accept Vietnamese without logging errors."""

import io

from utils.logger import _configure_utf8_stream


def test_redirected_stream_is_reconfigured_to_utf8():
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252")

    _configure_utf8_stream(stream)
    stream.write("Tiếng Việt: ngữ cảnh và phản hồi")
    stream.flush()

    assert stream.encoding.lower().replace("-", "") == "utf8"
    assert "Tiếng Việt" in raw.getvalue().decode("utf-8")
