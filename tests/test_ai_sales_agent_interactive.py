#!/usr/bin/env python3
"""
Test AI Sales Agent language detection and bilingual responses
"""
import asyncio
import json
from src.ai_sales_agent.services.ai_provider import AISalesAgentProvider
from src.providers.ai_provider_manager import AIProviderManager
from src.core.config import APP_CONFIG

async def test_language_detection_and_response():
    """Test language detection and bilingual AI responses"""
    print("🧪 Testing AI Sales Agent Language Detection...\n")
    
    # Get API keys from config
    deepseek_key = APP_CONFIG.get("DEEPSEEK_API_KEY")
    chatgpt_key = APP_CONFIG.get("CHATGPT_API_KEY")
    
    if not deepseek_key:
        print("❌ DEEPSEEK_API_KEY not found in config")
        return
    
    # Initialize AI provider
    ai_manager = AIProviderManager(deepseek_key, chatgpt_key)
    provider = AISalesAgentProvider(ai_manager)
    
    # Test cases
    test_cases = [
        {
            "name": "English Input",
            "message": "I want to borrow 03 billion for 05 years",
            "expected_lang": "English",
            "current_data": {}
        },
        {
            "name": "Vietnamese Input", 
            "message": "Tôi muốn vay 2 tỷ trong 3 năm",
            "expected_lang": "Vietnamese",
            "current_data": {}
        },
        {
            "name": "Mixed English",
            "message": "Hello, I need a loan of 500 million VND",
            "expected_lang": "English", 
            "current_data": {}
        },
        {
            "name": "Follow-up English",
            "message": "My name is John Smith, 35 years old",
            "expected_lang": "English",
            "current_data": {"loanAmount": 3000000000, "loanTerm": 5}
        }
    ]
    
    # Test configuration with both languages
    config = {
        "bankName": "ABC Bank / Ngân hàng ABC",
        "unsecuredInterestRate": 18.0,
        "mortgageRateFirstYear": 5.0,
        "mortgageRateAfterYear": 8.5
    }
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"📝 Test {i}: {test_case['name']}")
        print(f"   Input: '{test_case['message']}'")
        
        try:
            # Test just language detection first
            is_english = provider._detect_english(test_case['message'])
            detected_lang = "English" if is_english else "Vietnamese"
            
            print(f"   Expected: {test_case['expected_lang']}")
            print(f"   Detected: {detected_lang}")
            
            if detected_lang == test_case['expected_lang']:
                print("   ✅ Language detection: PASSED")
            else:
                print("   ❌ Language detection: FAILED")
            
            # Test AI response
            print("   🤖 Testing AI response...")
            result = await provider.process_message_combined(
                user_message=test_case['message'],
                current_data=test_case['current_data'],
                message_count=1,
                context=None,
                config=config
            )
            
            if 'nlg' in result and 'response' in result['nlg']:
                response = result['nlg']['response']
                response_lang = result['metadata'].get('language', 'unknown')
                
                print(f"   Response language: {response_lang}")
                print(f"   Response: {response[:100]}...")
                
                # Check if response is in expected language
                response_is_english = provider._detect_english(response)
                actual_response_lang = "en" if response_is_english else "vi"
                expected_response_lang = "en" if test_case['expected_lang'] == "English" else "vi"
                
                if actual_response_lang == expected_response_lang:
                    print("   ✅ Response language: PASSED")
                else:
                    print("   ❌ Response language: FAILED")
                    print(f"      Expected: {expected_response_lang}, Got: {actual_response_lang}")
                    
            else:
                print("   ❌ No response generated")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print()

def test_bilingual_greeting():
    """Test bilingual greeting message"""
    print("🌐 Testing Bilingual Greeting...")
    
    bilingual_greeting = """
🏦 Chào mừng anh/chị đến với ABC Bank! / Welcome to ABC Bank!

Tôi là AI Assistant, sẵn sàng hỗ trợ anh/chị tư vấn vay vốn.
I'm your AI Assistant, ready to help you with loan consultation.

Anh/chị cần tư vấn vay vốn phải không? Hãy cho tôi biết nhu cầu của anh/chị.
Do you need loan consultation? Please let me know your requirements.
"""
    
    print(bilingual_greeting)
    return bilingual_greeting

async def main():
    """Run all tests"""
    print("🚀 Starting AI Sales Agent Language Tests...\n")
    
    # Test bilingual greeting
    test_bilingual_greeting()
    
    # Test language detection and responses
    await test_language_detection_and_response()
    
    print("🎉 All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())
