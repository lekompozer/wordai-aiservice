#!/usr/bin/env python3
"""
Simple test of Cerebras API integration
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_cerebras_api():
    """Test Cerebras API directly"""
    print("🧠 SIMPLE CEREBRAS API TEST")
    print("=" * 40)

    try:
        from src.clients.cerebras_client import CerebrasClient

        # Initialize client
        api_key = "csk-6535mtwp6j9v6f9825eewe432rc4j24xrcrw6tj5m2cx5f32"
        client = CerebrasClient(api_key)

        # Test simple question
        messages = [
            {
                "role": "user",
                "content": "Xin chào! Bạn có thể giới thiệu về AIA Việt Nam trong 2-3 câu không?",
            }
        ]

        print("✅ Testing non-streaming completion...")
        response = await client.chat_completion(messages)
        print(f"Response: {response}")

        print("\n✅ Testing streaming completion...")
        chunks = []
        async for chunk in client.chat_completion_stream(messages):
            chunks.append(chunk)
            print(chunk, end="", flush=True)

        print(f"\n\nStream complete! Total chunks: {len(chunks)}")
        print("🎉 CEREBRAS API TEST SUCCESSFUL!")
        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_cerebras_api())
    sys.exit(0 if success else 1)
