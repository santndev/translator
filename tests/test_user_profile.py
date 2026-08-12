from datetime import date
import json

from core.dynamic_ai_generator import DynamicAIGenerator
from core.user_profile import UserProfile


def test_exact_age_is_calculated_from_full_birth_date():
    profile = UserProfile.from_mapping({"birth_date": "2000-10-20"})

    before_birthday = profile.try_answer(
        "How old are you?", today=date(2026, 8, 2)
    )
    on_birthday = profile.try_answer(
        "What's your age?", today=date(2026, 10, 20)
    )

    assert before_birthday.english == "I'm 25 years old."
    assert on_birthday.english == "I'm 26 years old."


def test_birth_year_only_does_not_guess_an_exact_age():
    profile = UserProfile.from_mapping({"birth_year": 2000})

    reply = profile.try_answer("How old are you?", today=date(2026, 8, 2))

    assert reply.english == "I was born in 2000."
    assert "26 years old" not in reply.english


def test_invalid_birth_date_does_not_discard_other_profile_fields():
    profile = UserProfile.from_mapping(
        {
            "preferred_name": "Minh",
            "birth_date": "02-April",
            "birth_year": 2000,
        }
    )

    assert profile.try_answer("What's your name?").english == "My name is Minh."
    assert profile.try_answer("How old are you?").english == "I was born in 2000."


class FailingCloud:
    is_configured = True
    model = "must-not-be-called"

    def __init__(self):
        self.calls = 0

    def generate_json(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("profile answer should bypass cloud AI")


def test_profile_question_bypasses_cloud_for_low_latency():
    cloud = FailingCloud()
    profile = UserProfile.from_mapping(
        {"preferred_name": "Minh", "cloud_shareable_fields": []}
    )
    generator = DynamicAIGenerator(cloud, user_profile=profile)

    result = generator.generate_all_streams("What's your name?")

    assert result["stream_2b_en"] == "My name is Minh."
    assert result["stream_2b_vi"] == "Tên tôi là Minh."
    assert result["stream_2b_should_reply"] is True
    assert cloud.calls == 0


class SelfAnsweredCloud:
    is_configured = True
    model = "test-model"

    def __init__(self):
        self.calls = 0

    def generate_json(self, *_args, **_kwargs):
        self.calls += 1
        return {
            "stream_1b": "Người nói đã tự giới thiệu tên.",
            "stream_2a": "name — tên",
            "stream_2b_quick_en": "",
            "stream_2b_quick_vi": "",
            "stream_2b_en": "",
            "stream_2b_vi": "",
            "stream_2b_should_reply": False,
        }


def test_profile_does_not_answer_a_self_answered_training_question():
    cloud = SelfAnsweredCloud()
    profile = UserProfile.from_mapping(
        {"preferred_name": "Minh", "cloud_shareable_fields": []}
    )

    result = DynamicAIGenerator(cloud, user_profile=profile).generate_all_streams(
        "What's your name? My name is Esther."
    )

    assert result["stream_2b_should_reply"] is False
    assert result["stream_2b_en"] == ""
    assert cloud.calls == 1


def test_cloud_context_contains_only_explicitly_shareable_fields():
    profile = UserProfile.from_mapping(
        {
            "preferred_name": "Minh",
            "company": "Private Company",
            "preferred_reply_style": "short_and_natural",
            "cloud_shareable_fields": ["preferred_name"],
        }
    )

    context = profile.cloud_context("Can you introduce yourself?")

    assert "preferred_name: Minh" in context
    assert "Private Company" not in context
    assert "short_and_natural" not in context


def test_profile_template_is_created_without_api_credentials(tmp_path):
    path = tmp_path / "user_profile.json"

    UserProfile.ensure_template(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["preferred_reply_style"] == "short_and_natural"
    assert "api_key" not in json.dumps(data).lower()
