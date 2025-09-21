#!/usr/bin/env python3
"""
Test message_id auto-generation for frontend requests
Kiểm tra tự động tạo message_id cho frontend requests
"""

import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.unified_models import UnifiedChatRequest, Industry


def test_frontend_request_without_message_id():
    """Test frontend request without message_id - should auto-generate"""

    print("🧪 Testing Frontend Request WITHOUT message_id...")

    # Frontend request - no message_id provided
    request = UnifiedChatRequest(
        message="Tôi muốn tìm hiểu về bảo hiểm",
        company_id="aia-insurance",
        industry=Industry.INSURANCE,
        channel="chatdemo",
    )

    print(f"✅ Request created successfully")
    print(f"   message: {request.message}")
    print(f"   message_id: {request.message_id}")  # Should be auto-generated
    print(f"   company_id: {request.company_id}")
    print(f"   channel: {request.channel}")

    # Verify message_id was auto-generated
    if request.message_id and request.message_id.startswith("msg_"):
        print(f"✅ SUCCESS: message_id auto-generated for frontend!")
        print(f"   Generated ID: {request.message_id}")
    else:
        print(f"❌ ERROR: message_id not auto-generated")
        return False

    return True


def test_backend_request_with_message_id():
    """Test backend request with message_id - should use provided ID"""

    print("\n🧪 Testing Backend Request WITH message_id...")

    # Backend request - message_id provided
    backend_message_id = "msg_backend_messenger_FB_12345"
    request = UnifiedChatRequest(
        message="Tôi muốn mua bảo hiểm",
        message_id=backend_message_id,
        company_id="aia-insurance",
        industry=Industry.INSURANCE,
        channel="messenger",
    )

    print(f"✅ Request created successfully")
    print(f"   message: {request.message}")
    print(f"   message_id: {request.message_id}")
    print(f"   company_id: {request.company_id}")
    print(f"   channel: {request.channel}")

    # Verify message_id matches provided one
    if request.message_id == backend_message_id:
        print(f"✅ SUCCESS: message_id preserved from backend!")
        print(f"   Provided ID: {backend_message_id}")
        print(f"   Used ID: {request.message_id}")
    else:
        print(f"❌ ERROR: message_id was modified")
        print(f"   Expected: {backend_message_id}")
        print(f"   Got: {request.message_id}")
        return False

    return True


def main():
    print("🚀 Testing message_id handling for Frontend vs Backend requests")
    print("=" * 70)

    # Test both scenarios
    frontend_success = test_frontend_request_without_message_id()
    backend_success = test_backend_request_with_message_id()

    print("\n" + "=" * 70)
    print("🎯 SUMMARY:")
    print(
        f"   Frontend auto-generation: {'✅ PASS' if frontend_success else '❌ FAIL'}"
    )
    print(f"   Backend preservation: {'✅ PASS' if backend_success else '❌ FAIL'}")

    if frontend_success and backend_success:
        print(f"\n🎉 ALL TESTS PASSED!")
        print(f"   - Frontend: message_id auto-generated when missing ✅")
        print(f"   - Backend: message_id preserved when provided ✅")
        print(f"   - Frontend validation error should be FIXED! 🎯")
    else:
        print(f"\n❌ Some tests failed!")

    return frontend_success and backend_success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
