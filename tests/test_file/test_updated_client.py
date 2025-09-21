#!/usr/bin/env python3
"""
Test new updated Gemini client
Test client mới đã cập nhật
"""
import asyncio
import sys
import requests

# Add src to path
sys.path.append("src")

from core.config import APP_CONFIG


async def test_updated_gemini_client():
    """Test updated Gemini client"""
    print("🧪 TESTING UPDATED GEMINI CLIENT")
    print("=" * 50)

    try:
        from src.clients.gemini_client import GeminiClient

        # Get API key
        api_key = APP_CONFIG.get("gemini_api_key")
        if not api_key:
            print("❌ No Gemini API key found")
            return

        # Create Gemini client
        gemini_client = GeminiClient(api_key=api_key)
        print("✅ Gemini client created")

        # Test 1: Simple chat completion
        print("\n💬 Test 1: Simple chat completion")
        messages = [
            {
                "role": "user",
                "content": "Hello, how are you? Please respond in Vietnamese.",
            }
        ]

        response = await gemini_client.chat_completion(messages)
        print(f"✅ Chat response: {response[:200]}...")

        # Test 2: R2 file upload and analysis
        print("\n📄 Test 2: R2 file upload and analysis")
        r2_file_url = "https://static.agent8x.io.vn/company/1e789800-b402-41b0-99d6-2e8d494a3beb/files/d528420e-8119-45b5-b76e-fddcbe798ac3.docx"

        print(f"📥 Downloading R2 file...")
        response = requests.get(r2_file_url, timeout=30)
        response.raise_for_status()

        file_content = response.content
        print(f"✅ File downloaded: {len(file_content)} bytes")

        # Test upload_file_and_analyze
        print("🚀 Testing upload_file_and_analyze...")

        result = await gemini_client.upload_file_and_analyze(
            file_content=file_content,
            file_name="r2_test_file.docx",
            prompt="Hãy phân tích file này và trích xuất thông tin về sản phẩm, dịch vụ, giá cả. Trả lời bằng tiếng Việt.",
        )

        print("=" * 50)
        print("🎯 GEMINI CLIENT RESPONSE:")
        print("=" * 50)
        print(result)
        print("=" * 50)

        # Test 3: Streaming chat
        print("\n🌊 Test 3: Streaming chat")
        messages = [
            {
                "role": "user",
                "content": "Hãy giải thích về Python programming language bằng tiếng Việt, viết ngắn gọn",
            }
        ]

        print("Streaming response:")
        async for chunk in gemini_client.chat_completion_stream(messages):
            print(chunk, end="", flush=True)
        print("\n✅ Streaming completed")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        print(f"🔍 Error type: {type(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_updated_gemini_client())
