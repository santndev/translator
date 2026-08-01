"""Tests for the time- and size-bounded rolling conversation context."""

from core.conversation_context import ConversationContext


def test_context_is_not_limited_to_three_utterances():
    context = ConversationContext(max_age_seconds=120, max_chars=1000)

    result = []
    for index in range(8):
        result = context.add(f"fragment {index}", now=float(index))

    assert result == [f"fragment {index}" for index in range(8)]


def test_context_expires_old_utterances_by_time():
    context = ConversationContext(max_age_seconds=10, max_chars=1000)
    context.add("too old", now=0)
    context.add("still recent", now=8)

    result = context.add("current", now=15)

    assert result == ["still recent", "current"]


def test_context_keeps_newest_complete_fragments_within_size_budget():
    context = ConversationContext(max_age_seconds=120, max_chars=12)
    context.add("aaaa", now=0)
    context.add("bbbb", now=1)

    result = context.add("cccc", now=2)

    assert result == ["bbbb", "cccc"]
