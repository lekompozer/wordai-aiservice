"""
Intent Detection Service using DeepSeek AI
Dịch vụ phát hiện ý định sử dụng DeepSeek AI với hỗ trợ đa ngôn ngữ
"""

import json
import re
from typing import Dict, Any, Optional, List
from src.models.unified_models import (
    ChatIntent,
    Language,
    IntentDetectionResult,
    Industry,
    ConversationHistory,
)
from src.services.language_detector import language_detector
from src.providers.ai_provider_manager import AIProviderManager


class IntentDetector:
    """
    Advanced intent detection with multi-language support
    Phát hiện ý định nâng cao với hỗ trợ đa ngôn ngữ
    """

    def __init__(self):
        # Initialize AI provider / Khởi tạo AI provider
        from src.core.config import APP_CONFIG

        self.ai_manager = AIProviderManager(
            deepseek_api_key=APP_CONFIG.get("deepseek_api_key"),
            chatgpt_api_key=APP_CONFIG.get("chatgpt_api_key"),
            gemini_api_key=APP_CONFIG.get("gemini_api_key"),
            cerebras_api_key=APP_CONFIG.get("cerebras_api_key"),
        )

        # Industry-specific intent patterns / Patterns ý định theo ngành
        self.industry_patterns = {
            Industry.BANKING: {
                "sales_keywords_vi": [
                    "vay",
                    "vay vốn",
                    "vay tiền",
                    "cần vay",
                    "muốn vay",
                    "xin vay",
                    "thẩm định",
                    "đánh giá",
                    "ước tính",
                    "thẩm định khoản vay",
                    "hồ sơ vay",
                    "làm hồ sơ",
                    "nộp hồ sơ",
                    "đăng ký vay",
                    "lãi suất bao nhiêu",
                    "vay được bao nhiêu",
                    "điều kiện vay",
                ],
                "sales_keywords_en": [
                    "loan",
                    "borrow",
                    "credit",
                    "apply",
                    "application",
                    "assessment",
                    "evaluate",
                    "qualify",
                    "loan application",
                    "interest rate",
                    "how much can",
                    "loan terms",
                ],
                "info_keywords_vi": [
                    "thông tin",
                    "tìm hiểu",
                    "cho biết",
                    "giải thích",
                    "lãi suất là",
                    "sản phẩm",
                    "dịch vụ",
                    "chi nhánh",
                    "ngân hàng",
                    "tư vấn",
                    "hỏi về",
                ],
                "info_keywords_en": [
                    "information",
                    "tell me about",
                    "what is",
                    "explain",
                    "interest rate",
                    "products",
                    "services",
                    "branch",
                    "bank",
                    "consult",
                    "ask about",
                ],
            },
            Industry.RESTAURANT: {
                "sales_keywords_vi": [
                    "đặt bàn",
                    "book",
                    "đặt chỗ",
                    "reservation",
                    "đặt trước",
                    "gọi món",
                    "order",
                    "đặt món",
                    "mang về",
                    "delivery",
                    "ship",
                    "giao hàng",
                    "takeaway",
                ],
                "sales_keywords_en": [
                    "book table",
                    "reservation",
                    "reserve",
                    "order",
                    "takeaway",
                    "delivery",
                    "dine in",
                ],
            },
            Industry.HOTEL: {
                "sales_keywords_vi": [
                    "đặt phòng",
                    "book room",
                    "có phòng",
                    "trống phòng",
                    "check in",
                    "check out",
                    "nghỉ",
                    "ở lại",
                ],
                "sales_keywords_en": [
                    "book room",
                    "reservation",
                    "available room",
                    "check in",
                    "check out",
                    "stay",
                ],
            },
        }

    async def detect_intent(
        self,
        message: str,
        industry: Industry = Industry.OTHER,
        company_id: str = "default",
        conversation_history: Optional[List[ConversationHistory]] = None,
        context: Optional[Dict[str, Any]] = None,
        provider: str = "deepseek",
    ) -> IntentDetectionResult:
        """
        Detect user intent with industry-specific context
        Phát hiện ý định người dùng với ngữ cảnh theo ngành
        """
        # Step 1: Detect language / Bước 1: Phát hiện ngôn ngữ
        language_result = language_detector.detect_language(message)
        detected_language = language_result.language

        # Step 2: Quick pattern-based detection / Bước 2: Phát hiện nhanh dựa trên pattern
        quick_intent = self._quick_pattern_detection(
            message, industry, detected_language
        )

        # Step 3: AI-based intent detection / Bước 3: Phát hiện ý định bằng AI
        ai_intent = await self._ai_intent_detection(
            message,
            industry,
            detected_language,
            conversation_history,
            context,
            provider,
        )

        # Step 4: Combine results / Bước 4: Kết hợp kết quả
        final_intent, confidence = self._combine_intent_results(quick_intent, ai_intent)

        return IntentDetectionResult(
            intent=final_intent,
            confidence=confidence,
            language=detected_language,
            extracted_info=ai_intent.get("extracted_info", {}),
            reasoning=ai_intent.get("reasoning", "Combined pattern and AI analysis"),
        )

    def _quick_pattern_detection(
        self, message: str, industry: Industry, language: Language
    ) -> Dict[str, Any]:
        """
        Quick pattern-based intent detection
        Phát hiện ý định nhanh dựa trên pattern
        """
        message_lower = message.lower()

        # Get industry patterns / Lấy patterns theo ngành
        patterns = self.industry_patterns.get(industry, {})

        # Check for sales intent / Kiểm tra ý định mua bán
        sales_keywords = []
        if language == Language.VIETNAMESE:
            sales_keywords = patterns.get("sales_keywords_vi", [])
        else:
            sales_keywords = patterns.get("sales_keywords_en", [])

        sales_matches = sum(1 for keyword in sales_keywords if keyword in message_lower)

        # Check for information intent / Kiểm tra ý định hỏi thông tin
        info_keywords = []
        if language == Language.VIETNAMESE:
            info_keywords = patterns.get("info_keywords_vi", [])
        else:
            info_keywords = patterns.get("info_keywords_en", [])

        info_matches = sum(1 for keyword in info_keywords if keyword in message_lower)

        # Quick decision / Quyết định nhanh
        if sales_matches > info_matches and sales_matches > 0:
            return {
                "intent": ChatIntent.SALES_INQUIRY,
                "confidence": min(0.8, 0.5 + (sales_matches * 0.1)),
                "method": "pattern_matching",
            }
        elif info_matches > 0:
            return {
                "intent": ChatIntent.INFORMATION,
                "confidence": min(0.7, 0.4 + (info_matches * 0.1)),
                "method": "pattern_matching",
            }
        else:
            return {
                "intent": ChatIntent.GENERAL_CHAT,
                "confidence": 0.3,
                "method": "pattern_matching",
            }

    async def _ai_intent_detection(
        self,
        message: str,
        industry: Industry,
        language: Language,
        conversation_history: Optional[List[ConversationHistory]] = None,
        context: Optional[Dict[str, Any]] = None,
        provider: str = "deepseek",
    ) -> Dict[str, Any]:
        """
        AI-powered intent detection using DeepSeek
        Phát hiện ý định bằng AI sử dụng DeepSeek
        """
        # Build conversation context / Xây dựng ngữ cảnh hội thoại
        history_context = ""
        if conversation_history:
            recent_messages = conversation_history[-3:]  # Last 3 messages
            history_context = "\n".join(
                [
                    f"{'User' if msg.role == 'user' else 'AI'}: {msg.content}"
                    for msg in recent_messages
                ]
            )

        # Build industry-specific prompt / Xây dựng prompt theo ngành
        industry_context = self._get_industry_context(industry, language)

        # Create bilingual prompt / Tạo prompt song ngữ
        if language == Language.VIETNAMESE:
            prompt = f"""
BẠN LÀ CHUYÊN GIA PHÂN TÍCH Ý ĐỊNH NGƯỜI DÙNG cho ngành {industry.value}.
Trả về chỉ một JSON hợp lệ, không có text khác.

LỊCH SỬ HỘI THOẠI GẦN ĐÂY:
{history_context if history_context else "Không có tin nhắn trước"}

TIN NHẮN HIỆN TẠI: "{message}"

NHIỆM VỤ: Phân tích ý định người dùng và phân loại vào một trong các loại sau:

1. INFORMATION (Hỏi thông tin):
   - Hỏi về thông tin công ty, lịch sử, địa chỉ, liên hệ
   - Chi tiết sản phẩm/dịch vụ, tính năng, đặc điểm
   - Thông tin giá cả (không có ý định mua)
   - Câu hỏi chung về dịch vụ

2. SALES_INQUIRY (Có nhu cầu mua/đặt):
   - Muốn mua, đặt hàng, đặt dịch vụ
   - Đặt chỗ, đặt bàn, đặt phòng
   - Bắt đầu hồ sơ vay/bảo hiểm
   - Yêu cầu báo giá với ý định mua
   - Thể hiện nhu cầu cụ thể

3. SUPPORT (Hỗ trợ):
   - Hỗ trợ đơn hàng/đặt chỗ hiện có
   - Vấn đề kỹ thuật
   - Khiếu nại hoặc vấn đề
   - Câu hỏi về tài khoản

4. GENERAL_CHAT (Trò chuyện thông thường):
   - Chào hỏi xã giao
   - Chào tạm biệt
   - Trò chuyện ngoài lề

{industry_context}

Trả về JSON:
{{
    "intent": "INFORMATION|SALES_INQUIRY|SUPPORT|GENERAL_CHAT",
    "confidence": 0.0-1.0,
    "reasoning": "Giải thích ngắn gọn tại sao chọn ý định này",
    "extracted_info": {{
        "product_interest": "nếu có đề cập",
        "service_type": "nếu áp dụng",
        "urgency": "immediate|future|exploring",
        "specific_needs": ["danh", "sách", "nhu cầu"],
        "needs_images": true/false,
        "image_query": "mô tả loại hình ảnh cần tìm nếu có"
    }}
}}

QUAN TRỌNG: 
1. Chú ý các tín hiệu mua hàng tinh tế. Ngay cả "cho biết về X" cũng có thể là SALES_INQUIRY nếu ngữ cảnh cho thấy có ý định mua.
2. Phát hiện yêu cầu hình ảnh: Nếu người dùng muốn "xem", "cho xem", "hình ảnh", "ảnh", "trông như thế nào", "không gian", "design", "mẫu", "model", v.v. thì đặt "needs_images": true và mô tả loại hình ảnh cần tìm.
"""
        else:
            prompt = f"""
YOU ARE AN INTENT ANALYSIS EXPERT for the {industry.value} industry.
Return only valid JSON, no other text.

RECENT CONVERSATION HISTORY:
{history_context if history_context else "No previous messages"}

CURRENT MESSAGE: "{message}"

TASK: Analyze the user's intent and categorize it into one of these categories:

1. INFORMATION - User is asking about:
   - Company information, history, location, contact
   - Product/service details, features, specifications
   - Pricing information (without intent to buy)
   - General questions about offerings

2. SALES_INQUIRY - User shows intent to:
   - Buy, purchase, order products
   - Book services, make reservations
   - Start a loan/insurance application
   - Request quotes with purchase intent
   - Express specific buying needs

3. SUPPORT - User needs help with:
   - Existing orders/bookings
   - Technical issues
   - Complaints or problems
   - Account-related questions

4. GENERAL_CHAT - User is:
   - Making small talk
   - Greeting or saying goodbye
   - Off-topic conversation

{industry_context}

Return JSON:
{{
    "intent": "INFORMATION|SALES_INQUIRY|SUPPORT|GENERAL_CHAT",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of why you chose this intent",
    "extracted_info": {{
        "product_interest": "if mentioned",
        "service_type": "if applicable",
        "urgency": "immediate|future|exploring",
        "specific_needs": ["list", "of", "needs"],
        "needs_images": true/false,
        "image_query": "description of images needed if any"
    }}
}}

IMPORTANT: 
1. Look for subtle buying signals. Even "tell me about X" could be SALES_INQUIRY if context suggests buying interest.
2. Detect image requests: If user wants to "see", "show me", "images", "photos", "how it looks", "space", "design", "sample", "model", etc. then set "needs_images": true and describe the type of images needed.
"""

        try:
            # Get AI response / Lấy phản hồi AI
            response = await self.ai_manager.get_response(
                question=prompt,
                session_id=f"intent_{industry.value}",
                user_id="intent_detection",
                provider=provider,
            )

            # Parse JSON response / Phân tích phản hồi JSON
            clean_response = self._clean_json_response(response)
            result_data = json.loads(clean_response)

            return {
                "intent": ChatIntent[result_data["intent"]],
                "confidence": float(result_data["confidence"]),
                "reasoning": result_data.get("reasoning", ""),
                "extracted_info": result_data.get("extracted_info", {}),
                "method": "ai_analysis",
            }

        except Exception as e:
            print(f"❌ AI intent detection error: {e}")
            # Fallback to general information / Fallback về thông tin chung
            return {
                "intent": ChatIntent.INFORMATION,
                "confidence": 0.5,
                "reasoning": f"AI analysis failed: {str(e)}",
                "extracted_info": {},
                "method": "ai_fallback",
            }

    def _get_industry_context(self, industry: Industry, language: Language) -> str:
        """
        Get industry-specific context for better intent detection
        Lấy ngữ cảnh theo ngành để phát hiện ý định tốt hơn
        """
        contexts = {
            Industry.BANKING: {
                Language.VIETNAMESE: """
Đối với ngành NGÂN HÀNG, chú ý đặc biệt:
- "Tôi cần vay" → SALES_INQUIRY
- "Lãi suất bao nhiêu?" → Có thể là INFORMATION hoặc SALES_INQUIRY tùy ngữ cảnh
- "Tôi muốn đăng ký" → SALES_INQUIRY
- "Cho biết về khoản vay" → INFORMATION trừ khi ngữ cảnh trước đó cho thấy ý định
- "Thẩm định giúp tôi" → SALES_INQUIRY
                """,
                Language.ENGLISH: """
For BANKING industry, pay special attention:
- "I need a loan" → SALES_INQUIRY
- "What are interest rates?" → Could be INFORMATION or SALES_INQUIRY depending on context
- "I want to apply" → SALES_INQUIRY
- "Tell me about loans" → INFORMATION unless previous context shows intent
- "Assess my application" → SALES_INQUIRY
                """,
            },
            Industry.RESTAURANT: {
                Language.VIETNAMESE: """
Đối với ngành NHÀ HÀNG, chú ý:
- "Đặt bàn" → SALES_INQUIRY
- "Menu có gì?" → INFORMATION trừ khi theo sau là ý định đặt món
- "Tôi muốn gọi món" → SALES_INQUIRY
- "Có giao hàng không?" → Có thể là cả hai tùy ngữ cảnh
                """,
                Language.ENGLISH: """
For RESTAURANT industry, note:
- "Book a table" → SALES_INQUIRY
- "What's on the menu?" → INFORMATION unless followed by ordering intent
- "I'd like to order" → SALES_INQUIRY
- "Do you deliver?" → Could be either depending on context
                """,
            },
        }

        return contexts.get(industry, {}).get(
            language, "No specific industry context available."
        )

    def _clean_json_response(self, response: str) -> str:
        """
        Clean AI response to extract valid JSON
        Làm sạch phản hồi AI để trích xuất JSON hợp lệ
        """
        # Remove markdown formatting / Loại bỏ định dạng markdown
        response = re.sub(r"```json\s*", "", response)
        response = re.sub(r"```\s*$", "", response)

        # Find JSON object / Tìm object JSON
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            return json_match.group(0)

        return response

    def _combine_intent_results(
        self, pattern_result: Dict[str, Any], ai_result: Dict[str, Any]
    ) -> tuple[ChatIntent, float]:
        """
        Combine pattern-based and AI-based intent detection results
        Kết hợp kết quả phát hiện ý định dựa trên pattern và AI
        """
        pattern_intent = pattern_result["intent"]
        pattern_confidence = pattern_result["confidence"]

        ai_intent = ai_result["intent"]
        ai_confidence = ai_result["confidence"]

        # If both agree and confidence is high, use that / Nếu cả hai đồng ý và độ tin cậy cao
        if pattern_intent == ai_intent:
            combined_confidence = min(
                0.95, (pattern_confidence + ai_confidence) / 2 + 0.1
            )
            return pattern_intent, combined_confidence

        # If AI has higher confidence, trust AI / Nếu AI có độ tin cậy cao hơn
        if ai_confidence > pattern_confidence + 0.2:
            return ai_intent, ai_confidence

        # If pattern matching found strong signals, trust it / Nếu pattern matching tìm thấy tín hiệu mạnh
        if pattern_confidence > 0.7:
            return pattern_intent, pattern_confidence

        # Default to AI result / Mặc định theo kết quả AI
        return ai_intent, max(0.5, ai_confidence)


# Create global instance / Tạo instance toàn cục
intent_detector = IntentDetector()
