"""Compare reply quality and latency across OpenAI, Gemini, and local NLP.

The benchmark uses a fixed corpus derived from real STT shapes seen in the
YouTube QA test. It never sends the user's saved profile to a provider.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import statistics
import time

from core.dynamic_ai_generator import DynamicAIGenerator
from core.gemini_client import GeminiClient
from core.openai_client import OpenAIClient
from core.translator_engine import TranslatorEngine
from core.user_profile import UserProfile


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    text: str
    should_reply: bool
    content_any: tuple[str, ...] = ()
    deflection_required: bool = False


@dataclass(frozen=True)
class TranslationCase:
    name: str
    utterances: tuple[str, ...]
    expected_any: tuple[str, ...]


CASES = (
    BenchmarkCase(
        "training_intro",
        "Welcome. We are going to ask you 100 English questions.",
        False,
    ),
    BenchmarkCase(
        "self_answered_profile",
        "How are you? I'm doing well. What's your name? My name is Esther. "
        "How old are you? I'm 33 years old.",
        False,
    ),
    BenchmarkCase(
        "self_answered_stt_correction",
        "How often do you write the bus? I never write the bus.",
        False,
        ("ride", "đi xe buýt"),
    ),
    BenchmarkCase(
        "unfinished_fragment",
        "I have some brothers and sisters. What's...",
        False,
    ),
    BenchmarkCase(
        "unknown_family_fact",
        "Do you have any children?",
        True,
        ("private", "rather", "how about you", "what about you"),
        True,
    ),
    BenchmarkCase(
        "unknown_preference",
        "What is your hobby?",
        True,
        ("how about you", "what about you", "rather", "few interests"),
        True,
    ),
    BenchmarkCase(
        "direct_request",
        "Could you lend me $100?",
        True,
        ("lend", "$100", "loan"),
    ),
    BenchmarkCase(
        "technical_question",
        "What is React and how can you best describe it?",
        True,
        ("library", "user interface", "ui"),
    ),
)


TRANSLATION_CASES = (
    TranslationCase(
        "fragment_completion",
        ("Do you love me? Not-", "that way."),
        ("không phải", "không theo"),
    ),
    TranslationCase(
        "stt_homophone_correction",
        ("How often do you ride the bus?", "I never write the bus."),
        ("đi xe buýt",),
    ),
    TranslationCase(
        "technical_identifier_preservation",
        (
            "It sanitizes user input.",
            "Then it executes the prepared statement.",
        ),
        (
            "prepared statement",
            "câu lệnh đã chuẩn bị",
            "câu lệnh đã được chuẩn bị",
            "câu lệnh chuẩn bị",
        ),
    ),
)


class GeminiAdapter:
    """Match the shared provider contract without router fallback."""

    provider_name = "Gemini"

    def __init__(self, client: GeminiClient):
        self.client = client
        self.model = client.model

    @property
    def is_configured(self) -> bool:
        return self.client.is_configured

    def generate_json(self, prompt: str, **kwargs) -> dict:
        kwargs.pop("json_schema", None)
        kwargs.pop("reasoning_effort", None)
        return self.client.generate_json(prompt, **kwargs)

    def generate_text(self, prompt: str, **kwargs) -> str:
        kwargs.pop("reasoning_effort", None)
        return self.client.generate_text(prompt, **kwargs)


class OfflineProvider:
    """Force DynamicAIGenerator to use its deterministic local NLP path."""

    is_configured = False
    model = "dynamic-nlp-local"
    provider_name = "Offline"


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'$-]+\b", text))


def _sentence_count(text: str) -> int:
    return len([part for part in re.split(r"[.!?]+", text) if part.strip()])


def _score(case: BenchmarkCase, result: dict) -> tuple[int, list[str]]:
    score = 0
    failures = []
    should_reply = bool(result.get("stream_2b_should_reply"))
    english = str(result.get("stream_2b_en", "")).strip()
    vietnamese = str(result.get("stream_2b_vi", "")).strip()
    quick_english = str(result.get("stream_2b_quick_en", "")).strip()
    explanation = str(result.get("stream_1b", "")).strip()
    keywords = str(result.get("stream_2a", "")).strip()
    combined = " ".join((explanation, keywords, english, vietnamese)).lower()

    if should_reply == case.should_reply:
        score += 40
    else:
        failures.append("wrong should_reply")

    contract_ok = (
        bool(english and vietnamese)
        if case.should_reply
        else not english
    )
    if contract_ok:
        score += 15
    else:
        failures.append("reply presence contract")

    if not case.content_any or any(
        token.lower() in combined for token in case.content_any
    ):
        score += 20
    else:
        failures.append("missing expected meaning")

    internal_language = re.search(
        r"\b(profile|hồ sơ|missing data|unavailable information|"
        r"previous context|what answer.*want)\b",
        combined,
    )
    if not internal_language:
        score += 10
    else:
        failures.append("internal/meta language visible")

    terms = [term.strip() for term in keywords.split(";") if term.strip()]
    if terms and len(terms) <= 6 and (
        "—" in keywords or " - " in keywords or len(terms) >= 3
    ):
        score += 10
    else:
        failures.append("weak keyword contract")

    concise = (
        (not case.should_reply and not quick_english)
        or (
            case.should_reply
            and 0 < _word_count(quick_english) <= 10
            and _sentence_count(english) <= 2
        )
    )
    if concise:
        score += 5
    else:
        failures.append("reply is not glanceable")

    if case.deflection_required and re.search(
        r"\b(i enjoy|i like|i love|my hobby is|"
        r"i (?:do not|don't) have (?:any )?children|"
        r"i have (?:no|one|two|three|\d+) children)\b",
        english.lower(),
    ):
        score = max(0, score - 25)
        failures.append("invented personal fact")

    return score, failures


def _run_provider(name: str, model: str, generator: DynamicAIGenerator) -> dict:
    formatter = TranslatorEngine(ai_client=OfflineProvider())
    rows = []
    for case in CASES:
        started = time.perf_counter()
        if name == "Offline":
            result = generator.generate_all_streams(case.text)
        else:
            result = generator._generate_via_cloud(case.text)
        latency_ms = round((time.perf_counter() - started) * 1000)
        result["stream_2a"] = formatter.format_bilingual_keywords(
            result.get("stream_2a", ""), allow_network=False
        )
        score, failures = _score(case, result)
        rows.append(
            {
                "case": case.name,
                "latency_ms": latency_ms,
                "score": score,
                "failures": failures,
                "should_reply": result.get("stream_2b_should_reply"),
                "explanation": result.get("stream_1b", ""),
                "keywords": result.get("stream_2a", ""),
                "reply_en": result.get("stream_2b_en", ""),
                "reply_vi": result.get("stream_2b_vi", ""),
            }
        )

    latencies = [row["latency_ms"] for row in rows]
    scores = [row["score"] for row in rows]
    return {
        "provider": name,
        "model": model,
        "summary": {
            "average_score": round(statistics.mean(scores), 1),
            "decision_accuracy": round(
                100
                * sum(
                    row["should_reply"] == case.should_reply
                    for row, case in zip(rows, CASES)
                )
                / len(CASES),
                1,
            ),
            "median_latency_ms": round(statistics.median(latencies)),
            "max_latency_ms": max(latencies),
        },
        "cases": rows,
    }


def _run_translation_provider(name: str, model: str, provider) -> dict:
    engine = TranslatorEngine(ai_client=provider)
    rows = []
    for case in TRANSLATION_CASES:
        started = time.perf_counter()
        translated = engine.translate_contextual_en_to_vi(list(case.utterances))
        latency_ms = round((time.perf_counter() - started) * 1000)
        lowered = translated.lower()
        failures = []
        score = 50 if translated else 0
        if not translated:
            failures.append("empty translation")
        if any(expected.lower() in lowered for expected in case.expected_any):
            score += 40
        else:
            failures.append("missing expected contextual meaning")
        if not re.search(r"^\s*(?:remote|you|bạn|từ xa)\s*:", lowered):
            score += 10
        else:
            failures.append("transport speaker label visible")
        rows.append(
            {
                "case": case.name,
                "latency_ms": latency_ms,
                "score": score,
                "failures": failures,
                "translation": translated,
            }
        )
    return {
        "provider": name,
        "model": model,
        "supported": True,
        "summary": {
            "average_score": round(
                statistics.mean(row["score"] for row in rows), 1
            ),
            "median_latency_ms": round(
                statistics.median(row["latency_ms"] for row in rows)
            ),
            "max_latency_ms": max(row["latency_ms"] for row in rows),
        },
        "cases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--section",
        choices=("all", "assistance", "translation"),
        default="all",
    )
    parser.add_argument(
        "--openai-model",
        action="append",
        dest="openai_models",
        help=(
            "Benchmark only the supplied OpenAI model ID. Repeat this option "
            "to compare multiple OpenAI models."
        ),
    )
    args = parser.parse_args()

    openai_key = os.getenv("TRANSLATOR_OPENAI_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    required_keys = [("TRANSLATOR_OPENAI_API_KEY", openai_key)]
    if not args.openai_models:
        required_keys.append(("GEMINI_API_KEY", gemini_key))
    if any(not value for _name, value in required_keys):
        missing = [
            name
            for name, value in required_keys
            if not value
        ]
        raise SystemExit("Missing environment variables: " + ", ".join(missing))

    empty_profile = UserProfile.empty()
    if args.openai_models:
        providers = tuple(
            (
                "OpenAI",
                OpenAIClient(api_key=openai_key, model=model),
            )
            for model in args.openai_models
        )
    else:
        providers = (
            (
                "OpenAI",
                OpenAIClient(api_key=openai_key),
            ),
            (
                "Gemini",
                GeminiAdapter(GeminiClient(api_key=gemini_key)),
            ),
            ("Offline", OfflineProvider()),
        )

    report = {
        "benchmark": "conversation-assistance-v1",
        "cases": [asdict(case) for case in CASES],
        "providers": [],
        "translation_cases": [asdict(case) for case in TRANSLATION_CASES],
        "translation_providers": [],
    }
    if args.section in {"all", "assistance"}:
        for name, provider in providers:
            generator = DynamicAIGenerator(
                ai_client=provider,
                user_profile=empty_profile,
            )
            report["providers"].append(
                _run_provider(name, provider.model, generator)
            )
    if args.section in {"all", "translation"}:
        for name, provider in providers:
            if name == "Offline":
                continue
            report["translation_providers"].append(
                _run_translation_provider(name, provider.model, provider)
            )
        if any(name == "Offline" for name, _provider in providers):
            report["translation_providers"].append(
                {
                    "provider": "Offline",
                    "model": "none",
                    "supported": False,
                    "reason": (
                        "The current offline path has no contextual translation "
                        "model; its fallback uses the online Google Translate endpoint."
                    ),
                }
            )

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
