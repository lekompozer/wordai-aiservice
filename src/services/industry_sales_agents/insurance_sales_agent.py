"""
Insurance Sales Agent
Agent bán hàng chuyên biệt cho ngành Bảo hiểm
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.models.unified_models import Language
from src.providers.ai_provider_manager import AIProviderManager

class InsuranceSalesAgent:
    """
    Specialized insurance sales agent
    Agent bán hàng chuyên biệt cho ngành bảo hiểm
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
        Process insurance consultation inquiry
        Xử lý yêu cầu tư vấn bảo hiểm
        """
        try:
            print(f"🛡️ [INSURANCE_SALES] Processing insurance inquiry for company {company_id}")
            print(f"   Message: {message[:100]}...")
            
            # Create specialized insurance prompt / Tạo prompt chuyên biệt bảo hiểm
            prompt = self._create_insurance_consultation_prompt(
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
                user_id=user_id or "insurance_sales_agent"
            )
            
            # Generate consultation code if customer shows interest / Tạo mã tư vấn nếu khách quan tâm
            consultation_code = None
            if self._detect_purchase_intent(message, language):
                consultation_code = self._generate_consultation_code(company_id)
            
            return {
                "response": response,
                "industry": "insurance",
                "agent_type": "insurance_sales",
                "company_id": company_id,
                "language": language.value,
                "consultation_code": consultation_code,
                "confidence": 0.95
            }
            
        except Exception as e:
            print(f"❌ [INSURANCE_SALES] Error: {e}")
            return {
                "response": self._get_fallback_response(language),
                "industry": "insurance",
                "agent_type": "insurance_sales",
                "error": str(e),
                "confidence": 0.3
            }
    
    def _create_insurance_consultation_prompt(
        self,
        message: str,
        company_context: str,
        language: Language,
        company_id: str,
        chat_history: List[Dict[str, Any]]
    ) -> str:
        """
        Create specialized insurance consultation prompt
        Tạo prompt tư vấn bảo hiểm chuyên biệt
        """
        if language == Language.VIETNAMESE:
            return f"""
Bạn là chuyên viên tư vấn bảo hiểm chuyên nghiệp của công ty (ID: {company_id}).

CHUYÊN MÔN BẢO HIỂM:
- Tư vấn các loại bảo hiểm: nhân thọ, sức khỏe, xe cộ, tài sản, du lịch
- Phân tích rủi ro và tính toán phí bảo hiểm phù hợp
- Hướng dẫn quy trình đăng ký và thủ tục bồi thường
- Tư vấn kế hoạch bảo vệ tài chính dài hạn
- Hỗ trợ gia hạn và điều chỉnh hợp đồng bảo hiểm

QUY TẮC QUAN TRỌNG:
1. CHỈ tư vấn sản phẩm bảo hiểm của công ty này (ID: {company_id})
2. KHÔNG đề cập đến công ty bảo hiểm khác
3. Luôn phân tích nhu cầu bảo vệ cụ thể của khách hàng
4. Giải thích rõ ràng về quyền lợi và điều kiện bảo hiểm
5. Tạo mã tư vấn khi khách hàng quan tâm đến sản phẩm cụ thể

THÔNG TIN CÔNG TY:
{company_context}

LỊCH SỬ CHAT GẦN ĐÂY:
{self._format_chat_history(chat_history, language)}

CÂU HỎI KHÁCH HÀNG: {message}

Hướng dẫn trả lời:
- Trả lời bằng tiếng Việt chuyên nghiệp, dễ hiểu
- Phân tích nhu cầu bảo vệ của khách hàng (gia đình, tài sản, sức khỏe)
- Giới thiệu gói bảo hiểm phù hợp với tình hình tài chính
- Giải thích rõ quyền lợi, phí bảo hiểm và quy trình bồi thường
- Nếu khách quan tâm: tạo mã tư vấn (format: INS-{company_id[:4]}-YYYYMMDD-XXXX)
- Hướng dẫn bước tiếp theo: hẹn lịch tư vấn chi tiết hoặc đăng ký
- Nhấn mạnh lợi ích bảo vệ và an tâm tài chính

PHẢN HỒI:
"""
        else:
            return f"""
You are a professional insurance consultant for the company (ID: {company_id}).

INSURANCE EXPERTISE:
- Insurance consultation: life, health, auto, property, travel insurance
- Risk analysis and premium calculation
- Registration process and claims procedure guidance
- Long-term financial protection planning
- Contract renewal and adjustment support

IMPORTANT RULES:
1. ONLY advise on insurance products of this company (ID: {company_id})
2. DO NOT mention other insurance companies
3. Always analyze specific protection needs of customers
4. Clearly explain benefits and insurance conditions
5. Generate consultation code when customers show interest in specific products

COMPANY INFORMATION:
{company_context}

RECENT CHAT HISTORY:
{self._format_chat_history(chat_history, language)}

CUSTOMER QUESTION: {message}

Response guidelines:
- Respond in English professionally and clearly
- Analyze customer's protection needs (family, assets, health)
- Introduce suitable insurance packages for their financial situation
- Explain benefits, premiums, and claims procedures clearly
- If customer interested: create consultation code (format: INS-{company_id[:4]}-YYYYMMDD-XXXX)
- Guide next steps: schedule detailed consultation or registration
- Emphasize protection benefits and financial peace of mind

RESPONSE:
"""
    
    def _detect_purchase_intent(self, message: str, language: Language) -> bool:
        """Detect if customer shows purchase intent / Phát hiện ý định mua của khách hàng"""
        if language == Language.VIETNAMESE:
            intent_keywords = [
                "muốn mua", "đăng ký", "tham gia", "quan tâm", "tư vấn chi tiết",
                "bao nhiêu tiền", "phí bảo hiểm", "quy trình", "thủ tục",
                "làm sao để", "cần bảo hiểm", "bảo vệ", "an toàn"
            ]
        else:
            intent_keywords = [
                "want to buy", "interested in", "how much", "premium cost",
                "sign up", "register", "purchase", "need insurance",
                "protect", "coverage", "policy", "quote"
            ]
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in intent_keywords)
    
    def _generate_consultation_code(self, company_id: str) -> str:
        """Generate insurance consultation code / Tạo mã tư vấn bảo hiểm"""
        timestamp = datetime.now().strftime("%Y%m%d")
        import random
        random_num = random.randint(1000, 9999)
        return f"INS-{company_id[:4].upper()}-{timestamp}-{random_num}"
    
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
Xin lỗi, tôi đang gặp sự cố trong việc xử lý yêu cầu tư vấn bảo hiểm của bạn.
Để được hỗ trợ tốt nhất, bạn có thể:
- Liên hệ trực tiếp với bộ phận tư vấn bảo hiểm
- Ghé thăm văn phòng để được tư vấn trực tiếp
- Gửi email với thông tin chi tiết về nhu cầu bảo hiểm
- Thử hỏi lại với thông tin cụ thể hơn về loại bảo hiểm

Tôi sẵn sàng hỗ trợ bạn với các sản phẩm bảo hiểm khác!
"""
        else:
            return """
Sorry, I'm experiencing difficulties processing your insurance consultation request.
For the best support, you can:
- Contact the insurance consultation department directly
- Visit the office for direct consultation
- Send an email with detailed insurance needs
- Try asking again with more specific insurance type information

I'm ready to help you with other insurance products!
"""
