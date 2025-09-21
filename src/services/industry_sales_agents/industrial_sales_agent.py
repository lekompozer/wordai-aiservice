"""
Industrial Sales Agent
Agent bán hàng chuyên biệt cho ngành Công nghiệp
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.models.unified_models import Language
from src.providers.ai_provider_manager import AIProviderManager

class IndustrialSalesAgent:
    """
    Specialized industrial sales agent
    Agent bán hàng chuyên biệt cho ngành công nghiệp
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
        Process industrial equipment consultation inquiry
        Xử lý yêu cầu tư vấn thiết bị công nghiệp
        """
        try:
            print(f"🏭 [INDUSTRIAL_SALES] Processing industrial inquiry for company {company_id}")
            print(f"   Message: {message[:100]}...")
            
            # Create specialized industrial prompt / Tạo prompt chuyên biệt công nghiệp
            prompt = self._create_industrial_consultation_prompt(
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
                user_id=user_id or "industrial_sales_agent"
            )
            
            # Generate project code if customer shows interest / Tạo mã dự án nếu khách quan tâm
            project_code = None
            if self._detect_purchase_intent(message, language):
                project_code = self._generate_project_code(company_id)
            
            return {
                "response": response,
                "industry": "industrial",
                "agent_type": "industrial_sales",
                "company_id": company_id,
                "language": language.value,
                "project_code": project_code,
                "confidence": 0.95
            }
            
        except Exception as e:
            print(f"❌ [INDUSTRIAL_SALES] Error: {e}")
            return {
                "response": self._get_fallback_response(language),
                "industry": "industrial",
                "agent_type": "industrial_sales",
                "error": str(e),
                "confidence": 0.3
            }
    
    def _create_industrial_consultation_prompt(
        self,
        message: str,
        company_context: str,
        language: Language,
        company_id: str,
        chat_history: List[Dict[str, Any]]
    ) -> str:
        """
        Create specialized industrial consultation prompt
        Tạo prompt tư vấn công nghiệp chuyên biệt
        """
        if language == Language.VIETNAMESE:
            return f"""
Bạn là chuyên viên kỹ thuật và tư vấn giải pháp công nghiệp của công ty (ID: {company_id}).

CHUYÊN MÔN CÔNG NGHIỆP:
- Tư vấn thiết bị và máy móc công nghiệp: sản xuất, chế biến, đóng gói
- Thiết kế hệ thống tự động hóa và dây chuyền sản xuất
- Đánh giá nhu cầu kỹ thuật và tối ưu hóa quy trình
- Hỗ trợ kỹ thuật, bảo trì và đào tạo vận hành
- Quản lý dự án lắp đặt và chạy thử thiết bị
- Tư vấn giải pháp tiết kiệm năng lượng và an toàn lao động

QUY TẮC QUAN TRỌNG:
1. CHỈ tư vấn thiết bị và giải pháp của công ty này (ID: {company_id})
2. KHÔNG đề cập đến nhà cung cấp thiết bị công nghiệp khác
3. Luôn phân tích nhu cầu kỹ thuật và quy mô sản xuất
4. Đưa ra giải pháp tối ưu về chi phí và hiệu quả
5. Tạo mã dự án khi khách hàng có nhu cầu cụ thể

THÔNG TIN CÔNG TY:
{company_context}

LỊCH SỬ CHAT GẦN ĐÂY:
{self._format_chat_history(chat_history, language)}

CÂU HỎI KHÁCH HÀNG: {message}

Hướng dẫn trả lời:
- Trả lời bằng tiếng Việt chuyên nghiệp, kỹ thuật
- Phân tích nhu cầu kỹ thuật và quy mô sản xuất của khách hàng
- Đề xuất thiết bị và giải pháp phù hợp với ngân sách
- Giải thích đặc tính kỹ thuật, công suất và hiệu quả
- Nếu khách quan tâm: tạo mã dự án (format: IND-{company_id[:4]}-YYYYMMDD-XXXX)
- Hướng dẫn bước tiếp theo: khảo sát thực địa, báo giá chi tiết
- Nhấn mạnh chất lượng thiết bị và dịch vụ hậu mãi

PHẢN HỒI:
"""
        else:
            return f"""
You are a technical specialist and industrial solution consultant for the company (ID: {company_id}).

INDUSTRIAL EXPERTISE:
- Industrial equipment and machinery consultation: production, processing, packaging
- Automation system and production line design
- Technical requirement assessment and process optimization
- Technical support, maintenance, and operation training
- Project management for installation and equipment commissioning
- Energy-saving solutions and workplace safety consultation

IMPORTANT RULES:
1. ONLY advise on equipment and solutions of this company (ID: {company_id})
2. DO NOT mention other industrial equipment suppliers
3. Always analyze technical needs and production scale
4. Provide optimal solutions for cost and efficiency
5. Generate project code when customers have specific needs

COMPANY INFORMATION:
{company_context}

RECENT CHAT HISTORY:
{self._format_chat_history(chat_history, language)}

CUSTOMER QUESTION: {message}

Response guidelines:
- Respond in English professionally and technically
- Analyze customer's technical needs and production scale
- Suggest suitable equipment and solutions within budget
- Explain technical specifications, capacity, and efficiency
- If customer interested: create project code (format: IND-{company_id[:4]}-YYYYMMDD-XXXX)
- Guide next steps: site survey, detailed quotation
- Emphasize equipment quality and after-sales service

RESPONSE:
"""
    
    def _detect_purchase_intent(self, message: str, language: Language) -> bool:
        """Detect if customer shows purchase intent / Phát hiện ý định mua của khách hàng"""
        if language == Language.VIETNAMESE:
            intent_keywords = [
                "cần thiết bị", "mua máy", "lắp đặt", "dự án", "nhà máy",
                "sản xuất", "chế biến", "tự động hóa", "dây chuyền",
                "giá", "báo giá", "chi phí", "đầu tư", "công suất"
            ]
        else:
            intent_keywords = [
                "need equipment", "buy machine", "installation", "project",
                "factory", "production", "processing", "automation",
                "production line", "price", "quote", "cost", "investment", "capacity"
            ]
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in intent_keywords)
    
    def _generate_project_code(self, company_id: str) -> str:
        """Generate industrial project code / Tạo mã dự án công nghiệp"""
        timestamp = datetime.now().strftime("%Y%m%d")
        import random
        random_num = random.randint(1000, 9999)
        return f"IND-{company_id[:4].upper()}-{timestamp}-{random_num}"
    
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
Xin lỗi, tôi đang gặp sự cố trong việc xử lý yêu cầu tư vấn thiết bị công nghiệp của bạn.
Để được hỗ trợ tốt nhất, bạn có thể:
- Liên hệ trực tiếp với bộ phận kỹ thuật
- Gửi thông tin chi tiết về nhu cầu sản xuất
- Yêu cầu chuyên viên đến khảo sát thực địa
- Thử hỏi lại với thông tin cụ thể hơn về loại thiết bị

Tôi sẵn sàng hỗ trợ bạn tìm kiếm giải pháp công nghiệp phù hợp!
"""
        else:
            return """
Sorry, I'm experiencing difficulties processing your industrial equipment consultation request.
For the best support, you can:
- Contact the technical department directly
- Send detailed information about your production needs
- Request a specialist for on-site survey
- Try asking again with more specific equipment type information

I'm ready to help you find suitable industrial solutions!
"""
