#!/usr/bin/env python3
"""
Simple API test với timeout ngắn
"""

import requests
import json
import time


def test_simple_chat():
    """Test đơn giản với AIA"""
    print("🧪 SIMPLE CHAT TEST")
    print("=" * 30)

    url = "http://localhost:8000/api/unified/chat-stream"

    payload = {
        "message": "AIA có những sản phẩm gì?",
        "company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
        "industry": "insurance",
        "user_info": {
            "user_id": "test_user",
            "device_id": "test_device",
            "name": "Test User",
        },
        "session_id": "test_simple",
        "language": "vietnamese",
    }

    headers = {
        "Content-Type": "application/json",
        "X-Company-Id": payload["company_id"],
    }

    print(f"📤 Sending request...")
    print(f"   Message: {payload['message']}")
    print(f"   Company: AIA")

    try:
        start_time = time.time()
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        end_time = time.time()

        print(f"⏱️  Response time: {end_time - start_time:.2f}s")
        print(f"📊 Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()

            print(f"\n✅ SUCCESS!")
            print(f"   Intent: {result.get('intent')}")
            print(f"   Language: {result.get('language')}")
            print(f"   Sources: {len(result.get('sources', []))}")

            answer = result.get("answer", "No answer")
            print(f"\n💬 Answer ({len(answer)} chars):")
            print(f"   {answer[:200]}{'...' if len(answer) > 200 else ''}")

            if result.get("sources"):
                print(f"\n📚 Sources:")
                for i, source in enumerate(result["sources"][:2], 1):
                    title = source.get("title", "No title")
                    print(f"   {i}. {title}")

        else:
            print(f"❌ Failed: {response.status_code}")
            print(f"   {response.text}")

    except requests.exceptions.Timeout:
        print(f"⏰ Request timeout (60s)")
    except Exception as e:
        print(f"❌ Error: {e}")


def test_intent_only():
    """Test intent detection riêng"""
    print(f"\n🎯 INTENT TEST")
    print("=" * 30)

    url = "http://localhost:8000/api/unified/detect-intent"

    payload = {
        "message": "Tôi muốn mua bảo hiểm AIA",
        "company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
        "industry": "insurance",
    }

    try:
        response = requests.post(url, json=payload, timeout=15)

        if response.status_code == 200:
            result = response.json()
            intent = result["intent_detection"]

            print(
                f"✅ Intent: {intent['intent']} (confidence: {intent['confidence']:.2f})"
            )
            print(f"   Reasoning: {intent['reasoning']}")
        else:
            print(f"❌ Failed: {response.status_code}")

    except Exception as e:
        print(f"❌ Error: {e}")


def test_curl_command():
    """Generate curl command for manual testing"""
    print(f"\n🔧 CURL COMMAND FOR MANUAL TEST")
    print("=" * 50)

    curl_cmd = """curl -X POST http://localhost:8000/api/unified/chat-stream \\
  -H "Content-Type: application/json" \\
  -H "X-Company-Id: 9a974d00-1a4b-4d5d-8dc3-4b5058255b8f" \\
  -d '{
    "message": "AIA có những sản phẩm bảo hiểm nào?",
    "company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
    "industry": "insurance",
    "user_info": {
      "user_id": "test_user",
      "device_id": "test_device",
      "name": "Test User"
    },
    "session_id": "curl_test",
    "language": "vietnamese"
  }'
"""

    print(curl_cmd)
    print(f"\n📋 Copy và chạy command trên để test manual!")


if __name__ == "__main__":
    # Test intent trước (nhanh)
    test_intent_only()

    # Test chat đầy đủ
    test_simple_chat()

    # Show curl command
    test_curl_command()
