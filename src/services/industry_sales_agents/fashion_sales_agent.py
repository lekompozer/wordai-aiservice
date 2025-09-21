"""
Fashion Sales Agent
Agent bán hàng chuyên biệt cho ngành Thời trang
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.models.unified_models import Language
from src.providers.ai_provider_manager import AIProviderManager

class FashionSalesAgent:
    """
    Specialized fashion sales agent
    Agent bán hàng chuyên biệt cho ngành thời trang
    """
    
    def __init__(self, ai_manager: AIProviderManager):
        self.ai_manager = ai_manager
    
    async def process_sales_inquiry(
        self,
        message: str,
        company_id: str,
        session_id: str,
        language: Language,
        company_context: str,
        chat_history: List[Dict[str, Any]] = None,
        user_id: str = None
    ) -> Dict[str, Any]:
        """
        Process fashion consultation inquiry
        Xử lý yêu cầu tư vấn thời trang
        """
        try:
            print(f"👗 [FASHION_SALES] Processing fashion inquiry for company {company_id}")
            print(f"   Message: {message[:100]}...")
            
            # Create specialized fashion prompt / Tạo prompt chuyên biệt thời trang
            prompt = self._create_fashion_consultation_prompt(
                message=message,
                company_context=company_context,
                language=language,
                company_id=company_id,
                chat_history=chat_history or []
            )
            
            # Get AI response / Lấy phản hồi AI
            response = await self.ai_manager.get_response(
                question=prompt,
                session_id=session_id,
                user_id=user_id or "fashion_sales_agent"
            )
            
            # Generate styling code if customer shows interest / Tạo mã styling nếu khách quan tâm
            styling_code = None
            if self._detect_purchase_intent(message, language):
                styling_code = self._generate_styling_code(company_id)
            
            return {
                "response": response,
                "industry": "fashion",
                "agent_type": "fashion_sales",
                "company_id": company_id,
                "language": language.value,
                "styling_code": styling_code,
                "confidence": 0.95
            }
            
        except Exception as e:
            print(f"❌ [FASHION_SALES] Error: {e}")
            return {
                "response": self._get_fallback_response(language),
                "industry": "fashion",
                "agent_type": "fashion_sales",
                "error": str(e),
                "confidence": 0.3
            }
    
    def _create_fashion_consultation_prompt(
        self,
        message: str,
        company_context: str,
        language: Language,
        company_id: str,
        chat_history: List[Dict[str, Any]]
    ) -> str:
        """
        Create specialized fashion consultation prompt
        Tạo prompt tư vấn thời trang chuyên biệt
        """
        if language == Language.VIETNAMESE:
            return f"""
Bạn là stylist và tư vấn viên thời trang chuyên nghiệp của công ty (ID: {company_id}).

CHUYÊN MÔN THỜI TRANG:
- Tư vấn phong cách cá nhân và xu hướng thời trang mới nhất
- Phối đồ phù hợp với dáng người, tính cách và hoàn cảnh
- Tư vấn trang phục theo sự kiện: công sở, dạ tiệc, casual, thể thao
- Kết hợp trang phục và phụ kiện một cách tinh tế
- Chăm sóc khách hàng VIP và dịch vụ stylist cá nhân
- Tư vấn màu sắc và chất liệu phù hợp với từng mùa

QUY TẮC QUAN TRỌNG:
1. CHỈ tư vấn và bán sản phẩm thời trang của công ty này (ID: {company_id})
2. KHÔNG đề cập đến thương hiệu thời trang khác
3. Luôn phân tích phong cách và nhu cầu cá nhân của khách hàng
4. Đưa ra gợi ý cụ thể về trang phục và cách phối đồ
5. Tạo mã styling khi khách hàng quan tâm đến dịch vụ tư vấn

THÔNG TIN CÔNG TY:
{company_context}

LỊCH SỬ CHAT GẦN ĐÂY:
{self._format_chat_history(chat_history, language)}

CÂU HỎI KHÁCH HÀNG: {message}

Hướng dẫn trả lời:
- Trả lời bằng tiếng Việt thân thiện, chuyên nghiệp
- Phân tích phong cách và nhu cầu thời trang của khách hàng
- Gợi ý trang phục cụ thể phù hợp với dáng người và sự kiện
- Tư vấn cách phối màu, chất liệu và phụ kiện
- Nếu khách quan tâm: tạo mã styling (format: FASH-{company_id[:4]}-YYYYMMDD-XXXX)
- Hướng dẫn bước tiếp theo: thử đồ, tư vấn trực tiếp hoặc đặt hàng
- Nhấn mạnh phong cách độc đáo và sự tự tin của khách hàng

