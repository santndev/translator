"""
Dual-Stream AI Smart Reply Engine
Powered by DynamicAIGenerator for dynamic, un-hardcoded response generation.
Handles:
- Stream 2a: Ultra-Fast Flash Keywords & Concepts (< 150ms)
- Stream 2b: Polished English Response & Vietnamese Meaning (< 400ms)
"""
import time
import threading
from core.dynamic_ai_generator import DynamicAIGenerator
from utils.logger import logger

class SmartReplyEngine:
    def __init__(self):
        self.context_history = []
        self.ai_generator = DynamicAIGenerator()

    def generate_stream_2a_keywords(self, english_text: str) -> str:
        """
        Stream 2a: Ultra-fast flash keywords generator (< 150ms).
        """
        start_time = time.time()
        res = self.ai_generator.generate_all_streams(english_text)
        keywords = res.get("stream_2a", "Keywords")
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Stream 2a generated dynamically in {elapsed_ms}ms: {keywords}")
        return keywords

    def generate_stream_2b_response(self, english_text: str) -> dict:
        """
        Stream 2b: Polished English Response + Vietnamese translation (< 400ms).
        Returns a dict: {'english': ..., 'vietnamese': ...}
        """
        start_time = time.time()
        res = self.ai_generator.generate_all_streams(english_text)
        
        resp_en = res.get("stream_2b_en", "Waiting for input...")
        resp_vi = res.get("stream_2b_vi", "(Đang chờ dữ liệu đầu vào...)")

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Stream 2b generated dynamically in {elapsed_ms}ms")
        return {
            "english": resp_en,
            "vietnamese": resp_vi
        }
