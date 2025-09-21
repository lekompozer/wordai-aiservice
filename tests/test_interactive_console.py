"""
Test console for flexible AI Sales Agent
Natural conversation with smart data extraction
"""
import asyncio
import sys
import os
from typing import Any
sys.path.append(os.path.join(os.path.dirname(__file__)))

from src.ai_sales_agent.services.ai_provider import AISalesAgentProvider
from src.ai_sales_agent.services.loan_assessment_client import LoanAssessmentClient
from src.ai_sales_agent.nlg.generator import NLGGenerator
from src.ai_sales_agent.utils.flexible_assessment import FlexibleAssessmentChecker, AssessmentReadiness
from src.providers.ai_provider_manager import AIProviderManager
from config.config import DEEPSEEK_API_KEY, CHATGPT_API_KEY

class FlexibleConsoleTest:
    def __init__(self):
        # Initialize components
        ai_manager = AIProviderManager(
            deepseek_api_key=DEEPSEEK_API_KEY,
            chatgpt_api_key=CHATGPT_API_KEY
        )
        self.ai_provider = AISalesAgentProvider(ai_manager)
        self.assessment_client = LoanAssessmentClient()
        self.nlg = NLGGenerator()
        self.flexible_checker = FlexibleAssessmentChecker()
        
        # Session data
        self.conversation_data = {}
        self.conversation_history = []
        
    def print_header(self, title: str):
        """Print formatted header"""
        print("\n" + "="*60)
        print(f"🏦 {title}")
        print("="*60)
    
    def print_readiness_status(self):
        """Print current readiness status"""
        readiness = self.flexible_checker.assess_readiness(self.conversation_data)
        
        print("\n📊 TÌNH TRẠNG DỮ LIỆU:")
        print("-" * 40)
        print(f"🎯 Mức độ: {readiness['readiness'].value.upper()}")
        print(f"📈 Điểm: {readiness['score']}/{readiness['max_possible_score']} ({readiness['completion_percentage']:.1f}%)")
        print(f"✅ Sẵn sàng thẩm định: {'CÓ' if readiness['can_proceed'] else 'CHƯA'}")
        
        if readiness['missing_critical']:
            print(f"\n🔥 Thiếu quan trọng: {', '.join(readiness['missing_critical'][:3])}")
        
        if readiness['recommendations']:
            print(f"\n💡 Gợi ý:")
            for rec in readiness['recommendations'][:2]:
                print(f"   • {rec}")
                
        return readiness
    
    def print_extracted_data(self, extracted: dict):
        """Print extracted data"""
        if not extracted:
            print("   • Không trích xuất được thông tin mới")
            return
            
        print("✅ Thông tin mới:")
        for field, value in extracted.items():
            vn_name = self.ai_provider._get_vietnamese_field_name(field)
            if field in ['loanAmount', 'collateralValue', 'monthlyIncome'] and isinstance(value, (int, float)):
                # Check for currency information
                currency = self.conversation_data.get('currency', 'VNĐ')
                if field == 'monthlyIncome' and 'incomeCurrency' in extracted:
                    currency = extracted['incomeCurrency']
                elif field == 'monthlyIncome' and 'currency' in extracted:
                    currency = extracted['currency']
                print(f"   • {vn_name}: {value:,} {currency}")
            else:
                print(f"   • {vn_name}: {value}")
    
    def print_current_data_summary(self):
        """Print summary of all collected data"""
        if not self.conversation_data:
            print("\n📋 Chưa có dữ liệu")
            return
            
        print("\n📋 DỮ LIỆU ĐÃ THU THẬP:")
        print("-" * 30)
        
        # Group by priority
        critical_fields = []
        important_fields = []
        other_fields = []
        
        for field, value in self.conversation_data.items():
            priority = self.ai_provider.field_priorities.get(field, 0)
            field_info = (field, value, priority)
            
            if priority >= 75:
                critical_fields.append(field_info)
            elif priority >= 50:
                important_fields.append(field_info)
            else:
                other_fields.append(field_info)
        
        # Print by groups
        if critical_fields:
            print("🔴 QUAN TRỌNG:")
            for field, value, _ in sorted(critical_fields, key=lambda x: x[2], reverse=True):
                self._print_field_value(field, value)
                
        if important_fields:
            print("\n🟡 CẦN THIẾT:")
            for field, value, _ in sorted(important_fields, key=lambda x: x[2], reverse=True):
                self._print_field_value(field, value)
                
        if other_fields:
            print("\n🟢 BỔ SUNG:")
            for field, value, _ in sorted(other_fields, key=lambda x: x[2], reverse=True):
                self._print_field_value(field, value)
    
    def _print_field_value(self, field: str, value: Any):
        """Print single field value"""
        vn_name = self.ai_provider._get_vietnamese_field_name(field)
        
        if field in ['loanAmount', 'collateralValue', 'monthlyIncome', 'totalDebtAmount'] and isinstance(value, (int, float)):
            # Check for currency information
            currency = self.conversation_data.get('currency', 'VNĐ')
            if field == 'monthlyIncome' and self.conversation_data.get('incomeCurrency'):
                currency = self.conversation_data.get('incomeCurrency')
            print(f"   • {vn_name}: {value:,} {currency}")
        else:
            print(f"   • {vn_name}: {value}")
    
    async def process_message(self, user_input: str) -> dict:
        """Process user message and extract information"""
        # Build context from history
        context = "\n".join([
            f"User: {h['user']}\nAI: {h['ai']}" 
            for h in self.conversation_history[-3:]
        ]) if self.conversation_history else None
        
        # Use combined processing
        message_count = len(self.conversation_history) + 1
        result = await self.ai_provider.process_message_combined(
            user_message=user_input,
            current_data=self.conversation_data,
            message_count=message_count,
            context=context
        )
        
        # Extract NLU data
        nlu_data = result.get("nlu", {})
        extracted_data = nlu_data.get("extractedData", {})
        
        # Update data
        if extracted_data:
            self.conversation_data.update(extracted_data)
            
        return {
            "extractedData": extracted_data,
            "confidence": nlu_data.get("confidence", 0.7),
            "ai_response": result.get("nlg", {}).get("response", "")
        }
    
    async def generate_response(self, user_input: str, extraction_result: dict) -> str:
        """Generate AI response"""
        # Get AI response from combined processing
        return extraction_result.get("ai_response", "")
    
    async def handle_assessment(self):
        """Handle loan assessment"""
        self.print_header("THẨM ĐỊNH HỒ SƠ VAY")
        
        print("🔄 Đang chuẩn bị dữ liệu...")
        
        # Prepare payload
        assessment_payload = self.nlg.prepare_assessment_payload(self.conversation_data)
        
        print("📊 Gọi API thẩm định...")
        
        try:
            # Call assessment API
            assessment_result = await self.assessment_client.assess_loan(assessment_payload)
            
            if not assessment_result.get("success"):
                print("⚠️ API không thành công, dùng mock...")
                assessment_result = self.assessment_client.create_mock_assessment_result(assessment_payload)
                
        except Exception as e:
            print(f"❌ Lỗi API: {e}")
            print("🎭 Dùng mock assessment...")
            assessment_result = self.assessment_client.create_mock_assessment_result(assessment_payload)
        
        # Format result
        formatted_result = self.nlg.format_assessment_result(assessment_result)
        
        print("\n🎉 KẾT QUẢ THẨM ĐỊNH:")
        print("=" * 60)
        print(formatted_result["question"])
        
        return assessment_result
    
    async def run(self):
        """Run flexible conversation test"""
        self.print_header("AI SALES AGENT - CHẾ ĐỘ HỘI THOẠI LINH HOẠT")
        
        print("\n🤖 Xin chào! Tôi là trợ lý tư vấn vay của VRB Bank.")
        print("💬 Anh/chị có thể nói chuyện tự nhiên với tôi.")
        print("📊 Tôi sẽ thu thập thông tin thông minh theo độ ưu tiên.")
        
        print("\n📌 Lệnh đặc biệt:")
        print("   • 'check': Kiểm tra tình trạng dữ liệu")
        print("   • 'summary': Xem tất cả dữ liệu đã thu thập")
        print("   • 'suggest': Gợi ý câu hỏi tiếp theo")
        print("   • 'assess': Tiến hành thẩm định (nếu đủ data)")
        print("   • 'quit': Thoát")
        
        # Initial greeting
        print("\n🤖 AI: Anh/chị đang cần tư vấn vay vốn phải không ạ? Không biết anh/chị đang cần vay vốn như nào?")
        
        while True:
            # Get user input
            user_input = input("\n👤 Bạn: ").strip()
            
            # Handle special commands
            if user_input.lower() == 'quit':
                print("👋 Cảm ơn anh/chị đã sử dụng dịch vụ!")
                break
                
            elif user_input.lower() == 'check':
                self.print_readiness_status()
                continue
                
            elif user_input.lower() == 'summary':
                self.print_current_data_summary()
                continue
                
            elif user_input.lower() == 'suggest':
                suggestions = self.flexible_checker.suggest_next_questions(self.conversation_data)
                if suggestions:
                    print("\n🧠 GỢI Ý CÂU HỎI:")
                    for i, q in enumerate(suggestions, 1):
                        print(f"   {i}. {q}")
                continue
                
            elif user_input.lower() == 'assess':
                readiness = self.flexible_checker.assess_readiness(self.conversation_data)
                if readiness['can_proceed']:
                    confirm = input("✅ Tiến hành thẩm định? (y/n): ")
                    if confirm.lower() == 'y':
                        await self.handle_assessment()
                        break
                else:
                    print("❌ Chưa đủ dữ liệu!")
                    print(f"🔥 Cần thêm: {', '.join(readiness['missing_critical'][:3])}")
                continue
            
            # Process normal message
            print("\n🔄 Đang xử lý...")
            
            # Extract information
            extraction_result = await self.process_message(user_input)
            
            # Show what was extracted
            extracted = extraction_result.get("extractedData", {})
            if extracted:
                self.print_extracted_data(extracted)
            
            # Generate response
            ai_response = await self.generate_response(user_input, extraction_result)
            
            print(f"\n🤖 AI: {ai_response}")
            
            # Update history
            self.conversation_history.append({
                "user": user_input,
                "ai": ai_response,
                "extracted": extracted
            })
            
            # Auto-check readiness after enough messages
            if len(self.conversation_history) > 5:
                readiness = self.flexible_checker.assess_readiness(self.conversation_data)
                if readiness['readiness'] == AssessmentReadiness.READY:
                    print("\n✅ Đã đủ thông tin để thẩm định!")
                    proceed = input("Tiến hành thẩm định ngay? (y/n): ")
                    if proceed.lower() == 'y':
                        await self.handle_assessment()
                        break

def main():
    """Main function"""
    try:
        test = FlexibleConsoleTest()
        asyncio.run(test.run())
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()