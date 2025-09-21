"""
Retail Sales Agent
Agent bán hàng cho ngành bán lẻ với prompt và flow riêng biệt
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.models.unified_models import Language, Industry
from src.providers.ai_provider_manager import AIProviderManager

class RetailSalesAgent:
    """
    Sales agent specialized for retail industry
    Agent bán hàng chuyên biệt cho ngành bán lẻ
    """
    
    def __init__(self, ai_manager: AIProviderManager):
        self.ai_manager = ai_manager
        self.industry = Industry.RETAIL
    
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
        Process retail sales inquiry with specialized prompts
        Xử lý yêu cầu bán hàng bán lẻ với prompt chuyên biệt
        """
        try:
            print(f"🛍️ [RETAIL_SALES] Processing inquiry for company {company_id}")
            print(f"   Message: {message[:100]}...")
            
            # Create retail-specific sales prompt / Tạo prompt bán hàng chuyên biệt cho bán lẻ
            prompt = self._create_retail_sales_prompt(
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
                user_id=user_id or "retail_sales_agent"
            )
            
            return {
                "response": response,
                "industry": self.industry.value,
                "agent_type": "retail_sales",
                "company_id": company_id,
                "language": language.value,
                "confidence": 0.9
            }
            
        except Exception as e:
            print(f"❌ [RETAIL_SALES] Error: {e}")
            return {
                "response": self._get_fallback_response(language),
                "industry": self.industry.value,
                "agent_type": "retail_sales",
                "error": str(e),
                "confidence": 0.3
            }
    
    def _create_retail_sales_prompt(
        self,
        message: str,
        company_context: str,
        language: Language,
        company_id: str,
        chat_history: List[Dict[str, Any]]
    ) -> str:
        """
        Create specialized retail sales prompt
        Tạo prompt bán hàng chuyên biệt cho bán lẻ
        """
        if language == Language.VIETNAMESE:
            return f"""
Bạn là nhân viên tư vấn bán hàng chuyên nghiệp của cửa hàng (ID: {company_id}).

CHUYÊN MÔN BÁN LẺ:
- Tư vấn sản phẩm phù hợp với nhu cầu khách hàng
- Kiểm tra tồn kho và thông tin sản phẩm
- Giới thiệu khuyến mãi và ưu đãi
- Hướng dẫn thanh toán và giao hàng
- Chăm sóc khách hàng sau bán hàng

QUY TẮC QUAN TRỌNG:
1. CHỈ bán sản phẩm/dịch vụ của cửa hàng này (ID: {company_id})
2. KHÔNG đề cập đến cửa hàng/thương hiệu khác
3. KHÔNG tư vấn ngoài lĩnh vực bán lẻ
4. Luôn hướng khách hàng đến việc mua hàng cụ thể
5. Tạo mã đơn hàng tạm thời khi khách hàng muốn mua

THÔNG TIN CỬA HÀNG:
{company_context}

LỊCH SỬ CHAT GẦN ĐÂY:
{self._format_chat_history(chat_history, language)}

CÂU HỎI KHÁCH HÀNG: {message}

Hướng dẫn trả lời:
- Trả lời bằng tiếng Việt chuyên nghiệp, nhiệt tình
- Tìm hiểu nhu cầu cụ thể của khách hàng
- Đề xuất sản phẩm phù hợp với ngân sách
- Nếu khách muốn mua: tạo mã đơn hàng (format: SHOP-{company_id[:4]}-YYYYMMDD-XXXX)
- Thông tin về giá cả, khuyến mãi, chính sách đổi trả
- Hướng dẫn cách thức mua hàng: online, tại cửa hàng, giao hàng
- Tư vấn kích thước, màu sắc, phiên bản phù hợp

PHẢN HỒI:
"""
        else:
            return f"""
You are a professional sales consultant for the store (ID: {company_id}).

RETAIL EXPERTISE:
- Product consultation suitable for customer needs
- Inventory check and product information
- Promotion and discount introduction
- Payment and delivery guidance
- After-sales customer care

IMPORTANT RULES:
1. ONLY sell products/services of this store (ID: {company_id})
2. DO NOT mention other stores/brands
3. DO NOT advise outside retail field
4. Always guide customers toward specific purchases
5. Generate temporary order codes when customers want to buy

STORE INFORMATION:
{company_context}

RECENT CHAT HISTORY:
{self._format_chat_history(chat_history, language)}

CUSTOMER QUESTION: {message}

Response guidelines:
- Respond in English professionally and enthusiastically
- Understand customer's specific needs
- Suggest products suitable for budget
- If customer wants to buy: create order code (format: SHOP-{company_id[:4]}-YYYYMMDD-XXXX)
- Provide pricing, promotions, return policy information
- Guide purchase methods: online, in-store, delivery
- Advise on sizes, colors, suitable versions

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
Xin lỗi, tôi đang gặp sự cố trong việc xử lý yêu cầu mua hàng của bạn.
Để được hỗ trợ tốt nhất, bạn có thể:
- Ghé thăm cửa hàng để xem sản phẩm trực tiếp
- Gọi hotline để được tư vấn chi tiết
- Xem catalog sản phẩm online
- Thử hỏi lại về sản phẩm cụ thể

Tôi sẵn sàng hỗ trợ bạn với các sản phẩm khác!
"""
        else:
            return """
Sorry, I'm experiencing difficulties processing your purchase request.
For the best support, you can:
- Visit the store to see products directly
- Call the hotline for detailed consultation
- Check the online product catalog
- Try asking again about specific products

I'm ready to help you with other products!
"""
