#!/usr/bin/env python3
"""
Test script for company basic info API with legacy format
"""

import requests
import json
import sys


def test_legacy_format():
    """Test with legacy format (direct fields)"""

    url = "http://localhost:8000/api/admin/companies/693409fd-c214-47db-a465-2e565b00be05/basic-info"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer test-internal-key",
    }

    # Legacy format payload (như backend đang gửi)
    legacy_payload = {
        "company_name": "AIA Vietnam Insurance",
        "industry": "insurance",
        "metadata": {
            "email": "contact@aia.com.vn",
            "phone": "+84 28 3520 2468",
            "website": "https://www.aia.com.vn",
            "description": "Leading life insurance company in Vietnam",
            "location": {
                "country": "Vietnam",
                "city": "Ho Chi Minh City",
                "address": "Unit 1501, 15th Floor, Saigon Trade Center",
            },
            "social_links": {
                "facebook": "https://facebook.com/AIAVietnam",
                "linkedin": "https://linkedin.com/company/aia-vietnam",
            },
        },
    }

    print("🧪 Testing Legacy Format...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(legacy_payload, indent=2)}")

    try:
        response = requests.put(url, headers=headers, json=legacy_payload, timeout=10)
        print(f"\nStatus Code: {response.status_code}")

        if response.status_code == 200:
            print("✅ Legacy format test successful!")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        else:
            print(f"❌ Legacy format test failed!")
            try:
                error_detail = response.json()
                print(f"Error: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"Raw error: {response.text}")

    except requests.exceptions.ConnectionError:
        print("⚠️ Server is not running. Please start the server first.")
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

    return True


def test_new_format():
    """Test with new format (basic_info wrapper)"""

    url = "http://localhost:8000/api/admin/companies/693409fd-c214-47db-a465-2e565b00be05/basic-info"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer test-internal-key",
    }

    # New format payload
    new_payload = {
        "basic_info": {
            "company_name": "AIA Vietnam Insurance Company",
            "industry": "insurance",
            "email": "contact@aia.com.vn",
            "phone": "+84 28 3520 2468",
            "website": "https://www.aia.com.vn",
            "description": "Leading life insurance company in Vietnam",
            "logo": "https://storage.company.com/logos/aia-logo.png",
            "location": {
                "country": "VN",
                "city": "Ho Chi Minh City",
                "address": "Unit 1501, 15th Floor, Saigon Trade Center",
            },
            "socialLinks": {
                "facebook": "https://facebook.com/AIAVietnam",
                "linkedin": "https://linkedin.com/company/aia-vietnam",
            },
        }
    }

    print("\n🧪 Testing New Format...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(new_payload, indent=2)}")

    try:
        response = requests.put(url, headers=headers, json=new_payload, timeout=10)
        print(f"\nStatus Code: {response.status_code}")

        if response.status_code == 200:
            print("✅ New format test successful!")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        else:
            print(f"❌ New format test failed!")
            try:
                error_detail = response.json()
                print(f"Error: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"Raw error: {response.text}")

    except requests.exceptions.ConnectionError:
        print("⚠️ Server is not running. Please start the server first.")
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

    return True


if __name__ == "__main__":
    print("🚀 Testing Company Basic Info API - Dual Format Support")
    print("=" * 60)

    # Test both formats
    legacy_success = test_legacy_format()
    new_success = test_new_format()

    print("\n" + "=" * 60)
    print("📋 Test Summary:")
    print(f"Legacy Format: {'✅ PASS' if legacy_success else '❌ FAIL'}")
    print(f"New Format: {'✅ PASS' if new_success else '❌ FAIL'}")

    if legacy_success and new_success:
        print("\n🎉 All tests passed! API supports both formats.")
        sys.exit(0)
    else:
        print("\n⚠️ Some tests failed. Check server logs for details.")
        sys.exit(1)
