#!/usr/bin/env python3
"""
Test chat functionality for Ivy Fashion Store
Test chức năng chat cho Ivy Fashion Store
"""

import asyncio
import aiohttp
import json
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000"
COMPANY_ID = "ivy-fashion-store"

# Test queries về sản phẩm thời trang
TEST_QUERIES = [
    {"message": "Có áo blazer nào không?", "expected": "blazer"},
    {"message": "Tôi muốn xem các mẫu đầm dự tiệc", "expected": "đầm"},
    {
        "message": "Giá của áo Cotton Tweed Jacket màu be là bao nhiêu?",
        "expected": "1,380,000",
    },
    {"message": "Có sản phẩm nào dưới 1 triệu không?", "expected": "price"},
    {"message": "Chính sách đổi trả như thế nào?", "expected": "policy"},
]


async def test_unified_chat():
    """Test unified chat endpoint"""

    print("💬 TESTING UNIFIED CHAT FOR IVY FASHION")
    print("=" * 60)

    async with aiohttp.ClientSession() as session:
        for i, test in enumerate(TEST_QUERIES, 1):
            print(f"\n🔍 Test {i}: {test['message']}")

            # Prepare request
            chat_request = {
                "company_id": COMPANY_ID,
                "industry": "fashion",
                "message": test["message"],
                "language": "vi",
                "session_id": f"test_session_{datetime.now().timestamp()}",
                "user_id": "test_user",
            }

            try:
                # Send chat request
                async with session.post(
                    f"{BASE_URL}/api/unified/chat",
                    json=chat_request,
                    headers={"Content-Type": "application/json"},
                ) as response:

                    if response.status == 200:
                        data = await response.json()

                        print(f"✅ Response received")
                        print(f"   Intent: {data.get('intent', 'N/A')}")
                        print(f"   Confidence: {data.get('confidence', 0):.2f}")
                        print(f"   Language: {data.get('language', 'N/A')}")
                        print(
                            f"   Response preview: {data.get('response', '')[:150]}..."
                        )

                        # Check if response contains expected content
                        response_text = data.get("response", "").lower()
                        if test["expected"].lower() in response_text:
                            print(f"   ✅ Found expected content: {test['expected']}")
                        else:
                            print(
                                f"   ⚠️ Expected content not found: {test['expected']}"
                            )

                        # Show sources if available
                        sources = data.get("sources", [])
                        if sources:
                            print(f"   📚 Sources: {len(sources)} documents")
                            for src in sources[:2]:
                                print(
                                    f"      - {src.get('title', 'N/A')}: {src.get('relevance_score', 0):.2f}"
                                )

                        # Show suggestions
                        suggestions = data.get("suggestions", [])
                        if suggestions:
                            print(f"   💡 Suggestions: {', '.join(suggestions[:3])}")

                    else:
                        print(f"❌ Error: Status {response.status}")
                        error_text = await response.text()
                        print(f"   Details: {error_text[:200]}")

            except Exception as e:
                print(f"❌ Request failed: {str(e)}")

            # Small delay between requests
            await asyncio.sleep(1)


async def test_streaming_chat():
    """Test streaming chat endpoint"""

    print("\n\n📡 TESTING STREAMING CHAT")
    print("=" * 60)

    chat_request = {
        "company_id": COMPANY_ID,
        "industry": "fashion",
        "message": "Kể cho tôi nghe về bộ sưu tập mùa hè của IVY Fashion",
        "language": "vi",
        "session_id": f"stream_test_{datetime.now().timestamp()}",
        "user_id": "test_user",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BASE_URL}/api/unified/chat-stream",
                json=chat_request,
                headers={"Content-Type": "application/json"},
            ) as response:

                if response.status == 200:
                    print("✅ Streaming started")

                    # Read streaming response
                    full_response = ""
                    async for line in response.content:
                        line = line.decode("utf-8").strip()
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                if data["type"] == "content":
                                    print(data["chunk"], end="", flush=True)
                                    full_response += data["chunk"]
                                elif data["type"] == "done":
                                    print(f"\n\n✅ Streaming completed")
                                    print(f"   Session ID: {data.get('session_id')}")
                                elif data["type"] == "error":
                                    print(f"\n❌ Stream error: {data.get('error')}")
                            except json.JSONDecodeError:
                                pass
                else:
                    print(f"❌ Streaming error: Status {response.status}")

    except Exception as e:
        print(f"❌ Streaming failed: {str(e)}")


async def main():
    """Run all tests"""

    # Test normal chat
    await test_unified_chat()

    # Test streaming chat
    await test_streaming_chat()

    print("\n\n✨ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
