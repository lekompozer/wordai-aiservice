#!/usr/bin/env python3
"""
Test script for /api/unified/chat-stream endpoint
Kiểm tra endpoint chat stream với comprehensive hybrid search
"""

import asyncio
import httpx
import json
from datetime import datetime


async def test_chat_stream_endpoint():
    """Test the optimized chat stream endpoint"""

    # Test data
    test_request = {
        "message": "Tôi muốn hỏi về sản phẩm bảo hiểm của công ty",
        "company_id": "abc_insurance_001",
        "industry": "insurance",
        "language": "vietnamese",
        "session_id": f"test_session_{int(datetime.now().timestamp())}",
        "user_info": {
            "user_id": "test_user_001",
            "name": "Test User",
            "device_id": "test_device_001",
            "source": "chatdemo",
        },
        "context": {},
    }

    print("🚀 Testing /api/unified/chat-stream endpoint...")
    print(f"📝 Request data: {json.dumps(test_request, indent=2, ensure_ascii=False)}")
    print("=" * 80)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Send streaming request
            async with client.stream(
                "POST",
                "http://localhost:8000/api/unified/chat-stream",
                json=test_request,
                headers={
                    "Content-Type": "application/json",
                    "X-Company-Id": "abc_insurance_001",  # Test header
                },
            ) as response:

                print(f"📡 Response status: {response.status_code}")
                print(f"📡 Response headers: {dict(response.headers)}")
                print("=" * 80)
                print("📤 Streaming response:")
                print("=" * 80)

                chunk_count = 0
                full_response = ""

                async for chunk in response.aiter_text():
                    if chunk.strip():
                        chunk_count += 1
                        print(f"[Chunk {chunk_count}] {chunk}")

                        # Try to parse as SSE data
                        if chunk.startswith("data: "):
                            try:
                                data = json.loads(chunk[6:])  # Remove "data: " prefix
                                if data.get("type") == "content":
                                    full_response += data.get("content", "")
                                elif data.get("type") == "done":
                                    print("✅ Stream completed successfully!")
                            except json.JSONDecodeError:
                                pass

                print("=" * 80)
                print(f"📊 Total chunks received: {chunk_count}")
                print(f"📝 Full response length: {len(full_response)} characters")
                if full_response:
                    print("📄 Full response:")
                    print("-" * 40)
                    print(full_response)
                    print("-" * 40)

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


async def test_chat_stream_validation():
    """Test endpoint validation"""

    print("\n🔍 Testing endpoint validation...")

    # Test cases
    test_cases = [
        {
            "name": "Missing company_id",
            "data": {"message": "Test message", "industry": "insurance"},
        },
        {
            "name": "Empty message",
            "data": {
                "message": "",
                "company_id": "test_company",
                "industry": "insurance",
            },
        },
        {
            "name": "Missing message field",
            "data": {"company_id": "test_company", "industry": "insurance"},
        },
    ]

    for test_case in test_cases:
        print(f"\n🧪 Testing: {test_case['name']}")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "http://localhost:8000/api/unified/chat-stream",
                    json=test_case["data"],
                )

                print(f"   Status: {response.status_code}")
                if response.status_code != 200:
                    print(f"   Error: {response.json()}")
                else:
                    print("   ⚠️ Expected validation error but got 200")

        except Exception as e:
            print(f"   Exception: {e}")


async def main():
    """Run all tests"""
    print("=" * 80)
    print("TESTING /api/unified/chat-stream ENDPOINT")
    print("=" * 80)

    # Test basic functionality
    await test_chat_stream_endpoint()

    # Test validation
    await test_chat_stream_validation()

    print("\n✅ All tests completed!")
    print("\n📂 Check /logs/prompt/ directory for prompt logs")


if __name__ == "__main__":
    asyncio.run(main())
