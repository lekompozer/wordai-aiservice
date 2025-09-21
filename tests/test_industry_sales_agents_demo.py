"""
Demo test for Industry-specific Sales Agents
Test demo cho các Sales Agent chuyên biệt theo ngành
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any

from src.models.unified_models import (
    UnifiedChatRequest, Language, Industry
)
from src.services.unified_chat_service import unified_chat_service

async def test_industry_sales_agents():
    """Test all industry-specific sales agents / Test tất cả sales agent chuyên biệt theo ngành"""
    
    print("🎯 Testing Industry-Specific Sales Agents")
    print("=" * 60)
    
    # Test cases for different industries / Test case cho các ngành khác nhau
    test_cases = [
        {
            "industry": Industry.BANKING,
            "company_id": "bank_001",
            "message": "Tôi muốn vay mua nhà 2 tỷ đồng, thời hạn 20 năm",
            "language": Language.VIETNAMESE,
            "description": "Banking - Home loan inquiry in Vietnamese"
        },
        {
            "industry": Industry.RESTAURANT, 
            "company_id": "rest_001",
            "message": "I'd like to book a table for 4 people tonight at 7 PM",
            "language": Language.ENGLISH,
            "description": "Restaurant - Table booking in English"
        },
        {
            "industry": Industry.RETAIL,
            "company_id": "retail_001", 
            "message": "Tôi cần tư vấn laptop cho sinh viên, ngân sách khoảng 15 triệu",
            "language": Language.VIETNAMESE,
            "description": "Retail - Laptop consultation in Vietnamese"
        },
        {
            "industry": Industry.HOTEL,
            "company_id": "hotel_001",
            "message": "I need a room for 2 guests from Dec 15-18, preferably with ocean view",
            "language": Language.ENGLISH,
            "description": "Hotel - Room booking in English"
        },
        {
            "industry": Industry.INSURANCE,
            "company_id": "ins_001",
            "message": "Tôi muốn tham gia bảo hiểm y tế cho gia đình 4 người",
            "language": Language.VIETNAMESE,
            "description": "Insurance - Health insurance inquiry in Vietnamese"
        },
        {
            "industry": Industry.FASHION,
            "company_id": "fashion_001",
            "message": "Can you help me choose an outfit for a business meeting?",
            "language": Language.ENGLISH,
            "description": "Fashion - Business outfit consultation in English"
        },
        {
            "industry": Industry.INDUSTRIAL,
            "company_id": "ind_001",
            "message": "Chúng tôi cần thiết bị sản xuất cho nhà máy thực phẩm",
            "language": Language.VIETNAMESE,
            "description": "Industrial - Food production equipment in Vietnamese"
        },
        {
            "industry": Industry.HEALTHCARE,
            "company_id": "health_001",
            "message": "I'd like to schedule a comprehensive health checkup",
            "language": Language.ENGLISH,
            "description": "Healthcare - Health checkup appointment in English"
        },
        {
            "industry": Industry.EDUCATION,
            "company_id": "edu_001",
            "message": "Tôi muốn đăng ký khóa học lập trình Python",
            "language": Language.VIETNAMESE,
            "description": "Education - Python course enrollment in Vietnamese"
        },
        {
            "industry": Industry.OTHER,
            "company_id": "other_001",
            "message": "What services do you provide for legal consultation?",
            "language": Language.ENGLISH,
            "description": "Other - Legal consultation services in English"
        }
    ]
    
    # Test each industry / Test từng ngành
    for i, case in enumerate(test_cases, 1):
        print(f"\n📋 Test {i}: {case['description']}")
        print(f"🏢 Industry: {case['industry'].value}")
        print(f"🏭 Company: {case['company_id']}")
        print(f"🗣️ Language: {case['language'].value}")
        print(f"💬 Message: {case['message']}")
        print("-" * 50)
        
        try:
            # Create request / Tạo request
            request = UnifiedChatRequest(
                message=case['message'],
                session_id=f"test_session_{i}",
                user_id="demo_user",
                industry=case['industry'],
                company_id=case['company_id'],
                user_language=case['language']
            )
            
            # Process with unified chat service / Xử lý với unified chat service
            response = await unified_chat_service.process_message(request)
            
            # Display response / Hiển thị phản hồi
            print(f"✅ Response:")
            print(f"   Intent: {response.intent}")
            print(f"   Language: {response.response_language}")
            print(f"   Agent: {response.metadata.get('agent_type', 'unknown')}")
            print(f"   Content: {response.response[:200]}...")
            
            if response.metadata.get('transaction_code'):
                print(f"   🎫 Transaction Code: {response.metadata['transaction_code']}")
            
            if response.confidence:
                print(f"   🎯 Confidence: {response.confidence}")
            
        except Exception as e:
            print(f"❌ Error testing {case['description']}: {e}")
        
        print()
    
    print("🎉 Industry Sales Agent Testing Complete!")

async def test_sales_agent_manager():
    """Test SalesAgentManager directly / Test SalesAgentManager trực tiếp"""
    
    print("\n🔧 Testing SalesAgentManager Directly")
    print("=" * 50)
    
    # Import and initialize / Import và khởi tạo
    from src.providers.ai_provider_manager import AIProviderManager
    from src.services.industry_sales_agents import SalesAgentManager
    from src.core.config import APP_CONFIG
    
    # Initialize AI manager / Khởi tạo AI manager
    ai_manager = AIProviderManager(
        deepseek_api_key=APP_CONFIG.get('deepseek_api_key'),
        chatgpt_api_key=APP_CONFIG.get('chatgpt_api_key')
    )
    
    # Initialize sales agent manager / Khởi tạo sales agent manager
    sales_manager = SalesAgentManager(ai_manager)
    
    # Test banking agent / Test banking agent
    banking_result = await sales_manager.process_sales_inquiry(
        message="I need a business loan for 500,000 USD for equipment purchase",
        industry=Industry.BANKING,
        company_id="test_bank",
        session_id="direct_test_1",
        language=Language.ENGLISH,
        company_context="Test Bank provides comprehensive financial services",
        user_id="test_user"
    )
    
    print("🏦 Banking Agent Result:")
    print(f"   Response: {banking_result['response'][:150]}...")
    print(f"   Industry: {banking_result['industry']}")
    print(f"   Agent Type: {banking_result['agent_type']}")
    print(f"   Confidence: {banking_result['confidence']}")
    
    # Test restaurant agent / Test restaurant agent
    restaurant_result = await sales_manager.process_sales_inquiry(
        message="Đặt bàn cho 6 người tối nay lúc 8 giờ, có không gian riêng tư",
        industry=Industry.RESTAURANT,
        company_id="test_restaurant",
        session_id="direct_test_2",
        language=Language.VIETNAMESE,
        company_context="Nhà hàng cao cấp chuyên món Á Âu",
        user_id="test_user"
    )
    
    print("\n🍽️ Restaurant Agent Result:")
    print(f"   Response: {restaurant_result['response'][:150]}...")
    print(f"   Industry: {restaurant_result['industry']}")
    print(f"   Agent Type: {restaurant_result['agent_type']}")
    print(f"   Confidence: {restaurant_result['confidence']}")
    
    # Test supported industries / Test các ngành được hỗ trợ
    supported = sales_manager.get_supported_industries()
    print(f"\n📋 Supported Industries ({len(supported)}):")
    for industry in supported:
        info = sales_manager.get_agent_info(industry)
        print(f"   - {industry.value}: {info['agent_type']} ({'Specialized' if info['specialized'] else 'Generic'})")

async def main():
    """Main demo function / Hàm demo chính"""
    print("🚀 Starting Industry Sales Agent Demo")
    print("=" * 60)
    
    # Test 1: Direct SalesAgentManager testing / Test 1: Test trực tiếp SalesAgentManager
    await test_sales_agent_manager()
    
    # Test 2: Full integration testing / Test 2: Test tích hợp đầy đủ
    await test_industry_sales_agents()
    
    print("\n✅ All tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
