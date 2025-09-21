"""
Hotel Sales Agent
Agent bán hàng cho ngành khách sạn với prompt và flow riêng biệt
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.models.unified_models import Language, Industry
from src.providers.ai_provider_manager import AIProviderManager

class HotelSalesAgent:
    """
    Sales agent specialized for hotel industry
    Agent bán hàng chuyên biệt cho ngành khách sạn
    """
    
    def __init__(self, ai_manager: AIProviderManager):
        self.ai_manager = ai_manager
        self.industry = Industry.HOTEL
    
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
        Process hotel sales inquiry with specialized prompts
        Xử lý yêu cầu bán hàng khách sạn với prompt chuyên biệt
        """
        try:
            print(f"🏨 [HOTEL_SALES] Processing inquiry for company {company_id}")
            print(f"   Message: {message[:100]}...")
            
            # Create hotel-specific sales prompt / Tạo prompt bán hàng chuyên biệt cho khách sạn
            prompt = self._create_hotel_sales_prompt(
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
                user_id=user_id or "hotel_sales_agent"
            )
            
            return {
                "response": response,
                "industry": self.industry.value,
                "agent_type": "hotel_sales",
                "company_id": company_id,
                "language": language.value,
                "confidence": 0.9
            }
            
        except Exception as e:
            print(f"❌ [HOTEL_SALES] Error: {e}")
            return {
                "response": self._get_fallback_response(language),
                "industry": self.industry.value,
                "agent_type": "hotel_sales",
                "error": str(e),
                "confidence": 0.3
            }
    
    def _create_hotel_sales_prompt(
        self,
        message: str,
        company_context: str,
        language: Language,
        company_id: str,
        chat_history: List[Dict[str, Any]]
    ) -> str:
        """
        Create specialized hotel sales prompt
        Tạo prompt bán hàng chuyên biệt cho khách sạn
        """
        if language == Language.VIETNAMESE:
            return f"""
Bạn là nhân viên tư vấn đặt phòng chuyên nghiệp của khách sạn (ID: {company_id}).

CHUYÊN MÔN KHÁCH SẠN:
- Tư vấn loại phòng phù hợp với nhu cầu
- Báo giá và gói ưu đãi đặc biệt
- Đặt phòng và quản lý booking
- Dịch vụ tiện ích: spa, nhà hàng, hội nghị
- Tư vấn tour và hoạt động địa phương

QUY TẮC QUAN TRỌNG:
1. CHỈ đặt phòng/dịch vụ của khách sạn này (ID: {company_id})
2. KHÔNG đề cập đến khách sạn khác
3. KHÔNG tư vấn ngoài lĩnh vực khách sạn/du lịch
4. Luôn hướng khách hàng đến việc đặt phòng cụ thể
5. Tạo mã đặt phòng tạm thời khi khách hàng muốn book

THÔNG TIN KHÁCH SẠN:
{company_context}

LỊCH SỬ CHAT GẦN ĐÂY:
{self._format_chat_history(chat_history, language)}

CÂU HỎI KHÁCH HÀNG: {message}

Hướng dẫn trả lời:
- Trả lời bằng tiếng Việt chuyên nghiệp, thân thiện
- Tìm hiểu lịch trình và nhu cầu lưu trú
- Đề xuất loại phòng và gói dịch vụ phù hợp
- Nếu khách muốn đặt: tạo mã booking (format: HOTEL-{company_id[:4]}-YYYYMMDD-XXXX)
- Thông tin về tiện ích, chính sách, giờ check-in/out
- Tư vấn điểm tham quan và hoạt động xung quanh
- Giải thích các loại phòng, view, giá cả chi tiết

PHẢN HỒI:
"""
        else:
            return f"""
You are a professional room booking consultant for the hotel (ID: {company_id}).

HOTEL EXPERTISE:
- Room type consultation suitable for needs
- Pricing and special package offers
- Room booking and reservation management
- Amenity services: spa, restaurant, conference
- Local tour and activity consultation

IMPORTANT RULES:
1. ONLY book rooms/services of this hotel (ID: {company_id})
2. DO NOT mention other hotels
3. DO NOT advise outside hotel/travel field
4. Always guide customers toward specific bookings
5. Generate temporary booking codes when customers want to book

HOTEL INFORMATION:
{company_context}

RECENT CHAT HISTORY:
{self._format_chat_history(chat_history, language)}

CUSTOMER QUESTION: {message}

Response guidelines:
- Respond in English professionally and friendly
- Understand itinerary and accommodation needs
- Suggest suitable room types and service packages
- If customer wants to book: create booking code (format: HOTEL-{company_id[:4]}-YYYYMMDD-XXXX)
- Provide amenity information, policies, check-in/out times
- Advise on nearby attractions and activities
- Explain room types, views, detailed pricing

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
Xin lỗi, tôi đang gặp sự cố trong việc xử lý yêu cầu đặt phòng của bạn.
Để được hỗ trợ tốt nhất, bạn có thể:
- Gọi trực tiếp đến lễ tân khách sạn
- Truy cập website chính thức để xem phòng trống
- Email đến bộ phận đặt phòng
- Thử hỏi lại với thông tin cụ thể hơn

Tôi sẵn sàng hỗ trợ bạn với các dịch vụ khác của khách sạn!
"""
        else:
            return """
Sorry, I'm experiencing difficulties processing your room booking request.
For the best support, you can:
- Call the hotel reception directly
- Visit the official website to check availability
- Email the reservations department
- Try asking again with more specific information

I'm ready to help you with other hotel services!
"""
