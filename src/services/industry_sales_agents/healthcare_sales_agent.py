"""
Healthcare Sales Agent
Agent bán hàng chuyên biệt cho ngành Y tế
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.models.unified_models import Language
from src.providers.ai_provider_manager import AIProviderManager

class HealthcareSalesAgent:
    """
    Specialized healthcare sales agent
    Agent bán hàng chuyên biệt cho ngành y tế
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
        Process healthcare service consultation inquiry
        Xử lý yêu cầu tư vấn dịch vụ y tế
        """
        try:
            print(f"🏥 [HEALTHCARE_SALES] Processing healthcare inquiry for company {company_id}")
            print(f"   Message: {message[:100]}...")
            
            # Create specialized healthcare prompt / Tạo prompt chuyên biệt y tế
            prompt = self._create_healthcare_consultation_prompt(
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
                user_id=user_id or "healthcare_sales_agent"
            )
            
            # Generate appointment code if customer shows interest / Tạo mã hẹn khám nếu khách quan tâm
            appointment_code = None
            if self._detect_service_intent(message, language):
                appointment_code = self._generate_appointment_code(company_id)
            
            return {
                "response": response,
                "industry": "healthcare",
                "agent_type": "healthcare_sales",
                "company_id": company_id,
                "language": language.value,
                "appointment_code": appointment_code,
                "confidence": 0.95
            }
            
        except Exception as e:
            print(f"❌ [HEALTHCARE_SALES] Error: {e}")
            return {
                "response": self._get_fallback_response(language),
                "industry": "healthcare",
                "agent_type": "healthcare_sales",
                "error": str(e),
                "confidence": 0.3
            }
    
    def _create_healthcare_consultation_prompt(
        self,
        message: str,
        company_context: str,
        language: Language,
        company_id: str,
        chat_history: List[Dict[str, Any]]
    ) -> str:
        """
        Create specialized healthcare consultation prompt
        Tạo prompt tư vấn y tế chuyên biệt
        """
        if language == Language.VIETNAMESE:
            return f"""
Bạn là tư vấn viên y tế chuyên nghiệp của cơ sở y tế (ID: {company_id}).

CHUYÊN MÔN Y TẾ:
- Tư vấn các dịch vụ khám chữa bệnh và chăm sóc sức khỏe
- Hướng dẫn đặt lịch khám với các bác sĩ chuyên khoa
- Tư vấn các gói khám sức khỏe tổng quát và định kỳ
- Hỗ trợ thông tin về chi phí điều trị và bảo hiểm y tế
- Chăm sóc khách hàng sau điều trị và theo dõi sức khỏe
- Tư vấn dịch vụ y tế tại nhà và chăm sóc người cao tuổi

QUY TẮC QUAN TRỌNG:
1. CHỈ tư vấn dịch vụ y tế của cơ sở này (ID: {company_id})
2. KHÔNG đề cập đến bệnh viện hoặc phòng khám khác
3. KHÔNG đưa ra chẩn đoán y khoa cụ thể
4. Luôn khuyến khích khách hàng gặp bác sĩ để được tư vấn chính xác
5. Tạo mã hẹn khám khi khách hàng muốn đặt lịch

THÔNG TIN CƠ SỞ Y TẾ:
{company_context}

LỊCH SỬ CHAT GẦN ĐÂY:
{self._format_chat_history(chat_history, language)}

CÂU HỎI KHÁCH HÀNG: {message}

Hướng dẫn trả lời:
- Trả lời bằng tiếng Việt chuyên nghiệp, tận tâm
- Lắng nghe và hiểu vấn đề sức khỏe của khách hàng
- Gợi ý dịch vụ khám hoặc gói sức khỏe phù hợp
- Hướng dẫn quy trình đặt lịch và chuẩn bị khám
- Nếu khách muốn đặt lịch: tạo mã hẹn (format: HEAL-{company_id[:4]}-YYYYMMDD-XXXX)
- Hướng dẫn bước tiếp theo: xác nhận lịch hẹn, chuẩn bị hồ sơ
- Nhấn mạnh chất lượng dịch vụ và sự quan tâm của đội ngũ y tế

LƯU Ý: Luôn nhắc nhở đây chỉ là tư vấn chung, cần gặp bác sĩ để được tư vấn chính xác.

PHẢN HỒI:
"""
        else:
            return f"""
You are a professional healthcare consultant for the medical facility (ID: {company_id}).

HEALTHCARE EXPERTISE:
- Medical service consultation and healthcare guidance
- Appointment scheduling with specialist doctors
- General and periodic health checkup package consultation
- Treatment cost and health insurance information support
- Post-treatment patient care and health monitoring
- Home healthcare services and elderly care consultation

IMPORTANT RULES:
1. ONLY advise on medical services of this facility (ID: {company_id})
2. DO NOT mention other hospitals or clinics
3. DO NOT provide specific medical diagnoses
4. Always encourage customers to see doctors for accurate consultation
5. Generate appointment code when customers want to schedule

MEDICAL FACILITY INFORMATION:
{company_context}

RECENT CHAT HISTORY:
{self._format_chat_history(chat_history, language)}

CUSTOMER QUESTION: {message}

Response guidelines:
- Respond in English professionally and caringly
- Listen and understand customer's health concerns
- Suggest suitable medical services or health packages
- Guide appointment scheduling process and preparation
- If customer wants to schedule: create appointment code (format: HEAL-{company_id[:4]}-YYYYMMDD-XXXX)
- Guide next steps: confirm appointment, prepare medical records
- Emphasize service quality and medical team's dedication

NOTE: Always remind that this is general consultation, need to see doctor for accurate advice.

RESPONSE:
"""
    
    def _detect_service_intent(self, message: str, language: Language) -> bool:
        """Detect if customer shows service intent / Phát hiện ý định sử dụng dịch vụ của khách hàng"""
        if language == Language.VIETNAMESE:
            intent_keywords = [
                "đặt lịch", "khám", "bác sĩ", "hẹn", "tư vấn",
                "khám sức khỏe", "xét nghiệm", "chữa bệnh", "điều trị",
                "gói khám", "chi phí", "giá", "bảo hiểm", "phòng khám"
            ]
        else:
            intent_keywords = [
                "appointment", "doctor", "checkup", "consultation", "medical",
                "health check", "treatment", "examination", "test",
                "health package", "cost", "price", "insurance", "clinic"
            ]
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in intent_keywords)
    
    def _generate_appointment_code(self, company_id: str) -> str:
        """Generate healthcare appointment code / Tạo mã hẹn khám y tế"""
        timestamp = datetime.now().strftime("%Y%m%d")
        import random
        random_num = random.randint(1000, 9999)
        return f"HEAL-{company_id[:4].upper()}-{timestamp}-{random_num}"
    
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
Xin lỗi, tôi đang gặp sự cố trong việc xử lý yêu cầu tư vấn y tế của bạn.
Để được hỗ trợ tốt nhất, bạn có thể:
- Liên hệ trực tiếp với lễ tân của chúng tôi
- Gọi hotline để được tư vấn ngay lập tức
- Ghé thăm cơ sở y tế để được hỗ trợ trực tiếp
- Thử hỏi lại với thông tin cụ thể hơn về vấn đề sức khỏe

Tôi sẵn sàng hỗ trợ bạn chăm sóc sức khỏe tốt nhất!
"""
        else:
            return """
Sorry, I'm experiencing difficulties processing your healthcare consultation request.
For the best support, you can:
- Contact our reception desk directly
- Call our hotline for immediate consultation
- Visit our medical facility for direct assistance
- Try asking again with more specific health concern information

I'm ready to help you with the best healthcare services!
"""
