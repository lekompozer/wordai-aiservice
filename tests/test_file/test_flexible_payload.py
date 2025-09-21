#!/usr/bin/env python3
"""
Test flexible payload validation for unified chat API
Kiểm tra tính linh hoạt của API chat với các định dạng payload khác nhau
"""

import json
import requests
import time

# Test endpoint
BASE_URL = "https://ai.aimoney.io.vn"
# For local testing, use: BASE_URL = "http://localhost:8000"


def debug_chat_stream_endpoint():
    """Debug the exact chat-stream endpoint that's failing"""
    print("🔍 Debugging chat-stream endpoint")
    print("=" * 50)

    # Test the exact endpoint that's failing in production
    url = f"{BASE_URL}/api/unified/chat-stream"

    # Test different payload variations to see what works
    test_payloads = [
        {
            "name": "Minimal + industry",
            "payload": {
                "company_id": "test-company-001",
                "message": "Xin chào",
                "industry": "other",
            },
        },
        {
            "name": "With basic user_info",
            "payload": {
                "company_id": "test-company-001",
                "message": "Xin chào",
                "industry": "other",
                "user_info": {
                    "user_id": "test_user",
                    "source": "chatdemo",
                    "device_id": "test_device",
                },
            },
        },
        {
            "name": "Full compatible payload",
            "payload": {
                "company_id": "test-company-001",
                "message": "Xin chào, tôi cần hỗ trợ",
                "industry": "banking",
                "language": "vi",
                "user_info": {
                    "user_id": "authenticated_user_123",
                    "source": "chatdemo",
                    "name": "Test User",
                    "device_id": "chatdemo_test_123",
                },
                "session_id": "test_session_123",
            },
        },
    ]

    for test_case in test_payloads:
        print(f"\n📋 Testing: {test_case['name']}")
        print(f"URL: {url}")
        print(f"Payload: {json.dumps(test_case['payload'], indent=2)}")

        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            }

            response = requests.post(
                url, json=test_case["payload"], headers=headers, timeout=10
            )
            print(f"Status: {response.status_code}")

            if response.status_code == 422:
                print(f"❌ Validation Error: {response.text}")
            elif response.status_code == 200:
                print(f"✅ Success! Response headers: {dict(response.headers)}")
            else:
                print(f"⚠️  Other status: {response.text}")

        except Exception as e:
            print(f"❌ Request failed: {e}")

        print("-" * 30)


def test_payload_flexibility():
    """Test various payload formats to ensure flexibility"""
    print("🧪 Testing Payload Flexibility for Unified Chat API")
    print("=" * 60)

    # Test case 1: Minimal payload (only required fields)
    print("\n1️⃣ Testing minimal payload (company_id + message only):")
    minimal_payload = {
        "company_id": "test-company-001",
        "message": "Xin chào, tôi muốn biết về dịch vụ của công ty",
    }

    print(f"Payload: {json.dumps(minimal_payload, indent=2)}")
    result1 = test_single_payload("minimal", minimal_payload)

    # Test case 2: Partial user info
    print("\n2️⃣ Testing partial user info payload:")
    partial_user_payload = {
        "company_id": "test-company-001",
        "message": "Tôi quan tâm đến sản phẩm vay thế chấp",
        "user_info": {"user_id": "user123", "device_id": "device456"},
    }

    print(f"Payload: {json.dumps(partial_user_payload, indent=2)}")
    result2 = test_single_payload("partial_user", partial_user_payload)

    # Test case 3: Full detailed payload
    print("\n3️⃣ Testing full detailed payload:")
    full_payload = {
        "company_id": "test-company-001",
        "message": "Tôi muốn vay mua nhà, cần tư vấn về lãi suất",
        "industry": "banking",
        "language": "vi",
        "user_info": {
            "user_id": "authenticated_user_789",
            "source": "chatdemo",
            "name": "Nguyen Van A",
            "email": "nguyenvana@email.com",
            "device_id": "chatdemo_fingerprint_abc123",
            "platform_specific_data": {
                "browser": "Chrome",
                "platform": "macOS",
                "screen_resolution": "1920x1080",
            },
        },
        "context": {
            "page_url": "https://admin.agent8x.io.vn/chat",
            "referrer": "https://admin.agent8x.io.vn/dashboard",
            "timestamp": "2025-01-31T10:30:00Z",
        },
        "metadata": {
            "source": "admin_panel",
            "version": "1.0.0",
            "request_id": "req_12345",
        },
    }

    print(f"Payload: {json.dumps(full_payload, indent=2)}")
    result3 = test_single_payload("full_detailed", full_payload)

    # Test case 4: No user_info at all
    print("\n4️⃣ Testing no user_info payload:")
    no_user_payload = {
        "company_id": "test-company-001",
        "message": "Chào bạn, tôi cần hỗ trợ",
        "industry": "other",
    }

    print(f"Payload: {json.dumps(no_user_payload, indent=2)}")
    result4 = test_single_payload("no_user", no_user_payload)

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY:")
    results = [
        ("Minimal payload", result1),
        ("Partial user info", result2),
        ("Full detailed payload", result3),
        ("No user info", result4),
    ]

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status} - {test_name}")

    success_count = sum(1 for _, success in results if success)
    print(f"\nOverall: {success_count}/{len(results)} tests passed")

    if success_count == len(results):
        print("🎉 All flexibility tests passed! API is now flexible.")
    else:
        print("⚠️  Some tests failed. Check validation logic.")


