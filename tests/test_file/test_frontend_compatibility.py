#!/usr/bin/env python3
"""
Test frontend compatibility with UPPERCASE formats
"""

import sys
import os

# Add the src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
sys.path.insert(0, src_dir)

from models.unified_models import UnifiedChatRequest


def test_frontend_formats():
    """Test với các format từ frontend"""
    print("🧪 Testing Frontend Format Compatibility")
    print("=" * 50)

    # Test 1: Frontend payload với UPPERCASE
    print("\n1. Testing UPPERCASE industry and language:")
    try:
        request = UnifiedChatRequest(
            company_id="test-company-001",
            message="Hello test",
            industry="INSURANCE",  # UPPERCASE
            language="ENGLISH",  # UPPERCASE
        )
        print(f"✅ SUCCESS")
        print(f"   industry: {request.industry} (value: {request.industry.value})")
        print(f"   language: {request.language} (value: {request.language.value})")
    except Exception as e:
        print(f"❌ FAILED: {e}")

    # Test 2: Mixed case
    print("\n2. Testing mixed case:")
    try:
        request = UnifiedChatRequest(
            company_id="test-company-001",
            message="Hello test",
            industry="Banking",  # Mixed case
            language="vi",  # lowercase
        )
        print(f"✅ SUCCESS")
        print(f"   industry: {request.industry} (value: {request.industry.value})")
        print(f"   language: {request.language} (value: {request.language.value})")
    except Exception as e:
        print(f"❌ FAILED: {e}")

    # Test 3: Invalid values
    print("\n3. Testing invalid values (should default):")
    try:
        request = UnifiedChatRequest(
            company_id="test-company-001",
            message="Hello test",
            industry="INVALID_INDUSTRY",
            language="INVALID_LANG",
        )
        print(f"✅ SUCCESS")
        print(
            f"   industry: {request.industry} (value: {request.industry.value}) - should be 'other'"
        )
        print(
            f"   language: {request.language} (value: {request.language.value}) - should be 'auto'"
        )
    except Exception as e:
        print(f"❌ FAILED: {e}")

    # Test 4: Exact frontend payload structure
    print("\n4. Testing exact frontend payload:")
    try:
        frontend_data = {
            "company_id": "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
            "industry": "INSURANCE",
            "language": "ENGLISH",
            "message": "cho tao thông tin về AIA xem",
            "session_id": "firebase_2Fi60Cy2jHcMhkn5o2VcjfUef7p2_1753905688",
            "user_info": {
                "user_id": "2Fi60Cy2jHcMhkn5o2VcjfUef7p2",
                "source": "chatdemo",
                "name": "Michael Le",
                "email": "tienhoi.lh@gmail.com",
                "device_id": "web_eczqgo",
            },
        }

        request = UnifiedChatRequest(**frontend_data)
        print(f"✅ SUCCESS - Frontend payload converted!")
        print(f"   company_id: {request.company_id}")
        print(f"   industry: INSURANCE -> {request.industry.value}")
        print(f"   language: ENGLISH -> {request.language.value}")
        print(f"   user_id: {request.user_info.user_id}")
        print(f"   message: {request.message[:50]}...")

    except Exception as e:
        print(f"❌ FAILED: {e}")


if __name__ == "__main__":
    test_frontend_formats()
