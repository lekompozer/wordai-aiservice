"""
Generic Sales Agent
Agent bán hàng chung cho các ngành: Insurance, Fashion, Industrial, Healthcare, Education, Other
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.models.unified_models import Language, Industry
from src.providers.ai_provider_manager import AIProviderManager

class GenericSalesAgent:
    """
    Generic sales agent for various industries
    Agent bán hàng chung cho các ngành khác nhau
    """
    
    def __init__(self, ai_manager: AIProviderManager, industry: Industry):
        self.ai_manager = ai_manager
        self.industry = industry
    
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
        Process sales inquiry with industry-specific prompts
        Xử lý yêu cầu bán hàng với prompt chuyên biệt theo ngành
        """
        try:
            print(f"💼 [GENERIC_SALES] Processing {self.industry.value} inquiry for company {company_id}")
            print(f"   Message: {message[:100]}...")
            
            # Create industry-specific sales prompt / Tạo prompt bán hàng chuyên biệt theo ngành
            prompt = self._create_industry_sales_prompt(
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
                user_id=user_id or "generic_sales_agent"
            )
            
            return {
                "response": response,
                "industry": self.industry.value,
                "agent_type": "generic_sales",
                "company_id": company_id,
                "language": language.value,
                "confidence": 0.9
            }
            
        except Exception as e:
            print(f"❌ [GENERIC_SALES] Error: {e}")
            return {
                "response": self._get_fallback_response(language),
                "industry": self.industry.value,
                "agent_type": "generic_sales",
                "error": str(e),
                "confidence": 0.3
            }
    
    def _create_industry_sales_prompt(
        self,
        message: str,
        company_context: str,
        language: Language,
        company_id: str,
        chat_history: List[Dict[str, Any]]
    ) -> str:
        """
        Create industry-specific sales prompt
        Tạo prompt bán hàng chuyên biệt theo ngành
        """
        industry_info = self._get_industry_info(self.industry, language)
        
        if language == Language.VIETNAMESE:
            return f"""
Bạn là {industry_info['role']} chuyên nghiệp của công ty (ID: {company_id}) trong ngành {industry_info['name']}.

CHUYÊN MÔN {industry_info['name'].upper()}:
{industry_info['expertise']}

QUY TẮC QUAN TRỌNG:
1. CHỈ tư vấn sản phẩm/dịch vụ của công ty này (ID: {company_id})
2. KHÔNG đề cập đến công ty khác trong cùng ngành
3. KHÔNG tư vấn ngoài lĩnh vực {industry_info['name']}
4. Luôn hướng khách hàng đến các bước cụ thể để thực hiện giao dịch
5. Tạo mã tư vấn tạm thời khi khách hàng có nhu cầu rõ ràng

THÔNG TIN CÔNG TY:
{company_context}

LỊCH SỬ CHAT GẦN ĐÂY:
{self._format_chat_history(chat_history, language)}

CÂU HỎI KHÁCH HÀNG: {message}

Hướng dẫn trả lời:
- Trả lời bằng tiếng Việt chuyên nghiệp, thân thiện
- Phân tích nhu cầu của khách hàng trong lĩnh vực {industry_info['name']}
- Đề xuất giải pháp phù hợp với yêu cầu và ngân sách
- Nếu khách hàng quan tâm: tạo mã tư vấn (format: {industry_info['code']}-{company_id[:4]}-YYYYMMDD-XXXX)
- Hướng dẫn bước tiếp theo: liên hệ, hẹn lịch, hoặc thực hiện dịch vụ
- Nhấn mạnh lợi ích và ưu điểm của công ty này

PHẢN HỒI:
"""
        else:
            return f"""
You are a professional {industry_info['role']} for the company (ID: {company_id}) in the {industry_info['name']} industry.

{industry_info['name'].upper()} EXPERTISE:
{industry_info['expertise']}

IMPORTANT RULES:
1. ONLY advise on products/services of this company (ID: {company_id})
2. DO NOT mention other companies in the same industry
3. DO NOT advise outside {industry_info['name']} field
4. Always guide customers to specific steps for transactions
5. Generate temporary consultation codes when customers show clear interest

COMPANY INFORMATION:
{company_context}

RECENT CHAT HISTORY:
{self._format_chat_history(chat_history, language)}

CUSTOMER QUESTION: {message}

Response guidelines:
- Respond in English professionally and friendly
- Analyze customer needs in {industry_info['name']} field
- Suggest solutions suitable for requirements and budget
- If customer is interested: create consultation code (format: {industry_info['code']}-{company_id[:4]}-YYYYMMDD-XXXX)
- Guide next steps: contact, appointment, or service execution
- Emphasize benefits and advantages of this company

RESPONSE:
"""
    
    def _get_industry_info(self, industry: Industry, language: Language) -> Dict[str, str]:
        """Get industry-specific information / Lấy thông tin chuyên biệt theo ngành"""
        if language == Language.VIETNAMESE:
            info_map = {
                Industry.INSURANCE: {
                    "name": "Bảo hiểm",
                    "role": "chuyên viên tư vấn bảo hiểm",
                    "code": "INS",
                    "expertise": "- Tư vấn các gói bảo hiểm: nhân thọ, sức khỏe, xe cộ\n- Định giá rủi ro và tính phí bảo hiểm\n- Hỗ trợ giải quyết bồi thường\n- Chăm sóc khách hàng và gia hạn hợp đồng"
                },
                Industry.FASHION: {
                    "name": "Thời trang",
                    "role": "tư vấn viên thời trang",
                    "code": "FASH",
                    "expertise": "- Tư vấn phong cách và xu hướng thời trang\n- Gợi ý trang phục phù hợp theo dáng người\n- Kết hợp trang phục và phụ kiện\n- Chăm sóc khách hàng VIP và stylist cá nhân"
                },
                Industry.INDUSTRIAL: {
                    "name": "Công nghiệp",
                    "role": "chuyên viên kỹ thuật",
                    "code": "IND",
                    "expertise": "- Tư vấn thiết bị và giải pháp công nghiệp\n- Đánh giá nhu cầu kỹ thuật\n- Hỗ trợ kỹ thuật và bảo trì\n- Quản lý dự án công nghiệp"
                },
                Industry.HEALTHCARE: {
                    "name": "Y tế",
                    "role": "tư vấn viên y tế",
                    "code": "HEAL",
                    "expertise": "- Tư vấn dịch vụ khám chữa bệnh\n- Hướng dẫn đặt lịch khám\n- Tư vấn gói khám sức khỏe\n- Chăm sóc khách hàng sau điều trị"
                },
                Industry.EDUCATION: {
                    "name": "Giáo dục",
                    "role": "tư vấn viên giáo dục",
                    "code": "EDU",
                    "expertise": "- Tư vấn các khóa học và chương trình đào tạo\n- Hướng dẫn đăng ký học tập\n- Tư vấn lộ trình học tập\n- Hỗ trợ học viên trong quá trình học"
                },
                Industry.OTHER: {
                    "name": "Dịch vụ khác",
                    "role": "chuyên viên tư vấn",
                    "code": "OTHER",
                    "expertise": "- Tư vấn dịch vụ chuyên nghiệp\n- Phân tích nhu cầu khách hàng\n- Đề xuất giải pháp phù hợp\n- Hỗ trợ khách hàng toàn diện"
                }
            }
        else:
            info_map = {
                Industry.INSURANCE: {
                    "name": "Insurance",
                    "role": "insurance consultant",
                    "code": "INS",
                    "expertise": "- Insurance package consultation: life, health, auto\n- Risk assessment and premium calculation\n- Claims processing support\n- Customer care and contract renewal"
                },
                Industry.FASHION: {
                    "name": "Fashion",
                    "role": "fashion consultant",
                    "code": "FASH",
                    "expertise": "- Style and fashion trend consultation\n- Outfit suggestions based on body type\n- Clothing and accessory coordination\n- VIP customer care and personal styling"
                },
                Industry.INDUSTRIAL: {
                    "name": "Industrial",
                    "role": "technical specialist",
                    "code": "IND",
                    "expertise": "- Industrial equipment and solution consultation\n- Technical requirement assessment\n- Technical support and maintenance\n- Industrial project management"
                },
                Industry.HEALTHCARE: {
                    "name": "Healthcare",
                    "role": "healthcare consultant",
                    "code": "HEAL",
                    "expertise": "- Medical service consultation\n- Appointment scheduling guidance\n- Health checkup package consultation\n- Post-treatment customer care"
                },
                Industry.EDUCATION: {
                    "name": "Education",
                    "role": "education consultant",
                    "code": "EDU",
                    "expertise": "- Course and training program consultation\n- Enrollment guidance\n- Learning pathway consultation\n- Student support during learning"
                },
                Industry.OTHER: {
                    "name": "Other Services",
                    "role": "professional consultant",
                    "code": "OTHER",
                    "expertise": "- Professional service consultation\n- Customer need analysis\n- Suitable solution suggestions\n- Comprehensive customer support"
                }
            }
        
        return info_map.get(industry, info_map[Industry.OTHER])
    
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
        industry_name = self._get_industry_info(self.industry, language)['name']
        
        if language == Language.VIETNAMESE:
            return f"""
Xin lỗi, tôi đang gặp sự cố trong việc xử lý yêu cầu tư vấn {industry_name} của bạn.
Để được hỗ trợ tốt nhất, bạn có thể:
- Liên hệ trực tiếp với bộ phận tư vấn
- Ghé thăm văn phòng để được hỗ trợ trực tiếp
- Gửi email với yêu cầu cụ thể
- Thử hỏi lại với thông tin chi tiết hơn

Tôi sẵn sàng hỗ trợ bạn với các dịch vụ {industry_name} khác!
"""
        else:
            return f"""
Sorry, I'm experiencing difficulties processing your {industry_name} consultation request.
For the best support, you can:
- Contact the consultation department directly
- Visit the office for direct support
- Send an email with specific requirements
- Try asking again with more detailed information

I'm ready to help you with other {industry_name} services!
"""
