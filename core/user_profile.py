"""Validated local user facts and deterministic personal-answer routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import json
from pathlib import Path
import re

from config import Config
from utils.logger import logger


PROFILE_TEMPLATE = {
    "_instructions": (
        "Fill only facts you want Translator to use. Use YYYY-MM-DD for "
        "birth_date. Only fields in cloud_shareable_fields may be sent to AI APIs."
    ),
    "full_name": "",
    "preferred_name": "",
    "birth_date": "",
    "birth_year": None,
    "job_title": "",
    "company": "",
    "location": "",
    "years_experience": None,
    "preferred_reply_style": "short_and_natural",
    "custom_facts": {},
    "cloud_shareable_fields": ["preferred_reply_style"],
}

TEXT_FIELDS = {
    "full_name",
    "preferred_name",
    "job_title",
    "company",
    "location",
    "preferred_reply_style",
}
KNOWN_FIELDS = TEXT_FIELDS | {
    "birth_date",
    "birth_year",
    "years_experience",
    "custom_facts",
}


@dataclass(frozen=True)
class ProfileReply:
    intent: str
    explanation_vi: str
    keywords: str
    english: str
    vietnamese: str

    def as_stream_bundle(self) -> dict:
        return {
            "stream_1b": self.explanation_vi,
            "stream_2a": self.keywords,
            "stream_2b_quick_en": self.english,
            "stream_2b_quick_vi": self.vietnamese,
            "stream_2b_en": self.english,
            "stream_2b_vi": self.vietnamese,
            "stream_2b_should_reply": True,
        }


@dataclass(frozen=True)
class UserProfile:
    values: dict[str, object] = field(default_factory=dict)
    cloud_shareable_fields: frozenset[str] = frozenset()

    @classmethod
    def empty(cls) -> "UserProfile":
        return cls()

    @classmethod
    def load(cls, path: str | Path | None = None) -> "UserProfile":
        profile_path = Path(path or Config.USER_PROFILE_PATH)
        cls.ensure_template(profile_path)
        try:
            if profile_path.stat().st_size > 64 * 1024:
                raise ValueError("profile file exceeds 64 KiB")
            raw = json.loads(profile_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("profile root must be a JSON object")
            profile = cls.from_mapping(raw)
            logger.info(f"User profile loaded from {profile_path}")
            return profile
        except (
            OSError,
            TypeError,
            ValueError,
            OverflowError,
            json.JSONDecodeError,
        ) as error:
            logger.warning(f"User profile ignored: {error}")
            return cls.empty()

    @staticmethod
    def ensure_template(path: str | Path | None = None) -> Path:
        profile_path = Path(path or Config.USER_PROFILE_PATH)
        if profile_path.exists():
            return profile_path
        try:
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            profile_path.write_text(
                json.dumps(PROFILE_TEMPLATE, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as error:
            logger.warning(f"Could not create user profile template: {error}")
        return profile_path

    @classmethod
    def from_mapping(cls, raw: dict) -> "UserProfile":
        values: dict[str, object] = {}
        for key in TEXT_FIELDS:
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                values[key] = cls._bounded_text(value)

        birth_date = raw.get("birth_date")
        if isinstance(birth_date, str) and birth_date.strip():
            try:
                parsed_date = date.fromisoformat(birth_date.strip())
                if parsed_date > date.today() or parsed_date.year < 1900:
                    raise ValueError("outside the supported range")
                values["birth_date"] = parsed_date
                values["birth_year"] = parsed_date.year
            except ValueError:
                logger.warning(
                    "Ignored invalid user profile field 'birth_date'; "
                    "expected YYYY-MM-DD."
                )
        if "birth_date" not in values:
            birth_year = raw.get("birth_year")
            if birth_year is not None and birth_year != "":
                try:
                    year = int(birth_year)
                    if year < 1900 or year > date.today().year:
                        raise ValueError("outside the supported range")
                    values["birth_year"] = year
                except (TypeError, ValueError):
                    logger.warning(
                        "Ignored invalid user profile field 'birth_year'."
                    )

        experience = raw.get("years_experience")
        if experience is not None and experience != "":
            try:
                years = int(experience)
                if not 0 <= years <= 80:
                    raise ValueError("outside the supported range")
                values["years_experience"] = years
            except (TypeError, ValueError):
                logger.warning(
                    "Ignored invalid user profile field 'years_experience'."
                )

        custom_facts = raw.get("custom_facts", {})
        if isinstance(custom_facts, dict):
            cleaned_facts = {
                cls._bounded_text(str(key), limit=60): cls._bounded_text(
                    str(value), limit=200
                )
                for key, value in list(custom_facts.items())[:20]
                if str(key).strip() and str(value).strip()
            }
            if cleaned_facts:
                values["custom_facts"] = cleaned_facts

        allowed = raw.get("cloud_shareable_fields", [])
        shareable = frozenset(
            field_name
            for field_name in allowed
            if isinstance(field_name, str)
            and field_name in KNOWN_FIELDS
            and field_name in values
        ) if isinstance(allowed, list) else frozenset()
        return cls(values=values, cloud_shareable_fields=shareable)

    def try_answer(self, english_text: str, *, today: date | None = None) -> ProfileReply | None:
        latest = english_text.split("\nPrevious context:", 1)[0].strip()
        normalized = re.sub(r"[^a-z0-9']+", " ", latest.lower()).strip()
        current_date = today or date.today()

        if self._matches(normalized, (
            r"\bhow old are you\b", r"\bwhat(?:'s| is) your age\b",
        )):
            return self._age_reply(current_date)
        if self._matches(normalized, (
            r"\bwhat year were you born\b", r"\bwhen were you born\b",
            r"\bwhat(?:'s| is) your birth(?:day| date| year)\b",
        )):
            return self._birth_reply()
        if self._matches(normalized, (
            r"\bwhat(?:'s| is) your name\b", r"\bhow should i call you\b",
            r"\bwho are you\b",
        )):
            return self._name_reply()
        if self._matches(normalized, (
            r"\bwhat do you do\b", r"\bwhat(?:'s| is) your (?:job|occupation)\b",
            r"\bwhat do you do for (?:work|a living)\b",
        )):
            return self._job_reply()
        if self._matches(normalized, (
            r"\bwhere do you work\b", r"\bwhich company do you work (?:at|for)\b",
            r"\bwhat company do you work (?:at|for)\b",
        )):
            return self._company_reply()
        if self._matches(normalized, (
            r"\bwhere are you from\b", r"\bwhere do you live\b",
            r"\bwhere are you based\b",
        )):
            return self._location_reply()
        if self._matches(normalized, (
            r"\bhow many years of experience do you have\b",
            r"\bhow long have you (?:worked|been working)\b",
            r"\bwhat(?:'s| is) your experience\b",
        )):
            return self._experience_reply()
        return None

    def cloud_context(self, english_text: str) -> str:
        """Return only explicitly shareable facts for personal questions."""
        latest = english_text.split("\nPrevious context:", 1)[0].lower()
        if not re.search(r"\b(you|your|yourself)\b", latest):
            style = self.values.get("preferred_reply_style")
            if "preferred_reply_style" in self.cloud_shareable_fields and style:
                return f"preferred_reply_style: {style}"
            return ""
        lines = []
        for key in sorted(self.cloud_shareable_fields):
            value = self.values.get(key)
            if value is None:
                continue
            if isinstance(value, date):
                rendered = value.isoformat()
            elif isinstance(value, dict):
                rendered = json.dumps(value, ensure_ascii=False)
            else:
                rendered = str(value)
            lines.append(f"{key}: {rendered}")
        return "\n".join(lines)[:1500]

    def _age_reply(self, today: date) -> ProfileReply | None:
        birth_date = self.values.get("birth_date")
        if isinstance(birth_date, date):
            age = today.year - birth_date.year - (
                (today.month, today.day) < (birth_date.month, birth_date.day)
            )
            return ProfileReply(
                "ask_age", "Hỏi tuổi của bạn; trả lời từ ngày sinh trong hồ sơ.",
                "age; personal profile", f"I'm {age} years old.", f"Tôi {age} tuổi.",
            )
        year = self.values.get("birth_year")
        if isinstance(year, int):
            return ProfileReply(
                "ask_age", "Hỏi tuổi; hồ sơ chỉ có năm sinh nên không đoán tuổi chính xác.",
                "age; birth year", f"I was born in {year}.", f"Tôi sinh năm {year}.",
            )
        return None

    def _birth_reply(self) -> ProfileReply | None:
        birth_date = self.values.get("birth_date")
        if isinstance(birth_date, date):
            english = f"I was born on {birth_date.strftime('%B')} {birth_date.day}, {birth_date.year}."
            vietnamese = f"Tôi sinh ngày {birth_date.day} tháng {birth_date.month} năm {birth_date.year}."
        else:
            year = self.values.get("birth_year")
            if not isinstance(year, int):
                return None
            english, vietnamese = f"I was born in {year}.", f"Tôi sinh năm {year}."
        return ProfileReply(
            "ask_birth", "Hỏi thời điểm sinh của bạn; dùng dữ liệu hồ sơ.",
            "birth date; personal profile", english, vietnamese,
        )

    def _name_reply(self) -> ProfileReply | None:
        name = self.values.get("preferred_name") or self.values.get("full_name")
        if not isinstance(name, str):
            return None
        return ProfileReply(
            "ask_name", "Hỏi tên của bạn; dùng dữ liệu hồ sơ.", "name; introduction",
            f"My name is {name}.", f"Tên tôi là {name}.",
        )

    def _job_reply(self) -> ProfileReply | None:
        job = self.values.get("job_title")
        if not isinstance(job, str):
            return None
        return ProfileReply(
            "ask_job", "Hỏi nghề nghiệp của bạn; dùng dữ liệu hồ sơ.", "job; occupation",
            f"I work as {job}.", f"Tôi làm công việc {job}.",
        )

    def _company_reply(self) -> ProfileReply | None:
        company = self.values.get("company")
        if not isinstance(company, str):
            return None
        return ProfileReply(
            "ask_company", "Hỏi nơi làm việc của bạn; dùng dữ liệu hồ sơ.", "company; workplace",
            f"I work at {company}.", f"Tôi làm việc tại {company}.",
        )

    def _location_reply(self) -> ProfileReply | None:
        location = self.values.get("location")
        if not isinstance(location, str):
            return None
        return ProfileReply(
            "ask_location", "Hỏi nơi bạn sống hoặc làm việc; dùng dữ liệu hồ sơ.", "location; personal profile",
            f"I'm based in {location}.", f"Tôi đang ở {location}.",
        )

    def _experience_reply(self) -> ProfileReply | None:
        years = self.values.get("years_experience")
        if not isinstance(years, int):
            return None
        return ProfileReply(
            "ask_experience", "Hỏi số năm kinh nghiệm; dùng dữ liệu hồ sơ.", "experience; career",
            f"I have {years} years of experience.", f"Tôi có {years} năm kinh nghiệm.",
        )

    @staticmethod
    def _matches(text: str, patterns: tuple[str, ...]) -> bool:
        return any(re.search(pattern, text) for pattern in patterns)

    @staticmethod
    def _bounded_text(value: str, *, limit: int = 200) -> str:
        return " ".join(value.strip().split())[:limit]
