# ai-chatbot-rag/tests/test_tone_adjuster.py

import unittest
from src.utils.tone_adjuster import ToneAdjuster

class TestToneAdjuster(unittest.TestCase):
    def setUp(self):
        self.adjuster = ToneAdjuster()
    
    def test_detect_tone(self):
        self.assertEqual(self.adjuster.detect_tone_from_query("Xin hỏi về lãi suất"), "professional")
        self.assertEqual(self.adjuster.detect_tone_from_query("Bạn ơi giúp mình với"), "friendly")
        self.assertEqual(self.adjuster.detect_tone_from_query("Thời tiết hôm nay"), "default")
    
    def test_adjust_response(self):
        response = "Lãi suất hiện tại là 5%"
        adjusted = self.adjuster.adjust_response(response, "professional")
        self.assertTrue(adjusted.startswith(("Kính chào", "Xin chào")) or "Trân trọng" in adjusted)
        
        friendly_adjusted = self.adjuster.adjust_response(response, "friendly")
        self.assertIn("bạn", friendly_adjusted.lower())

if __name__ == "__main__":
    unittest.main()