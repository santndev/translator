"""
Mock Audio Payload Generator for Automated Testing
Reads dynamic test content from mock_test_data.json if present.
"""
import os
import json
from utils.logger import logger

class MockAudioGenerator:
    @staticmethod
    def _load_data_from_file() -> dict:
        file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mock_test_data.json'))
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading mock_test_data.json: {e}")
        return {}

    @classmethod
    def get_mock_speaker_audio(cls) -> dict:
        """Returns mock incoming speaker English audio text & data."""
        data = cls._load_data_from_file()
        en_text = data.get("incoming_speaker", {}).get("english_text", "Can you explain Object-Oriented Programming principles?")
        return {
            "channel": "incoming",
            "english_text": en_text,
            "expected_keywords": ["Class", "Encapsulation", "Inheritance", "Polymorphism"],
        }

    @classmethod
    def get_mock_mic_audio(cls) -> dict:
        """Returns mock outgoing microphone English audio text & data."""
        data = cls._load_data_from_file()
        en_text = data.get("outgoing_mic", {}).get("english_text", "Dependency injection helps decouple software modules and improves testability.")
        return {
            "channel": "outgoing",
            "english_text": en_text,
            "expected_keywords": ["Dependency", "decouple", "testability"],
        }