PHẢN HỒI:
"""
        else:
            return f"""
You are a professional stylist and fashion consultant for the company (ID: {company_id}).

FASHION EXPERTISE:
- Personal style consultation and latest fashion trends
- Outfit coordination suitable for body type, personality, and occasion
- Clothing advice for various events: office, evening, casual, sports
- Elegant combination of clothing and accessories
- VIP customer care and personal stylist services
- Color and fabric consultation suitable for each season

IMPORTANT RULES:
1. ONLY advise and sell fashion products of this company (ID: {company_id})
2. DO NOT mention other fashion brands
3. Always analyze customer's personal style and needs
4. Provide specific outfit suggestions and styling tips
5. Generate styling code when customers show interest in consultation services

COMPANY INFORMATION:
{company_context}

RECENT CHAT HISTORY:
{self._format_chat_history(chat_history, language)}

CUSTOMER QUESTION: {message}

Response guidelines:
- Respond in English friendly and professionally
- Analyze customer's fashion style and needs
- Suggest specific outfits suitable for body type and occasions
- Advise on color coordination, fabrics, and accessories
- If customer interested: create styling code (format: FASH-{company_id[:4]}-YYYYMMDD-XXXX)
- Guide next steps: try-on, direct consultation, or ordering
- Emphasize unique style and customer confidence

RESPONSE:
"""
    
    def _detect_purchase_intent(self, message: str, language: Language) -> bool:
        """Detect if customer shows purchase intent / Phát hiện ý định mua của khách hàng"""
        if language == Language.VIETNAMESE:
            intent_keywords = [
                "muốn mua", "tư vấn", "thử đồ", "có không", "giá", "size",
                "phối đồ", "stylist", "trang phục", "váy", "áo", "quần",
                "phụ kiện", "túi xách", "giày", "đồ", "mặc gì"
            ]
        else:
            intent_keywords = [
                "want to buy", "need", "looking for", "price", "size",
                "outfit", "dress", "shirt", "pants", "accessories",
                "bag", "shoes", "styling", "fashion", "wear", "clothing"
            ]
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in intent_keywords)
    
    def _generate_styling_code(self, company_id: str) -> str:
        """Generate fashion styling code / Tạo mã styling thời trang"""
        timestamp = datetime.now().strftime("%Y%m%d")
        import random
        random_num = random.randint(1000, 9999)
        return f"FASH-{company_id[:4].upper()}-{timestamp}-{random_num}"
    
    def _format_chat_history(self, chat_history: List[Dict[str, Any]], language: Language) -> str:
        """Format chat history for prompt / Định dạng lịch sử chat cho prompt"""
        if not chat_history:
            return "Không có lịch sử chat" if language == Language.VIETNAMESE else "No chat history"
        
        formatted = []
        for i, msg in enumerate(chat_history[-3:], 1):  # Last 3 messages
            role = msg.get('role', 'user')
            content = msg.get('content', '')[:100]
            formatted.append(f"{i}. {role}: {content}")
        
        return "\n".join(formatted)
    
    def _get_fallback_response(self, language: Language) -> str:
        """Get fallback response for errors / Lấy phản hồi dự phòng khi lỗi"""
        if language == Language.VIETNAMESE:
            return """
Xin lỗi, tôi đang gặp sự cố trong việc xử lý yêu cầu tư vấn thời trang của bạn.
Để được hỗ trợ tốt nhất, bạn có thể:
- Liên hệ trực tiếp với stylist của chúng tôi
- Ghé thăm showroom để được tư vấn và thử đồ trực tiếp
- Gửi ảnh và thông tin về sở thích phong cách
- Thử hỏi lại với thông tin cụ thể hơn về loại trang phục

Tôi sẵn sàng hỗ trợ bạn tìm kiếm phong cách hoàn hảo!
"""
        else:
            return """
Sorry, I'm experiencing difficulties processing your fashion consultation request.
For the best support, you can:
- Contact our stylist directly
- Visit our showroom for direct consultation and try-on
- Send photos and information about your style preferences
- Try asking again with more specific clothing type information

I'm ready to help you find the perfect style!
"""
