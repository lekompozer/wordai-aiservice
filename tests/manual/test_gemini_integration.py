#!/usr/bin/env python3
"""
Test Gemini integration với các phương thức cơ bản:
- Chat completion
- Chat stream
- Chat with file stream
"""

import asyncio
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.providers.ai_provider_manager import AIProviderManager
from config.config import DEEPSEEK_API_KEY, CHATGPT_API_KEY, GEMINI_API_KEY


async def test_gemini_chat_completion():
    """Test basic Gemini chat completion"""
    print("🧪 Testing Gemini Chat Completion...")

    try:
        ai_manager = AIProviderManager(
            deepseek_api_key=DEEPSEEK_API_KEY,
            chatgpt_api_key=CHATGPT_API_KEY,
            gemini_api_key=GEMINI_API_KEY,
        )

        messages = [
            {
                "role": "user",
                "content": "Xin chào! Bạn có thể giới thiệu về bản thân không?",
            }
        ]

        response = await ai_manager.chat_completion(messages, provider="gemini")
        print(f"✅ Gemini Response: {response[:200]}...")
        return True

    except Exception as e:
        print(f"❌ Gemini chat completion failed: {e}")
        return False


async def test_gemini_chat_stream():
    """Test Gemini streaming chat"""
    print("\n🧪 Testing Gemini Chat Stream...")

    try:
        ai_manager = AIProviderManager(
            deepseek_api_key=DEEPSEEK_API_KEY,
            chatgpt_api_key=CHATGPT_API_KEY,
            gemini_api_key=GEMINI_API_KEY,
        )

        messages = [
            {
                "role": "user",
                "content": "Hãy liệt kê 5 lợi ích của việc sử dụng AI trong kinh doanh.",
            }
        ]

        print("✅ Gemini Stream Response:")
        async for chunk in ai_manager.chat_completion_stream_with_reasoning(
            messages, provider="gemini"
        ):
            print(chunk, end="", flush=True)
        print("\n")
        return True

    except Exception as e:
        print(f"❌ Gemini chat stream failed: {e}")
        return False


async def test_gemini_with_reasoning():
    """Test Gemini với reasoning"""
    print("\n🧪 Testing Gemini with Reasoning...")

    try:
        ai_manager = AIProviderManager(
            deepseek_api_key=DEEPSEEK_API_KEY,
            chatgpt_api_key=CHATGPT_API_KEY,
            gemini_api_key=GEMINI_API_KEY,
        )

        messages = [
            {
                "role": "user",
                "content": "Tại sao 2+2=4? Hãy giải thích từng bước một cách logic.",
            }
        ]

        print("✅ Gemini Reasoning Response:")
        async for chunk in ai_manager.chat_completion_stream_with_reasoning(
            messages, provider="gemini", use_reasoning=True
        ):
            print(chunk, end="", flush=True)
        print("\n")
        return True

    except Exception as e:
        print(f"❌ Gemini reasoning failed: {e}")
        return False


async def test_gemini_file_upload():
    """Test Gemini file upload with text content"""
    print("\n🧪 Testing Gemini File Upload...")

    try:
        ai_manager = AIProviderManager(
            deepseek_api_key=DEEPSEEK_API_KEY,
            chatgpt_api_key=CHATGPT_API_KEY,
            gemini_api_key=GEMINI_API_KEY,
        )

        # Create a sample CSV content
        csv_content = """product_name,price,category
iPhone 15,999,Electronics
Samsung Galaxy,799,Electronics
MacBook Pro,1999,Computers
iPad Air,599,Tablets"""

        file_content = csv_content.encode("utf-8")

        messages = [
            {
                "role": "user",
                "content": "Hãy phân tích file CSV này và cho biết có bao nhiêu sản phẩm, giá trung bình là bao nhiêu?",
            }
        ]

        print("✅ Gemini File Analysis:")
        async for chunk in ai_manager.chat_with_file_stream(
            messages, file_content, "sample_products.csv", provider="gemini"
        ):
            print(chunk, end="", flush=True)
        print("\n")
        return True

    except Exception as e:
        print(f"❌ Gemini file upload failed: {e}")
        return False


async def main():
    """Run all Gemini tests"""
    print("🚀 Starting Gemini Integration Tests...")

    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY not found in environment")
        return

    print(f"🔑 Using Gemini API Key: {GEMINI_API_KEY[:20]}...")

    tests = [
        test_gemini_chat_completion,
        test_gemini_chat_stream,
        test_gemini_with_reasoning,
        test_gemini_file_upload,
    ]

    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append(False)

    print(f"\n📊 Test Results: {sum(results)}/{len(results)} passed")

    if all(results):
        print("🎉 All Gemini tests passed! Integration successful!")
    else:
        print("⚠️ Some tests failed. Check the logs above.")


if __name__ == "__main__":
    asyncio.run(main())
