"""
Banking Sales Agent
Agent bán hàng cho ngành ngân hàng với prompt và flow riêng biệt
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.models.unified_models import Language, Industry
from src.providers.ai_provider_manager import AIProviderManager

class BankingSalesAgent:
    """
    Sales agent specialized for banking industry
    Agent bán hàng chuyên biệt cho ngành ngân hàng
    """
    
    def __init__(self, ai_manager: AIProviderManager):
        self.ai_manager = ai_manager
        self.industry = Industry.BANKING
    
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
        Process banking sales inquiry with specialized prompts
        Xử lý yêu cầu bán hàng ngân hàng với prompt chuyên biệt
        """
        try:
            print(f"🏦 [BANKING_SALES] Processing inquiry for company {company_id}")
            print(f"   Message: {message[:100]}...")
            
            # Create banking-specific sales prompt / Tạo prompt bán hàng chuyên biệt cho ngân hàng
            prompt = self._create_banking_sales_prompt(
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
                user_id=user_id or "banking_sales_agent"
            )
            
            return {
                "response": response,
                "industry": self.industry.value,
                "agent_type": "banking_sales",
                "company_id": company_id,
                "language": language.value,
                "confidence": 0.9
            }
            
        except Exception as e:
            print(f"❌ [BANKING_SALES] Error: {e}")
            return {
                "response": self._get_fallback_response(language),
                "industry": self.industry.value,
                "agent_type": "banking_sales",
                "error": str(e),
                "confidence": 0.3
            }
    
    def _create_banking_sales_prompt(
        self,
        message: str,
        company_context: str,
        language: Language,
        company_id: str,
        chat_history: List[Dict[str, Any]]
    ) -> str:
        """
        Create specialized banking sales prompt
        Tạo prompt bán hàng chuyên biệt cho ngân hàng
        """
        if language == Language.VIETNAMESE:
            return f"""
Bạn là chuyên viên tư vấn tài chính chuyên nghiệp của ngân hàng (ID: {company_id}).

CHUYÊN MÔN NGÂN HÀNG:
- Tư vấn các sản phẩm vay: cá nhân, thế chấp, kinh doanh
- Thẻ tín dụng và dịch vụ thanh toán
- Tiết kiệm và đầu tư
- Bảo hiểm ngân hàng
- Dịch vụ chuyển tiền và ngoại hối

QUY TẮC QUAN TRỌNG:
1. CHỈ tư vấn sản phẩm/dịch vụ của ngân hàng này (ID: {company_id})
2. KHÔNG đề cập đến ngân hàng khác
3. KHÔNG tư vấn ngoài lĩnh vực ngân hàng
4. Luôn hướng khách hàng đến các bước cụ thể để thực hiện giao dịch
5. Tạo mã giao dịch tạm thời khi khách hàng có nhu cầu rõ ràng

THÔNG TIN NGÂN HÀNG:
{company_context}

LỊCH SỬ CHAT GẦN ĐÂY:
{self._format_chat_history(chat_history, language)}

CÂU HỎI KHÁCH HÀNG: {message}

Hướng dẫn trả lời:
- Trả lời bằng tiếng Việt chuyên nghiệp, thân thiện
- Phân tích nhu cầu tài chính của khách hàng
- Đề xuất sản phẩm phù hợp với lợi ích cụ thể
- Nếu khách hàng quan tâm: tạo mã tư vấn (format: BANK-{company_id[:4]}-YYYYMMDD-XXXX)
- Hướng dẫn bước tiếp theo: đăng ký online, đến chi nhánh, gọi hotline
- Nhấn mạnh ưu điểm cạnh tranh của ngân hàng

PHẢN HỒI:
"""
        else:
            return f"""
You are a professional financial advisor for the bank (ID: {company_id}).

BANKING EXPERTISE:
- Loan consulting: personal, mortgage, business loans
- Credit cards and payment services
- Savings and investment
- Bank insurance
- Money transfer and foreign exchange services

IMPORTANT RULES:
1. ONLY advise on products/services of this bank (ID: {company_id})
2. DO NOT mention other banks
3. DO NOT advise outside banking field
4. Always guide customers to specific steps for transactions
5. Generate temporary transaction codes when customers show clear interest

BANK INFORMATION:
{company_context}

RECENT CHAT HISTORY:
{self._format_chat_history(chat_history, language)}

CUSTOMER QUESTION: {message}

Response guidelines:
- Respond in English professionally and friendly
- Analyze customer's financial needs
- Suggest suitable products with specific benefits
- If customer is interested: create consultation code (format: BANK-{company_id[:4]}-YYYYMMDD-XXXX)
- Guide next steps: online registration, branch visit, hotline call
- Emphasize bank's competitive advantages

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
Xin lỗi, tôi đang gặp sự cố trong việc xử lý yêu cầu tư vấn tài chính của bạn.
Để được hỗ trợ tốt nhất, bạn có thể:
- Gọi hotline ngân hàng để được tư vấn trực tiếp
- Ghé thăm chi nhánh gần nhất
- Truy cập website chính thức của ngân hàng
- Thử hỏi lại với câu hỏi cụ thể hơn

Tôi sẵn sàng hỗ trợ bạn với các vấn đề tài chính khác!
"""
        else:
            return """
Sorry, I'm experiencing difficulties processing your financial consultation request.
For the best support, you can:
- Call the bank hotline for direct consultation
- Visit the nearest branch
- Access the bank's official website
- Try asking again with a more specific question

I'm ready to help you with other financial matters!
"""
