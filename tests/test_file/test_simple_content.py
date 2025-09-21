#!/usr/bin/env python3
"""
Test simple content generation
Test generate content đơn giản trước
"""
import sys

# Add src to path
sys.path.append("src")

from core.config import APP_CONFIG


def test_simple_content_generation():
    """Test simple content generation"""
    print("🧪 TESTING SIMPLE CONTENT GENERATION")
    print("=" * 50)

    try:
        from google import genai
        from google.genai import types

        # Get API key
        api_key = APP_CONFIG.get("gemini_api_key")
        client = genai.Client(api_key=api_key)

        # Test 1: Simple text only
        print("📝 Test 1: Simple text content")
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[
                types.Content(
                    role="user", parts=[types.Part(text="Hello, how are you?")]
                )
            ],
        )
        print(f"✅ Text response: {response.text[:100]}...")

        # Test 2: Without Content wrapper
        print("\n📝 Test 2: Direct string content")
        response2 = client.models.generate_content(
            model="gemini-2.5-flash-lite", contents="What is the capital of Vietnam?"
        )
        print(f"✅ Direct response: {response2.text[:100]}...")

        # Test 3: Different Content structure
        print("\n📝 Test 3: Alternative Content structure")
        response3 = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[
                {"role": "user", "parts": [{"text": "Explain Python in Vietnamese"}]}
            ],
        )
        print(f"✅ Alternative response: {response3.text[:100]}...")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        print(f"🔍 Error type: {type(e)}")


if __name__ == "__main__":
    test_simple_content_generation()
