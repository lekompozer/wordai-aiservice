"""
Test config loading for API keys
"""

import sys
import os

sys.path.append("/Users/user/Code/ai-chatbot-rag/src")

from core.config import get_app_config


def test_config():
    config = get_app_config()

    print("🔍 CONFIG DEBUG:")
    print(f"Environment: {os.getenv('ENV', 'production')}")
    print(f"DeepSeek Key: {config.get('deepseek_api_key', 'NOT_FOUND')[:10]}...")
    print(f"ChatGPT Key: {config.get('chatgpt_api_key', 'NOT_FOUND')[:10]}...")
    print(f"Default Provider: {config.get('default_ai_provider', 'NOT_SET')}")
    print(
        f"API Available: {bool(config.get('deepseek_api_key') or config.get('chatgpt_api_key'))}"
    )

    # Check environment directly
    print("\n🌐 ENVIRONMENT VARIABLES:")
    print(f"DEEPSEEK_API_KEY: {os.getenv('DEEPSEEK_API_KEY', 'NOT_SET')[:10]}...")
    print(f"CHATGPT_API_KEY: {os.getenv('CHATGPT_API_KEY', 'NOT_SET')[:10]}...")
    print(f"DEFAULT_AI_PROVIDER: {os.getenv('DEFAULT_AI_PROVIDER', 'NOT_SET')}")


if __name__ == "__main__":
    test_config()
