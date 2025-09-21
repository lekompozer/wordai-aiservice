#!/usr/bin/env python3
"""
Test script to verify hard-coded values have been replaced with configuration
"""
import asyncio
import json
from src.ai_sales_agent.services.ai_provider import AISalesAgentProvider
from src.providers.ai_provider_manager import AIProviderManager
from src.api.loan_routes import calculate_interest_rate

async def test_ai_provider_config():
    """Test AI provider with config support"""
    print("🧪 Testing AI Provider with configuration...")
    
    ai_manager = AIProviderManager()
    provider = AISalesAgentProvider(ai_manager)
    
    # Test config with custom bank name
    config = {
        "bankName": "ABC Bank",
        "unsecuredInterestRate": 20.0,
        "mortgageRateFirstYear": 6.0,
        "mortgageRateAfterYear": 9.0
    }
    
    current_data = {
        "loanAmount": 500000000,
        "loanType": "Tín chấp"
    }
    
    try:
        result = await provider.process_message_combined(
            user_message="Tôi tên Nguyễn Văn A, 30 tuổi",
            current_data=current_data,
            message_count=1,
            context=None,
            config=config
        )
        
        print("✅ AI Provider test completed")
        print(f"   Bank name in metadata: {result.get('metadata', {}).get('bankName', 'Not found')}")
        print(f"   Config passed: {result.get('metadata', {}).get('config', 'Not found')}")
        
    except Exception as e:
        print(f"❌ AI Provider test failed: {e}")

def test_interest_rate_calculation():
    """Test interest rate calculation function"""
    print("\n🧪 Testing Interest Rate Calculation...")
    
    # Test unsecured loan
    rate1 = calculate_interest_rate("Tín chấp", None)
    print(f"   Unsecured loan (default): {rate1}%")
    
    # Test secured loan
    rate2 = calculate_interest_rate("Thế chấp", None)
    print(f"   Secured loan (default): {rate2}%")
    
    # Test with custom config
    config = {
        "unsecuredInterestRate": 15.0,
        "mortgageRateFirstYear": 4.5,
        "mortgageRateAfterYear": 7.8
    }
    
    rate3 = calculate_interest_rate("Tín chấp", config)
    print(f"   Unsecured loan (custom config): {rate3}%")
    
    rate4 = calculate_interest_rate("Thế chấp", config)
    print(f"   Secured loan (custom config): {rate4}%")
    
    # Test unknown loan type
    rate5 = calculate_interest_rate("Unknown", config)
    print(f"   Unknown loan type (fallback): {rate5}%")
    
    print("✅ Interest rate calculation tests completed")

async def main():
    """Run all tests"""
    print("🚀 Starting Configuration Tests...\n")
    
    # Test interest rate calculation
    test_interest_rate_calculation()
    
    # Test AI provider (comment out if no API key)
    # await test_ai_provider_config()
    
    print("\n🎉 All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())
