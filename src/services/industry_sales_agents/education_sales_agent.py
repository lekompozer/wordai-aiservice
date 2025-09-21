"""
Education Sales Agent
Agent bán hàng chuyên biệt cho ngành Giáo dục
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.models.unified_models import Language
from src.providers.ai_provider_manager import AIProviderManager

class EducationSalesAgent:
    """
    Specialized education sales agent
    Agent bán hàng chuyên biệt cho ngành giáo dục
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
        Process education service consultation inquiry
        Xử lý yêu cầu tư vấn dịch vụ giáo dục
        """
        try:
            print(f"🎓 [EDUCATION_SALES] Processing education inquiry for company {company_id}")
            print(f"   Message: {message[:100]}...")
            
            # Create specialized education prompt / Tạo prompt chuyên biệt giáo dục
            prompt = self._create_education_consultation_prompt(
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
                user_id=user_id or "education_sales_agent"
            )
            
            # Generate enrollment code if customer shows interest / Tạo mã đăng ký nếu khách quan tâm
            enrollment_code = None
            if self._detect_enrollment_intent(message, language):
                enrollment_code = self._generate_enrollment_code(company_id)
            
            return {
                "response": response,
                "industry": "education",
                "agent_type": "education_sales",
                "company_id": company_id,
                "language": language.value,
                "enrollment_code": enrollment_code,
                "confidence": 0.95
            }
            
        except Exception as e:
            print(f"❌ [EDUCATION_SALES] Error: {e}")
            return {
                "response": self._get_fallback_response(language),
                "industry": "education",
                "agent_type": "education_sales",
                "error": str(e),
                "confidence": 0.3
            }
    
    def _create_education_consultation_prompt(
        self,
        message: str,
        company_context: str,
        language: Language,
        company_id: str,
        chat_history: List[Dict[str, Any]]
    ) -> str:
        """
        Create specialized education consultation prompt
        Tạo prompt tư vấn giáo dục chuyên biệt
        """
        if language == Language.VIETNAMESE:
            return f"""
Bạn là tư vấn viên giáo dục chuyên nghiệp của cơ sở giáo dục (ID: {company_id}).

CHUYÊN MÔN GIÁO DỤC:
- Tư vấn các khóa học và chương trình đào tạo phù hợp
- Hướng dẫn lộ trình học tập và phát triển kỹ năng
- Tư vấn đăng ký học, thủ tục và học phí
- Hỗ trợ học viên trong quá trình học tập
- Tư vấn chứng chỉ, bằng cấp và cơ hội nghề nghiệp
- Chăm sóc học viên và tư vấn học bổng

QUY TẮC QUAN TRỌNG:
1. CHỈ tư vấn các khóa học của cơ sở này (ID: {company_id})
2. KHÔNG đề cập đến trường học hoặc trung tâm đào tạo khác
3. Luôn phân tích nhu cầu học tập và mục tiêu nghề nghiệp
4. Đưa ra lộ trình học tập phù hợp với từng cá nhân
5. Tạo mã đăng ký khi học viên quan tâm đến khóa học cụ thể

THÔNG TIN CƠ SỞ GIÁO DỤC:
{company_context}

LỊCH SỬ CHAT GẦN ĐÂY:
{self._format_chat_history(chat_history, language)}

CÂU HỎI KHÁCH HÀNG: {message}

Hướng dẫn trả lời:
- Trả lời bằng tiếng Việt chuyên nghiệp, nhiệt tình
- Phân tích nhu cầu học tập và mục tiêu nghề nghiệp
- Gợi ý khóa học phù hợp với trình độ và thời gian
- Giải thích chi tiết về nội dung, thời lượng và học phí
- Nếu học viên quan tâm: tạo mã đăng ký (format: EDU-{company_id[:4]}-YYYYMMDD-XXXX)
- Hướng dẫn bước tiếp theo: đăng ký, thanh toán, bắt đầu học
- Nhấn mạnh chất lượng giảng dạy và cơ hội phát triển

PHẢN HỒI:
"""
        else:
            return f"""
You are a professional education consultant for the educational institution (ID: {company_id}).

EDUCATION EXPERTISE:
- Course and training program consultation
- Learning pathway and skill development guidance
- Enrollment guidance, procedures, and tuition consultation
- Student support during learning process
- Certificate, degree, and career opportunity consultation
- Student care and scholarship consultation

IMPORTANT RULES:
1. ONLY advise on courses of this institution (ID: {company_id})
2. DO NOT mention other schools or training centers
3. Always analyze learning needs and career goals
4. Provide suitable learning pathways for each individual
5. Generate enrollment code when students show interest in specific courses

EDUCATIONAL INSTITUTION INFORMATION:
{company_context}

RECENT CHAT HISTORY:
{self._format_chat_history(chat_history, language)}

CUSTOMER QUESTION: {message}

Response guidelines:
- Respond in English professionally and enthusiastically
- Analyze learning needs and career objectives
- Suggest suitable courses for skill level and schedule
- Explain details about content, duration, and tuition
- If student interested: create enrollment code (format: EDU-{company_id[:4]}-YYYYMMDD-XXXX)
- Guide next steps: enrollment, payment, start learning
- Emphasize teaching quality and development opportunities

RESPONSE:
"""
    
    def _detect_enrollment_intent(self, message: str, language: Language) -> bool:
        """Detect if customer shows enrollment intent / Phát hiện ý định đăng ký của khách hàng"""
        if language == Language.VIETNAMESE:
            intent_keywords = [
                "đăng ký", "học", "khóa học", "lớp", "chương trình",
                "học phí", "thời gian học", "lịch học", "giáo viên",
                "chứng chỉ", "bằng cấp", "học bổng", "tư vấn", "muốn học"
            ]
        else:
            intent_keywords = [
                "enroll", "register", "course", "class", "program",
                "tuition", "schedule", "teacher", "instructor",
                "certificate", "degree", "scholarship", "want to learn", "study"
            ]
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in intent_keywords)
    
    def _generate_enrollment_code(self, company_id: str) -> str:
        """Generate education enrollment code / Tạo mã đăng ký giáo dục"""
        timestamp = datetime.now().strftime("%Y%m%d")
        import random
        random_num = random.randint(1000, 9999)
        return f"EDU-{company_id[:4].upper()}-{timestamp}-{random_num}"
    
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
Xin lỗi, tôi đang gặp sự cố trong việc xử lý yêu cầu tư vấn giáo dục của bạn.
Để được hỗ trợ tốt nhất, bạn có thể:
- Liên hệ trực tiếp với phòng tư vấn tuyển sinh
- Ghé thăm cơ sở để được tư vấn trực tiếp và tham quan
- Gửi thông tin về nhu cầu học tập cụ thể
- Thử hỏi lại với thông tin chi tiết hơn về khóa học quan tâm

Tôi sẵn sàng hỗ trợ bạn tìm kiếm con đường học tập phù hợp!
"""
        else:
            return """
Sorry, I'm experiencing difficulties processing your education consultation request.
For the best support, you can:
- Contact the admissions counseling office directly
- Visit our facility for direct consultation and tour
- Send information about your specific learning needs
- Try asking again with more detailed course interest information

I'm ready to help you find the right learning path!
"""
