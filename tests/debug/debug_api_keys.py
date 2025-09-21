"""
Debug API key loading for AI Sales Agent
"""

import sys
import os
sys.path.append('/Users/user/Code/ai-chatbot-rag')

from src.core.config import APP_CONFIG
from src.ai_sales_agent.utils.ai_helper import get_ai_provider_manager

def debug_api_keys():
    """Debug API key configuration"""
    
    print("🔧 DEBUGGING API KEY CONFIGURATION")
    print("=" * 60)
    
    # Check environment variables directly
    print("📋 ENVIRONMENT VARIABLES:")
    print(f"   DEEPSEEK_API_KEY: {os.getenv('DEEPSEEK_API_KEY', 'NOT SET')[:20]}...")
    print(f"   CHATGPT_API_KEY: {os.getenv('CHATGPT_API_KEY', 'NOT SET')[:20]}...")
    print(f"   DEFAULT_AI_PROVIDER: {os.getenv('DEFAULT_AI_PROVIDER', 'NOT SET')}")
    
    # Check APP_CONFIG
    print(f"\n📋 APP_CONFIG:")
    print(f"   deepseek_api_key: {APP_CONFIG.get('deepseek_api_key', 'NOT SET')[:20]}...")
    print(f"   chatgpt_api_key: {APP_CONFIG.get('chatgpt_api_key', 'NOT SET')[:20]}...")
    print(f"   default_ai_provider: {APP_CONFIG.get('default_ai_provider', 'NOT SET')}")
    
    # Test AI Manager initialization
    print(f"\n🤖 AI PROVIDER MANAGER TEST:")
    try:
        ai_manager = get_ai_provider_manager()
        if ai_manager:
            print(f"   ✅ AI Manager created successfully")
            print(f"   🔑 DeepSeek API Key: {ai_manager.deepseek_api_key[:20]}...")
            print(f"   🌐 DeepSeek URL: {ai_manager.deepseek_api_url}")
        else:
            print(f"   ❌ Failed to create AI Manager")
    except Exception as e:
        print(f"   ❌ Error creating AI Manager: {e}")
    
    # Test simple API call
    print(f"\n🧪 TEST API CALL:")
    try:
        import asyncio
        from src.ai_sales_agent.utils.ai_helper import get_ai_response
        
        async def test_call():
            try:
                response = await get_ai_response("Hello, test connection", provider="deepseek")
                print(f"   ✅ API Call successful: {response[:50]}...")
                return True
            except Exception as e:
                print(f"   ❌ API Call failed: {e}")
                return False
        
        # Run test
        success = asyncio.run(test_call())
        
    except Exception as e:
        print(f"   ❌ Test setup failed: {e}")

if __name__ == "__main__":
    debug_api_keys()
