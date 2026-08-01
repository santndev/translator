"""
Translator & Context Explanation Engine
Handles Stream 1a (Realtime EN->VI Translation) and Stream 1b (Vietnamese Meaning & Context Explanation)
"""
import urllib.parse
import urllib.request
import json
from utils.logger import logger

from core.dynamic_ai_generator import DynamicAIGenerator

class TranslatorEngine:
    def __init__(self):
        # Free Google Translate RPC Endpoint
        self.gt_url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=vi&dt=t&q="
        self.ai_generator = DynamicAIGenerator()

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

    def explain_context_vi(self, english_text: str, vi_translation: str = "") -> str:
        """
        Stream 1b: Explains the meaning, intent, or technical context in Vietnamese dynamically.
        """
        if not english_text or not english_text.strip():
            return ""
        res = self.ai_generator.generate_all_streams(english_text)
        return res.get("stream_1b", f"Đối phương đang hỏi về: '{english_text.strip()}'")


