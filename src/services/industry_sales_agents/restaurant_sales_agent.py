"""
Restaurant Sales Agent
Agent bán hàng cho ngành nhà hàng với prompt và flow riêng biệt
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.models.unified_models import Language, Industry
from src.providers.ai_provider_manager import AIProviderManager

class RestaurantSalesAgent:
    """
    Sales agent specialized for restaurant industry
    Agent bán hàng chuyên biệt cho ngành nhà hàng
    """
    
    def __init__(self, ai_manager: AIProviderManager):
        self.ai_manager = ai_manager
        self.industry = Industry.RESTAURANT
    
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
        Process restaurant sales inquiry with specialized prompts
        Xử lý yêu cầu bán hàng nhà hàng với prompt chuyên biệt
        """
        try:
            print(f"🍽️ [RESTAURANT_SALES] Processing inquiry for company {company_id}")
            print(f"   Message: {message[:100]}...")
            
            # Create restaurant-specific sales prompt / Tạo prompt bán hàng chuyên biệt cho nhà hàng
            prompt = self._create_restaurant_sales_prompt(
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
                user_id=user_id or "restaurant_sales_agent"
            )
            
            return {
                "response": response,
                "industry": self.industry.value,
                "agent_type": "restaurant_sales",
                "company_id": company_id,
                "language": language.value,
                "confidence": 0.9
            }
            
        except Exception as e:
            print(f"❌ [RESTAURANT_SALES] Error: {e}")
            return {
                "response": self._get_fallback_response(language),
                "industry": self.industry.value,
                "agent_type": "restaurant_sales",
                "error": str(e),
                "confidence": 0.3
            }
    
    def _create_restaurant_sales_prompt(
        self,
        message: str,
        company_context: str,
        language: Language,
        company_id: str,
        chat_history: List[Dict[str, Any]]
    ) -> str:
        """
        Create specialized restaurant sales prompt
        Tạo prompt bán hàng chuyên biệt cho nhà hàng
        """
        if language == Language.VIETNAMESE:
            return f"""
Bạn là nhân viên phục vụ chuyên nghiệp của nhà hàng (ID: {company_id}).

CHUYÊN MÔN NHÀ HÀNG:
- Tư vấn thực đơn và món ăn đặc sắc
- Đặt bàn và sắp xếp chỗ ngồi
- Đặt món trước và giao hàng
- Tổ chức tiệc và sự kiện
- Combo và ưu đãi đặc biệt

QUY TẮC QUAN TRỌNG:
1. CHỈ giới thiệu món ăn/dịch vụ của nhà hàng này (ID: {company_id})
2. KHÔNG đề cập đến nhà hàng khác
3. KHÔNG tư vấn ngoài lĩnh vực ẩm thực/nhà hàng
4. Luôn hướng khách hàng đến việc đặt bàn hoặc gọi món
5. Tạo mã đặt bàn tạm thời khi khách hàng muốn đặt

THÔNG TIN NHÀ HÀNG:
{company_context}

LỊCH SỬ CHAT GẦN ĐÂY:
{self._format_chat_history(chat_history, language)}

CÂU HỎI KHÁCH HÀNG: {message}

Hướng dẫn trả lời:
- Trả lời bằng tiếng Việt thân thiện, nhiệt tình
- Giới thiệu món ăn với mô tả hấp dẫn
- Tư vấn combo phù hợp với nhu cầu và ngân sách
- Nếu khách muốn đặt bàn: tạo mã đặt bàn (format: REST-{company_id[:4]}-YYYYMMDD-XXXX)
- Hỏi về số người, thời gian, yêu cầu đặc biệt
- Gợi ý món ăn theo mùa hoặc đặc sản của nhà hàng
- Thông tin về giờ mở cửa, địa chỉ, liên hệ

PHẢN HỒI:
"""
        else:
            return f"""
You are a professional service staff member of the restaurant (ID: {company_id}).

RESTAURANT EXPERTISE:
- Menu consultation and specialty dishes
- Table reservations and seating arrangements
- Pre-ordering and delivery services
- Party and event organization
- Combo deals and special offers

IMPORTANT RULES:
1. ONLY introduce dishes/services of this restaurant (ID: {company_id})
2. DO NOT mention other restaurants
3. DO NOT advise outside food/restaurant field
4. Always guide customers toward table booking or ordering
5. Generate temporary booking codes when customers want to reserve

RESTAURANT INFORMATION:
{company_context}

RECENT CHAT HISTORY:
{self._format_chat_history(chat_history, language)}

CUSTOMER QUESTION: {message}

Response guidelines:
- Respond in English friendly and enthusiastic
- Introduce dishes with appealing descriptions
- Suggest combos suitable for needs and budget
- If customer wants to book: create booking code (format: REST-{company_id[:4]}-YYYYMMDD-XXXX)
- Ask about number of people, time, special requirements
- Suggest seasonal dishes or restaurant specialties
- Provide opening hours, address, contact information

RESPONSE:
"""
    
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
Xin lỗi, tôi đang gặp sự cố trong việc xử lý yêu cầu đặt bàn của bạn.
Để được phục vụ tốt nhất, bạn có thể:
- Gọi trực tiếp đến số hotline của nhà hàng
- Ghé thăm nhà hàng để được tư vấn thực đơn
- Xem thực đơn online trên website
- Thử hỏi lại về món ăn cụ thể

Tôi sẵn sàng hỗ trợ bạn với các câu hỏi về thực đơn khác!
"""
        else:
            return """
Sorry, I'm experiencing difficulties processing your reservation request.
For the best service, you can:
- Call the restaurant hotline directly
- Visit the restaurant for menu consultation
- Check the online menu on our website
- Try asking again about specific dishes

I'm ready to help you with other menu questions!
"""
