#!/usr/bin/env python3
"""
Test Unified Chat API Endpoints
Test các endpoint API unified chat trực tiếp
"""

import requests
import json
import time
import asyncio
from typing import Dict, Any

BASE_URL = "http://localhost:8000"


def test_unified_chat_api():
    """Test unified chat endpoint với AIA company"""
    print("🚀 TESTING UNIFIED CHAT API")
    print("=" * 50)

    # Test data cho AIA company
    test_payload = {
        "message": "Hãy cho tôi biết về công ty AIA Việt Nam và các sản phẩm bảo hiểm",
        "company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",  # AIA company ID
        "industry": "insurance",
        "user_info": {
            "user_id": "test_user_api",
            "device_id": "test_device_api",
            "name": "API Test User",
            "source": "chatdemo",
        },
        "session_id": "test_session_api_001",
        "language": "vietnamese",
    }

    print(f"📦 Request payload:")
    print(f"   Company: {test_payload['company_id']}")
    print(f"   Industry: {test_payload['industry']}")
    print(f"   Message: {test_payload['message']}")
    print(f"   User: {test_payload['user_info']['user_id']}")

    try:
        # Test unified chat streaming endpoint
        print(f"\n🔗 Testing: POST {BASE_URL}/api/unified/chat-stream")

        headers = {
            "Content-Type": "application/json",
            "X-Company-Id": test_payload["company_id"],  # Header cho frontend
        }

        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/unified/chat-stream",
            json=test_payload,
            headers=headers,
            timeout=30,
        )
        end_time = time.time()

        print(f"⏱️  Response time: {end_time - start_time:.2f}s")
        print(f"📊 Status code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()

            print(f"\n✅ SUCCESS - Response received:")
            print(f"   Status: {result.get('status', 'unknown')}")
            print(f"   Intent: {result.get('intent', 'unknown')}")
            print(f"   Confidence: {result.get('confidence', 0):.2f}")
            print(f"   Language: {result.get('language', 'unknown')}")
            print(f"   Sources: {len(result.get('sources', []))}")

            # Show answer
            answer = result.get("answer", "No answer")
            print(f"\n💬 Answer:")
            print(f"   {answer[:300]}{'...' if len(answer) > 300 else ''}")

            # Show sources if available
            if result.get("sources"):
                print(f"\n📚 RAG Sources ({len(result['sources'])}):")
                for i, source in enumerate(result["sources"][:3], 1):
                    title = source.get("title", "No title")
                    content_type = source.get("content_type", "unknown")
                    score = source.get("score", 0)
                    print(f"   {i}. {title} ({content_type}) - Score: {score:.3f}")

            return True

        else:
            print(f"\n❌ FAILED - Status: {response.status_code}")
            try:
                error_detail = response.json()
                print(f"   Error: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"   Error: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"\n❌ REQUEST ERROR: {e}")
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        return False


def test_unified_chat_stream():
    """Test streaming endpoint"""
    print(f"\n🌊 TESTING STREAMING ENDPOINT")
    print("=" * 50)

    stream_payload = {
        "message": "Cho tôi biết chi tiết về các sản phẩm bảo hiểm sức khỏe của AIA",
        "company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
        "industry": "insurance",
        "user_info": {
            "user_id": "test_user_stream",
            "device_id": "test_device_stream",
            "name": "Stream Test User",
            "source": "chatdemo",
        },
        "session_id": "test_session_stream_001",
        "language": "vietnamese",
    }

    try:
        print(f"🔗 Testing: POST {BASE_URL}/api/unified/chat-stream")

        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}

        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/unified/chat-stream",
            json=stream_payload,
            headers=headers,
            stream=True,
            timeout=30,
        )

        print(f"📊 Status code: {response.status_code}")

        if response.status_code == 200:
            print(f"\n🌊 Streaming response:")
            print("   ", end="")

            chunk_count = 0
            for line in response.iter_lines():
                if line:
                    chunk_count += 1
                    # Show first few chunks
                    if chunk_count <= 10:
                        try:
                            decoded = line.decode("utf-8")
                            if decoded.startswith("data: "):
                                data = json.loads(decoded[6:])
                                if data.get("type") == "content":
                                    print(data.get("content", ""), end="", flush=True)
                                elif data.get("type") == "done":
                                    print(f"\n   ✅ Stream completed")
                                    sources = data.get("sources", [])
                                    if sources:
                                        print(f"   📚 Sources: {len(sources)}")
                                    break
                        except:
                            print(".", end="", flush=True)
                    else:
                        print(".", end="", flush=True)

                    # Limit output for demo
                    if chunk_count > 50:
                        print(f"\n   📊 Stream continues... (showing first 50 chunks)")
                        break

            end_time = time.time()
            print(f"\n⏱️  Total time: {end_time - start_time:.2f}s")
            print(f"📊 Total chunks: {chunk_count}")
            return True

        else:
            print(f"\n❌ STREAM FAILED - Status: {response.status_code}")
            return False

    except Exception as e:
        print(f"\n❌ STREAM ERROR: {e}")
        return False


