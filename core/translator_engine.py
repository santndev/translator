"""
Translator & Context Explanation Engine
Handles Stream 1a (Realtime EN->VI Translation) and Stream 1b (Vietnamese Meaning & Context Explanation)
"""
import urllib.parse
import urllib.request
import json
from utils.logger import logger

from core.dynamic_ai_generator import DynamicAIGenerator
from core.ai_provider import AIProviderRouter

class TranslatorEngine:
    CONTEXT_TRANSLATION_MAX_CHARS = 700
    CONTEXT_TRANSLATION_MAX_UTTERANCES = 10
    KEYWORD_GLOSSARY = {
        "api": "giao diện lập trình",
        "architecture": "kiến trúc",
        "availability": "tính sẵn sàng",
        "cache": "bộ nhớ đệm",
        "cluster": "cụm máy",
        "concurrency": "xử lý đồng thời",
        "consistency": "tính nhất quán",
        "constraint": "ràng buộc",
        "database": "cơ sở dữ liệu",
        "deadline": "thời hạn",
        "dependency": "phụ thuộc",
        "deployment": "triển khai",
        "distributed": "phân tán",
        "error": "lỗi",
        "event": "sự kiện",
        "feature": "tính năng",
        "framework": "khung phần mềm",
        "inference": "suy luận",
        "latency": "độ trễ",
        "memory": "bộ nhớ",
        "microservices": "vi dịch vụ",
        "model": "mô hình",
        "performance": "hiệu năng",
        "query": "truy vấn",
        "queue": "hàng đợi",
        "realtime": "thời gian thực",
        "replica": "bản sao",
        "response": "phản hồi",
        "rollback": "quay lui",
        "scalability": "khả năng mở rộng",
        "security": "bảo mật",
        "sharding": "phân mảnh dữ liệu",
        "state": "trạng thái",
        "storage": "lưu trữ",
        "testability": "khả năng kiểm thử",
        "testing": "kiểm thử",
        "throughput": "thông lượng",
        "token": "mã xác thực",
        "traffic": "lưu lượng",
        "transaction": "giao dịch",
        "websocket": "kết nối hai chiều",
    }

    def __init__(self, gemini_client=None, *, ai_client=None):
        # Free Google Translate RPC Endpoint
        self.gt_url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=vi&dt=t&q="
        self.ai = ai_client or gemini_client or AIProviderRouter()
        self.ai_generator = DynamicAIGenerator(ai_client=self.ai)

    def translate_en_to_vi(self, english_text: str) -> str:
        """
        Stream 1a: Real-time translation from English to Vietnamese.
        """
        if not english_text or not english_text.strip():
            return ""
        try:
            url = self.gt_url + urllib.parse.quote(english_text.strip())
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                result = json.loads(response.read().decode('utf-8'))
                translated_parts = [part[0] for part in result[0] if part[0]]
                return "".join(translated_parts)
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return f"(Dịch tự động: {english_text})"

    def translate_contextual_en_to_vi(self, recent_utterances: list[str]) -> str:
        """Translate the newest turn using bounded prior conversation context."""
        context = self._select_readable_translation_context(recent_utterances)
        if not context:
            return ""

        newest_text = context[-1]
        if not self.ai.is_configured:
            return self.translate_en_to_vi(newest_text)

        dialogue = "\n".join(
            f"{index + 1}. {text}" for index, text in enumerate(context)
        )
        prompt = (
            "Translate only the FINAL line of this recent English conversation "
            "into natural Vietnamese for quick reading. Use all earlier lines "
            "only to resolve pronouns, omitted subjects, terminology, and "
            "sentence fragments. Make the final translation understandable "
            "on its own, but do not repeat or summarize earlier turns. "
            "Preserve technical meaning, SQL/code/identifiers, and punctuation "
            "that belongs to code. Translate ordinary technical prose naturally "
            "from context rather than applying a fixed glossary. Do not explain, "
            "summarize, or add facts. Return Vietnamese text only.\n\n"
            f"{dialogue}"
        )
        try:
            return self.ai.generate_text(
                prompt,
                max_output_tokens=300,
                reasoning_effort="none",
                thinking_level="minimal",
            ).strip()
        except Exception as error:
            logger.warning(
                "Contextual translation fallback to combined translation: "
                f"{error}"
            )
            return self.translate_en_to_vi(newest_text)

    @classmethod
    def _select_readable_translation_context(
        cls, recent_utterances: list[str]
    ) -> list[str]:
        """Keep more than three fragments while bounding the visible translation."""
        normalized = [text.strip() for text in recent_utterances if text.strip()]
        selected = []
        used_chars = 0
        for text in reversed(normalized):
            if len(selected) >= cls.CONTEXT_TRANSLATION_MAX_UTTERANCES:
                break
            separator_chars = 1 if selected else 0
            if (
                selected
                and used_chars + separator_chars + len(text)
                > cls.CONTEXT_TRANSLATION_MAX_CHARS
            ):
                break
            if not selected and len(text) > cls.CONTEXT_TRANSLATION_MAX_CHARS:
                selected.append(text[-cls.CONTEXT_TRANSLATION_MAX_CHARS :])
                break
            selected.append(text)
            used_chars += separator_chars + len(text)
        return list(reversed(selected))

    def format_bilingual_keywords(
        self, keywords_text: str, allow_network: bool = True
    ) -> str:
        """Format keyword chips as English — Vietnamese without blocking fast mode."""
        terms = [
            term.strip()
            for term in keywords_text.replace(",", ";").split(";")
            if term.strip()
        ][:6]
        if not terms:
            return ""

        translations = {}
        unknown = []
        for term in terms:
            translated = self.KEYWORD_GLOSSARY.get(term.lower())
            if translated:
                translations[term] = translated
            else:
                unknown.append(term)

        if allow_network and unknown:
            combined = " ; ".join(unknown)
            translated_combined = self.translate_en_to_vi(combined)
            translated_parts = [
                part.strip() for part in translated_combined.split(";")
            ]
            if len(translated_parts) == len(unknown):
                translations.update(dict(zip(unknown, translated_parts)))

        display_terms = terms
        if not allow_network:
            known_terms = [term for term in terms if translations.get(term)]
            if len(known_terms) >= 3:
                display_terms = known_terms

        return " ; ".join(
            (
                f"{term} — {translations[term]}"
                if translations.get(term)
                else term
            )
            for term in display_terms
        )

    def explain_context_vi(self, english_text: str, vi_translation: str = "") -> str:
        """
        Stream 1b: Explains the meaning, intent, or technical context in Vietnamese dynamically.
        """
        if not english_text or not english_text.strip():
            return ""
        res = self.ai_generator.generate_all_streams(english_text)
        return res.get("stream_1b", f"Đối phương đang hỏi về: '{english_text.strip()}'")
