#!/usr/bin/env python3
"""
Test model validation locally in detail
Kiểm tra validation model local chi tiết
"""

import sys
import os

# Add the src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
sys.path.insert(0, src_dir)

from models.unified_models import UnifiedChatRequest, UserInfo, Industry, UserSource


def test_comprehensive_validation():
    """Test all edge cases for model validation"""
    print("🔍 Comprehensive Model Validation Test")
    print("=" * 50)

    # Test 1: Absolute minimum
    print("\n1. Testing absolute minimum (company_id + message):")
    try:
        request = UnifiedChatRequest(company_id="test-001", message="Hello")
        print(f"✅ SUCCESS")
        print(f"   company_id: {request.company_id}")
        print(f"   industry: {request.industry}")
        print(f"   user_info: {request.user_info}")
        print(f"   user_id: {request.user_info.user_id if request.user_info else None}")
        print(f"   session_id: {request.session_id}")
    except Exception as e:
        print(f"❌ FAILED: {e}")

    # Test 2: Empty user_info dict
    print("\n2. Testing empty user_info dict:")
    try:
        request = UnifiedChatRequest(
            company_id="test-001", message="Hello", user_info={}
        )
        print(f"✅ SUCCESS")
        print(f"   user_info: {request.user_info}")
        print(f"   user_id: {request.user_info.user_id if request.user_info else None}")
    except Exception as e:
        print(f"❌ FAILED: {e}")

    # Test 3: Partial user_info
    print("\n3. Testing partial user_info (only user_id):")
    try:
        request = UnifiedChatRequest(
            company_id="test-001", message="Hello", user_info={"user_id": "user123"}
        )
        print(f"✅ SUCCESS")
        print(f"   user_id: {request.user_info.user_id}")
        print(f"   source: {request.user_info.source}")
        print(f"   device_id: {request.user_info.device_id}")
    except Exception as e:
        print(f"❌ FAILED: {e}")

    # Test 4: UserInfo with None values
    print("\n4. Testing UserInfo with explicit None values:")
    try:
        user_info = UserInfo(user_id=None, source=UserSource.CHATDEMO, device_id=None)
        request = UnifiedChatRequest(
            company_id="test-001", message="Hello", user_info=user_info
        )
        print(f"✅ SUCCESS")
        print(f"   user_id: {request.user_info.user_id}")
        print(f"   source: {request.user_info.source}")
        print(f"   device_id: {request.user_info.device_id}")
    except Exception as e:
        print(f"❌ FAILED: {e}")

    # Test 5: Direct UserInfo creation
    print("\n5. Testing direct UserInfo creation with minimal data:")
    try:
        user_info = UserInfo()
        print(f"✅ SUCCESS")
        print(f"   user_id: {user_info.user_id}")
        print(f"   source: {user_info.source}")
        print(f"   device_id: {user_info.device_id}")
    except Exception as e:
        print(f"❌ FAILED: {e}")

    # Test 6: Different industries
    print("\n6. Testing different industry defaults:")
    try:
        request1 = UnifiedChatRequest(company_id="test-001", message="Hello")
        request2 = UnifiedChatRequest(
            company_id="test-001", message="Hello", industry=Industry.BANKING
        )

        print(f"✅ SUCCESS")
        print(f"   Default industry: {request1.industry}")
        print(f"   Explicit industry: {request2.industry}")
    except Exception as e:
        print(f"❌ FAILED: {e}")

    # Test 7: JSON serialization
    print("\n7. Testing JSON serialization:")
    try:
        request = UnifiedChatRequest(company_id="test-001", message="Hello")

        import json

        # Convert to dict and then to JSON
        request_dict = request.model_dump()
        json_str = json.dumps(request_dict, indent=2, default=str)

        print(f"✅ SUCCESS - JSON serialization works")
        print(f"JSON preview (first 200 chars):\n{json_str[:200]}...")
    except Exception as e:
        print(f"❌ FAILED: {e}")


if __name__ == "__main__":
    test_comprehensive_validation()