def test_single_payload(test_name: str, payload: dict) -> bool:
    """Test a single payload and return success status"""
    try:
        # Test against detect-intent endpoint (lighter than full chat)
        url = f"{BASE_URL}/api/unified/detect-intent"

        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        print(f"Sending request to: {url}")
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        print(f"Response status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(
                f"✅ SUCCESS - Intent detected: {result.get('intent_detection', {}).get('intent', 'unknown')}"
            )
            return True
        elif response.status_code == 422:
            print(f"❌ VALIDATION ERROR (422): {response.text}")
            return False
        else:
            print(f"❌ HTTP ERROR ({response.status_code}): {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ REQUEST ERROR: {e}")
        return False
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        return False


def test_local_validation():
    """Test payload validation locally without making HTTP requests"""
    print("\n🔧 Testing local validation (without HTTP requests):")
    print("-" * 50)

    try:
        # Import the model locally to test validation
        import sys
        import os

        # Add the src directory to Python path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        src_dir = os.path.join(current_dir, "src")
        sys.path.insert(0, src_dir)

        from models.unified_models import UnifiedChatRequest

        # Test minimal payload
        print("\n1. Testing minimal payload locally:")
        try:
            minimal_data = {"company_id": "test-company-001", "message": "Xin chào"}
            request = UnifiedChatRequest(**minimal_data)
            print(f"✅ Minimal payload validated successfully")
            print(f"   Generated session_id: {request.session_id}")
            print(f"   Default industry: {request.industry}")
            print(
                f"   Generated user_info: user_id={request.user_info.user_id if request.user_info else 'None'}"
            )

        except Exception as e:
            print(f"❌ Minimal payload validation failed: {e}")

        # Test no user_info payload
        print("\n2. Testing no user_info payload locally:")
        try:
            no_user_data = {
                "company_id": "test-company-001",
                "message": "Test message",
                "industry": "banking",
            }
            request = UnifiedChatRequest(**no_user_data)
            print(f"✅ No user_info payload validated successfully")
            print(
                f"   Auto-generated user_info: {request.user_info.user_id if request.user_info else 'None'}"
            )

        except Exception as e:
            print(f"❌ No user_info payload validation failed: {e}")

    except ImportError as e:
        print(f"❌ Cannot import model for local testing: {e}")
        print("   (This is expected if running outside the project directory)")


if __name__ == "__main__":
    print("🔄 Starting Unified Chat API Flexibility Tests...")
    print(f"Target: {BASE_URL}")

    # First debug the exact failing endpoint
    debug_chat_stream_endpoint()

    # Test local validation first
    test_local_validation()

    # Then test actual HTTP endpoints
    test_payload_flexibility()

    print("\n🏁 Test completed!")
