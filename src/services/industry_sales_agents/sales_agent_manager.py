"""
Sales Agent Manager
Quản lý tất cả các Sales Agent theo ngành
"""

from typing import Dict, Any, Optional, List
from src.models.unified_models import Language, Industry
from src.providers.ai_provider_manager import AIProviderManager

# Import all sales agents
from .banking_sales_agent import BankingSalesAgent
from .restaurant_sales_agent import RestaurantSalesAgent
from .retail_sales_agent import RetailSalesAgent
from .hotel_sales_agent import HotelSalesAgent
from .insurance_sales_agent import InsuranceSalesAgent
from .fashion_sales_agent import FashionSalesAgent
from .industrial_sales_agent import IndustrialSalesAgent
from .healthcare_sales_agent import HealthcareSalesAgent
from .education_sales_agent import EducationSalesAgent
from .generic_sales_agent import GenericSalesAgent

class SalesAgentManager:
    """
    Manager for all industry-specific sales agents
    Quản lý tất cả các sales agent chuyên biệt theo ngành
    """
    
    def __init__(self, ai_manager: AIProviderManager):
        self.ai_manager = ai_manager
        self._agents: Dict[Industry, Any] = {}
        self._initialize_agents()
    
    def _initialize_agents(self):
        """Initialize all sales agents / Khởi tạo tất cả sales agent"""
        self._agents[Industry.BANKING] = BankingSalesAgent(self.ai_manager)
        self._agents[Industry.RESTAURANT] = RestaurantSalesAgent(self.ai_manager)
        self._agents[Industry.RETAIL] = RetailSalesAgent(self.ai_manager)
        self._agents[Industry.HOTEL] = HotelSalesAgent(self.ai_manager)
        
        # Specialized agents for specific industries
        self._agents[Industry.INSURANCE] = InsuranceSalesAgent(self.ai_manager)
        self._agents[Industry.FASHION] = FashionSalesAgent(self.ai_manager)
        self._agents[Industry.INDUSTRIAL] = IndustrialSalesAgent(self.ai_manager)
        self._agents[Industry.HEALTHCARE] = HealthcareSalesAgent(self.ai_manager)
        self._agents[Industry.EDUCATION] = EducationSalesAgent(self.ai_manager)
        
        # Generic agent only for OTHER industry
        self._agents[Industry.OTHER] = GenericSalesAgent(self.ai_manager, Industry.OTHER)
    
    async def process_sales_inquiry(
        self,
        message: str,
        industry: Industry,
        company_id: str,
        session_id: str,
        language: Language,
        company_context: str,
        chat_history: List[Dict[str, Any]] = None,
        user_id: str = None
    ) -> Dict[str, Any]:
        """
        Process sales inquiry with appropriate agent
        Xử lý yêu cầu bán hàng với agent phù hợp
        """
        try:
            print(f"🎯 [SALES_MANAGER] Routing to {industry.value} agent for company {company_id}")
            
            # Get appropriate agent for the industry
            agent = self._agents.get(industry)
            if not agent:
                print(f"❌ [SALES_MANAGER] No agent found for industry: {industry.value}")
                agent = self._agents[Industry.OTHER]  # Fallback to generic agent
            
            # Process the inquiry
            result = await agent.process_sales_inquiry(
                message=message,
                company_id=company_id,
                session_id=session_id,
                language=language,
                company_context=company_context,
                chat_history=chat_history,
                user_id=user_id
            )
            
            print(f"✅ [SALES_MANAGER] Successfully processed {industry.value} inquiry")
            return result
            
        except Exception as e:
            print(f"❌ [SALES_MANAGER] Error processing sales inquiry: {e}")
            return {
                "response": self._get_error_response(language, industry),
                "industry": industry.value,
                "agent_type": "error",
                "error": str(e),
                "confidence": 0.2
            }
    
    def get_supported_industries(self) -> List[Industry]:
        """Get list of supported industries / Lấy danh sách ngành được hỗ trợ"""
        return list(self._agents.keys())
    
    def get_agent_info(self, industry: Industry) -> Dict[str, Any]:
        """Get information about a specific agent / Lấy thông tin về agent cụ thể"""
        agent = self._agents.get(industry)
        if not agent:
            return {"error": f"No agent found for industry: {industry.value}"}
        
        return {
            "industry": industry.value,
            "agent_type": type(agent).__name__,
            "specialized": isinstance(agent, (BankingSalesAgent, RestaurantSalesAgent, 
                                          RetailSalesAgent, HotelSalesAgent,
                                          InsuranceSalesAgent, FashionSalesAgent,
                                          IndustrialSalesAgent, HealthcareSalesAgent,
                                          EducationSalesAgent)),
            "capabilities": self._get_agent_capabilities(industry)
        }
    
    def _get_agent_capabilities(self, industry: Industry) -> List[str]:
        """Get agent capabilities by industry / Lấy khả năng của agent theo ngành"""
        capabilities_map = {
            Industry.BANKING: [
                "Financial product consultation",
                "Loan and credit assessment",
                "Investment advice",
                "Banking service guidance",
                "Transaction code generation"
            ],
            Industry.RESTAURANT: [
                "Table reservation",
                "Menu consultation",
                "Special event booking",
                "Catering services",
                "Reservation code generation"
            ],
            Industry.RETAIL: [
                "Product consultation",
                "Order processing",
                "Inventory checking",
                "Customer service",
                "Order code generation"
            ],
            Industry.HOTEL: [
                "Room booking",
                "Amenity consultation",
                "Event planning",
                "Concierge services",
                "Booking code generation"
            ],
            Industry.INSURANCE: [
                "Policy consultation",
                "Risk assessment",
                "Claims support",
                "Coverage analysis"
            ],
            Industry.FASHION: [
                "Style consultation",
                "Trend advice",
                "Personal shopping",
                "Wardrobe planning"
            ],
            Industry.INDUSTRIAL: [
                "Equipment consultation",
                "Technical support",
                "Solution design",
                "Project management"
            ],
            Industry.HEALTHCARE: [
                "Service consultation",
                "Appointment scheduling",
                "Health package advice",
                "Patient support"
            ],
            Industry.EDUCATION: [
                "Course consultation",
                "Learning pathway advice",
                "Enrollment support",
                "Student guidance"
            ],
            Industry.OTHER: [
                "General consultation",
                "Service advice",
                "Customer support",
                "Solution planning"
            ]
        }
        
        return capabilities_map.get(industry, ["General consultation"])
    
    def _get_error_response(self, language: Language, industry: Industry) -> str:
        """Get error response / Lấy phản hồi lỗi"""
        if language == Language.VIETNAMESE:
            return f"""
Xin lỗi, tôi đang gặp sự cố trong việc xử lý yêu cầu tư vấn {industry.value} của bạn.

Để được hỗ trợ tốt nhất, bạn có thể:
- Thử lại sau vài phút
- Liên hệ trực tiếp với bộ phận tư vấn
- Gửi email với yêu cầu cụ thể
- Mô tả yêu cầu chi tiết hơn

Tôi sẵn sàng hỗ trợ bạn khi hệ thống hoạt động trở lại!
"""
        else:
            return f"""
Sorry, I'm experiencing difficulties processing your {industry.value} consultation request.

For the best support, you can:
- Try again in a few minutes
- Contact the consultation department directly
- Send an email with specific requirements
- Provide more detailed request description

I'm ready to help you when the system is back online!
"""