def test_helper_endpoints():
    """Test các endpoint helper"""
    print(f"\n🔧 TESTING HELPER ENDPOINTS")
    print("=" * 50)

    endpoints = [
        "/api/unified/industries",
        "/api/unified/languages",
        "/api/unified/stats",
        "/api/unified/webhook/test",
    ]

    for endpoint in endpoints:
        try:
            print(f"\n🔗 Testing: GET {BASE_URL}{endpoint}")
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)

            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ Success - Keys: {list(result.keys())}")
            else:
                print(f"   ❌ Failed - Status: {response.status_code}")

        except Exception as e:
            print(f"   ❌ Error: {e}")


def test_intent_detection():
    """Test intent detection endpoint"""
    print(f"\n🎯 TESTING INTENT DETECTION")
    print("=" * 50)

    intent_payload = {
        "message": "Tôi muốn mua bảo hiểm sức khỏe cho gia đình",
        "company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
        "industry": "insurance",
        "language": "vietnamese",
    }

    try:
        print(f"🔗 Testing: POST {BASE_URL}/api/unified/detect-intent")
        print(f"   Message: {intent_payload['message']}")

        response = requests.post(
            f"{BASE_URL}/api/unified/detect-intent", json=intent_payload, timeout=15
        )

        if response.status_code == 200:
            result = response.json()

            lang_detection = result.get("language_detection", {})
            intent_detection = result.get("intent_detection", {})
            routing = result.get("suggested_routing", {})

            print(f"\n✅ Intent Detection Results:")
            print(
                f"   Language: {lang_detection.get('language')} (confidence: {lang_detection.get('confidence', 0):.2f})"
            )
            print(
                f"   Intent: {intent_detection.get('intent')} (confidence: {intent_detection.get('confidence', 0):.2f})"
            )
            print(f"   Reasoning: {intent_detection.get('reasoning', 'N/A')}")
            print(f"   Suggested Agent: {routing.get('agent', 'N/A')}")

        else:
            print(f"   ❌ Failed - Status: {response.status_code}")

    except Exception as e:
        print(f"   ❌ Error: {e}")


def main():
    """Run all API tests"""
    print("🧪 UNIFIED CHAT API TEST SUITE")
    print("🎯 Target: AIA Company with Cerebras AI")
    print("=" * 60)

    results = []

    # Test 1: Basic chat
    results.append(("Unified Chat", test_unified_chat_api()))

    # Test 2: Streaming
    results.append(("Chat Streaming", test_unified_chat_stream()))

    # Test 3: Intent detection
    results.append(("Intent Detection", test_intent_detection()))

    # Test 4: Helper endpoints
    test_helper_endpoints()

    # Summary
    print(f"\n📊 TEST RESULTS SUMMARY")
    print("=" * 60)

    total_tests = len(results)
    passed_tests = sum(1 for _, success in results if success)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {test_name}: {status}")

    print(f"\n🎯 Overall: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED! API is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the logs above.")

    return passed_tests == total_tests


if __name__ == "__main__":
    success = main()
    print(f"\n{'🚀 API READY FOR USE!' if success else '❌ API NEEDS ATTENTION'}")
