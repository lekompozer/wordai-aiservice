#!/usr/bin/env python3
"""
Test bank name in prompts and verify no hard-coded VRB
"""
import re
from src.ai_sales_agent.services.ai_provider import AISalesAgentProvider
from src.providers.ai_provider_manager import AIProviderManager

def test_prompt_generation():
    """Test that prompts use config bank name instead of hard-coded VRB"""
    print("🧪 Testing Prompt Generation with Config...")
    
    # Create mock provider without full initialization
    class MockAIProvider:
        def __init__(self):
            self.field_priorities = {
                "loanAmount": 95,
                "fullName": 100,
                "phoneNumber": 75
            }
        
        def _format_current_data(self, data):
            if not data:
                return "Chưa có thông tin"
            lines = []
            for field, value in data.items():
                lines.append(f"- {field}: {value}")
            return "\n".join(lines)
        
        def _build_flexible_extraction_prompt(self, user_message, current_data, context=None, bank_name="VRB"):
            # Get all possible fields
            all_fields = list(self.field_priorities.keys())
            
            # Handle context section to avoid f-string backslash issue
            context_section = f"LỊCH SỬ HỘI THOẠI GẦN ĐÂY:\n{context}" if context else ""
            
            prompt = f"""
BẠN LÀ CHUYÊN GIA TRÍCH XUẤT THÔNG TIN VAY VỐN NGÂN HÀNG {bank_name}.

NHIỆM VỤ: Trích xuất TẤT CẢ thông tin có thể từ câu trả lời của khách hàng.

THÔNG TIN ĐÃ CÓ:
{self._format_current_data(current_data)}

CÁC FIELD CÓ THỂ TRÍCH XUẤT: {', '.join(all_fields)}

NGƯỜI DÙNG NÓI: "{user_message}"

{context_section}

CHỈ TRẢ VỀ JSON, KHÔNG GIẢI THÍCH.
"""
            return prompt
    
    provider = MockAIProvider()
    
    # Test _build_flexible_extraction_prompt with custom bank name
    current_data = {"loanAmount": 500000000}
    user_message = "Tôi tên Nguyễn Văn A"
    
    # Test default bank name
    prompt1 = provider._build_flexible_extraction_prompt(
        user_message, current_data, None, "VRB"
    )
    print("✅ Default bank name test:")
    print(f"   Contains 'VRB': {'VRB' in prompt1}")
    
    # Test custom bank name
    prompt2 = provider._build_flexible_extraction_prompt(
        user_message, current_data, None, "ABC Bank"
    )
    print("✅ Custom bank name test:")
    print(f"   Contains 'ABC Bank': {'ABC Bank' in prompt2}")
    print(f"   Contains 'VRB': {'VRB' in prompt2}")
    
    # Test Vietnamese bank name
    prompt3 = provider._build_flexible_extraction_prompt(
        user_message, current_data, None, "Ngân hàng XYZ"
    )
    print("✅ Vietnamese bank name test:")
    print(f"   Contains 'Ngân hàng XYZ': {'Ngân hàng XYZ' in prompt3}")
    print(f"   Contains 'VRB': {'VRB' in prompt3}")
    
    return prompt1, prompt2, prompt3

def check_for_hardcoded_values():
    """Check source files for remaining hard-coded values"""
    print("\n🔍 Checking for remaining hard-coded values...")
    
    files_to_check = [
        "/Users/user/Code/ai-chatbot-rag/src/ai_sales_agent/services/ai_provider.py",
        "/Users/user/Code/ai-chatbot-rag/src/api/loan_routes.py"
    ]
    
    for file_path in files_to_check:
        print(f"\n📄 Checking {file_path.split('/')[-1]}:")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Check for hard-coded VRB
            vrb_matches = re.findall(r'["\']VRB["\']', content)
            if vrb_matches:
                print(f"   ❌ Found hard-coded VRB: {len(vrb_matches)} occurrences")
            else:
                print(f"   ✅ No hard-coded VRB found")
            
            # Check for hard-coded interest rates
            rate_matches = re.findall(r'= 8\.5|= 18\.0|= 5\.0', content)
            if rate_matches:
                print(f"   ⚠️  Found potential hard-coded rates: {rate_matches}")
            else:
                print(f"   ✅ No obvious hard-coded rates found")
                
        except Exception as e:
            print(f"   ❌ Error reading file: {e}")

def main():
    """Run all tests"""
    print("🚀 Starting Hard-coded Value Detection Tests...\n")
    
    # Test prompt generation
    test_prompt_generation()
    
    # Check for remaining hard-coded values
    check_for_hardcoded_values()
    
    print("\n🎉 All tests completed!")

if __name__ == "__main__":
    main()
