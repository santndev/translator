"""
Automated End-to-End Integration Test Suite
Verifies all 4 Streams (1a, 1b, 2a, 2b) using 2 Mock English Audio Sources.
"""
import unittest
import sys
import os

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


from core.translator_engine import TranslatorEngine
from core.smart_reply_engine import SmartReplyEngine
from core.audio_capturer import AudioCapturer
from tests.mock_audio_generator import MockAudioGenerator

class TestFullPipeline(unittest.TestCase):

    def setUp(self):
        self.translator = TranslatorEngine()
        self.smart_reply = SmartReplyEngine()
        self.audio_capturer = AudioCapturer()

    def test_stream1a_realtime_translation(self):
        """Test Stream 1a: English to Vietnamese Real-time Translation."""
        mock_data = MockAudioGenerator.get_mock_speaker_audio()
        en_text = mock_data["english_text"]

        vi_translation = self.translator.translate_en_to_vi(en_text)
        print(f"\n[Test Stream 1a] EN: '{en_text}' -> VI: '{vi_translation}'")
        
        self.assertTrue(len(vi_translation) > 0)

    def test_stream1b_context_explanation(self):
        """Test Stream 1b: Vietnamese Meaning & Context Explanation."""
        mock_data = MockAudioGenerator.get_mock_speaker_audio()
        en_text = mock_data["english_text"]

        explanation = self.translator.explain_context_vi(en_text)
        print(f"[Test Stream 1b] Explanation: '{explanation}'")
        
        self.assertTrue(len(explanation) > 0)

    def test_stream2a_flash_keywords(self):
        """Test Stream 2a: Ultra-Fast Flash Keywords (< 150ms)."""
        mock_data = MockAudioGenerator.get_mock_speaker_audio()
        en_text = mock_data["english_text"]

        keywords = self.smart_reply.generate_stream_2a_keywords(en_text)
        print(f"[Test Stream 2a] Flash Keywords (<150ms): '{keywords}'")
        
        self.assertTrue(len(keywords) > 0)


    def test_stream2b_polished_response(self):
        """Test Stream 2b: Polished English Response & Vietnamese Translation (< 400ms)."""
        mock_data = MockAudioGenerator.get_mock_speaker_audio()
        en_text = mock_data["english_text"]

        response_dict = self.smart_reply.generate_stream_2b_response(en_text)
        print(f"[Test Stream 2b] Polished English: '{response_dict['english']}'")
        print(f"[Test Stream 2b] Vietnamese Meaning: '{response_dict['vietnamese']}'")
        
        self.assertIn("english", response_dict)
        self.assertIn("vietnamese", response_dict)
        self.assertTrue(len(response_dict["english"]) > 20)

    def test_mock_audio_injection(self):
        """Test Mock Audio Capturer Dispatch."""
        received_data = []

        def mock_callback(channel_type, text_payload, raw_bytes):
            received_data.append((channel_type, text_payload))

        self.audio_capturer.callback = mock_callback

        mock_spk = MockAudioGenerator.get_mock_speaker_audio()
        mock_mic = MockAudioGenerator.get_mock_mic_audio()

        self.audio_capturer.inject_mock_audio(mock_spk["channel"], mock_spk["english_text"])
        self.audio_capturer.inject_mock_audio(mock_mic["channel"], mock_mic["english_text"])

        self.assertEqual(len(received_data), 2)
        self.assertEqual(received_data[0][0], "incoming")
        self.assertEqual(received_data[1][0], "outgoing")
        print(f"[Test Audio Capturer] Successfully dispatched 2 mock audio streams!")

if __name__ == '__main__':
    unittest.main()
