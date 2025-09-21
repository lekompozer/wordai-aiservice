"""
Language Detection Service
Dịch vụ phát hiện ngôn ngữ tự động với tối ưu cho tiếng Việt và Anh
"""

import re
from typing import Dict, List, Tuple
from src.models.unified_models import Language, LanguageDetectionResult

class LanguageDetector:
    """
    Advanced language detection optimized for Vietnamese and English
    Phát hiện ngôn ngữ nâng cao tối ưu cho tiếng Việt và Anh
    """
    
    def __init__(self):
        # Vietnamese language indicators / Dấu hiệu tiếng Việt
        self.vietnamese_patterns = {
            # Vietnamese-specific characters / Ký tự đặc trưng tiếng Việt
            'vietnamese_chars': r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]',
            
            # Common Vietnamese words / Từ tiếng Việt thường gặp
            'vietnamese_words': r'\b(tôi|tao|mình|anh|chị|em|ạ|ợ|được|là|có|không|của|và|với|cho|để|từ|này|đó|khi|như|về|sau|trước|trong|ngoài|trên|dưới|giữa|bên|cùng|nhưng|mà|hay|hoặc|nếu|thì|sẽ|đã|đang|sắp|vừa|mới|cũ|tốt|xấu|lớn|nhỏ|nhiều|ít|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|trăm|nghìn|triệu|tỷ)\b',
            
            # Vietnamese banking/finance terms / Thuật ngữ ngân hàng/tài chính tiếng Việt
            'vietnamese_finance': r'\b(vay|vốn|tiền|ngân hàng|lãi suất|thu nhập|lương|công việc|thế chấp|tín chấp|bảo hiểm|đầu tư|tiết kiệm|thẻ|tài khoản|giao dịch|chuyển khoản|rút tiền|gửi tiền)\b',
            
            # Vietnamese question words / Từ hỏi tiếng Việt
            'vietnamese_questions': r'\b(gì|ai|nào|đâu|khi nào|bao giờ|tại sao|sao|vì sao|làm sao|thế nào|bao nhiêu|mấy|có phải|có|không)\b',
            
            # Vietnamese politeness markers / Dấu hiệu lịch sự tiếng Việt
            'vietnamese_politeness': r'\b(xin chào|chào|cảm ơn|xin lỗi|làm ơn|vui lòng|cho phép|được không|có thể|giúp|hỗ trợ)\b'
        }
        
        # English language indicators / Dấu hiệu tiếng Anh
        self.english_patterns = {
            # Common English words / Từ tiếng Anh thường gặp
            'english_words': r'\b(i|me|my|you|your|he|him|his|she|her|we|us|our|they|them|their|am|is|are|was|were|have|has|had|do|does|did|will|would|could|should|can|may|might|the|a|an|and|or|but|if|when|where|what|why|how|who|which|that|this|these|those)\b',
            
            # English banking/finance terms / Thuật ngữ ngân hàng/tài chính tiếng Anh
            'english_finance': r'\b(loan|credit|bank|banking|interest|rate|income|salary|mortgage|insurance|investment|savings|account|transaction|transfer|withdraw|deposit|money|cash|payment|debt|finance|financial)\b',
            
            # English question patterns / Mẫu câu hỏi tiếng Anh
            'english_questions': r'\b(what|who|where|when|why|how|which|whose|whom|can|could|would|should|do|does|did|is|are|was|were)\b',
            
            # English politeness / Lịch sự tiếng Anh
            'english_politeness': r'\b(hello|hi|please|thank|thanks|sorry|excuse|help|assist|support|welcome)\b'
        }
        
        # Weight for each pattern type / Trọng số cho từng loại pattern
        self.pattern_weights = {
            'vietnamese_chars': 3.0,      # Highest weight for Vietnamese characters
            'vietnamese_words': 2.0,
            'vietnamese_finance': 2.5,
            'vietnamese_questions': 1.5,
            'vietnamese_politeness': 1.0,
            'english_words': 1.5,
            'english_finance': 2.5,
            'english_questions': 1.5,
            'english_politeness': 1.0
        }
    
    def detect_language(self, text: str) -> LanguageDetectionResult:
        """
        Detect language from text with confidence score
        Phát hiện ngôn ngữ từ văn bản với điểm tin cậy
        """
        if not text or not text.strip():
            return LanguageDetectionResult(
                language=Language.VIETNAMESE,  # Default to Vietnamese
                confidence=0.5,
                indicators=["empty_text"]
            )
        
        text_lower = text.lower()
        vietnamese_score = 0.0
        english_score = 0.0
        found_indicators = []
        
        # Check Vietnamese patterns / Kiểm tra các pattern tiếng Việt
        for pattern_name, pattern in self.vietnamese_patterns.items():
            matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
            if matches > 0:
                weight = self.pattern_weights.get(pattern_name, 1.0)
                vietnamese_score += matches * weight
                found_indicators.append(f"vi_{pattern_name}:{matches}")
        
        # Check English patterns / Kiểm tra các pattern tiếng Anh
        for pattern_name, pattern in self.english_patterns.items():
            matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
            if matches > 0:
                weight = self.pattern_weights.get(pattern_name, 1.0)
                english_score += matches * weight
                found_indicators.append(f"en_{pattern_name}:{matches}")
        
        # Additional checks / Kiểm tra bổ sung
        
        # Check for Vietnamese tone marks / Kiểm tra dấu thanh tiếng Việt
        vietnamese_tone_count = len(re.findall(r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', text_lower))
        if vietnamese_tone_count > 0:
            vietnamese_score += vietnamese_tone_count * 3.0
            found_indicators.append(f"vi_tone_marks:{vietnamese_tone_count}")
        
        # Check for English-specific patterns / Kiểm tra pattern đặc trưng tiếng Anh
        english_contractions = len(re.findall(r"\b\w+[''](?:t|re|ll|ve|d|s|m)\b", text))
        if english_contractions > 0:
            english_score += english_contractions * 2.0
            found_indicators.append(f"en_contractions:{english_contractions}")
        
        # Check for numbers with currency / Kiểm tra số với đơn vị tiền tệ
        vnd_pattern = len(re.findall(r'\b\d+(?:[.,]\d+)?\s*(?:vnd|vnđ|đồng|triệu|tỷ)\b', text_lower))
        if vnd_pattern > 0:
            vietnamese_score += vnd_pattern * 2.0
            found_indicators.append(f"vi_currency:{vnd_pattern}")
        
        usd_pattern = len(re.findall(r'\b\d+(?:[.,]\d+)?\s*(?:usd|dollar|cents?)\b', text_lower))
        if usd_pattern > 0:
            english_score += usd_pattern * 2.0
            found_indicators.append(f"en_currency:{usd_pattern}")
        
        # Determine language and confidence / Xác định ngôn ngữ và độ tin cậy
        total_score = vietnamese_score + english_score
        
        if total_score == 0:
            # No clear indicators, default to Vietnamese / Không có dấu hiệu rõ ràng, mặc định tiếng Việt
            return LanguageDetectionResult(
                language=Language.VIETNAMESE,
                confidence=0.5,
                indicators=["no_clear_indicators"]
            )
        
        if vietnamese_score > english_score:
            confidence = min(vietnamese_score / total_score, 0.95)
            return LanguageDetectionResult(
                language=Language.VIETNAMESE,
                confidence=confidence,
                indicators=found_indicators
            )
        else:
            confidence = min(english_score / total_score, 0.95)
            return LanguageDetectionResult(
                language=Language.ENGLISH,
                confidence=confidence,
                indicators=found_indicators
            )
    
    def get_response_language(self, user_language: Language, detected_language: Language) -> Language:
        """
        Determine response language based on user preference and detection
        Xác định ngôn ngữ phản hồi dựa trên ưa thích người dùng và phát hiện
        """
        if user_language == Language.AUTO_DETECT:
            return detected_language
        else:
            return user_language
    
    def validate_language_consistency(self, conversation_history: List[Dict[str, str]]) -> Dict[str, any]:
        """
        Validate language consistency in conversation
        Kiểm tra tính nhất quán ngôn ngữ trong hội thoại
        """
        if not conversation_history:
            return {"consistent": True, "primary_language": Language.VIETNAMESE}
        
        language_counts = {Language.VIETNAMESE: 0, Language.ENGLISH: 0}
        
        for message in conversation_history[-5:]:  # Check last 5 messages
            content = message.get("content", "")
            if content:
                detection = self.detect_language(content)
                language_counts[detection.language] += 1
        
        primary_language = max(language_counts, key=language_counts.get)
        total_messages = sum(language_counts.values())
        consistency_ratio = language_counts[primary_language] / total_messages if total_messages > 0 else 1.0
        
        return {
            "consistent": consistency_ratio >= 0.7,  # 70% consistency threshold
            "primary_language": primary_language,
            "consistency_ratio": consistency_ratio,
            "language_distribution": language_counts
        }

# Create global instance / Tạo instance toàn cục
language_detector = LanguageDetector()
