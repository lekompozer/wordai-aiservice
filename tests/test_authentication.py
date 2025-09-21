"""
Test Authentication Middleware
Test middleware xác thực cho AI Service
"""

import httpx
import asyncio
import json
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000"
VALID_API_KEY = "agent8x-backend-secret-key-2025"
INVALID_API_KEY = "invalid-key-123"
TEST_COMPANY_ID = "test-company-789"

async def test_authentication():
    """Test authentication middleware"""
    print("🔐 Testing Authentication Middleware")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        
        # Test 1: Admin routes without API key
        print("\n❌ Testing admin access without API key...")
        try:
            response = await client.get(f"{BASE_URL}/admin/system/status")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test 2: Admin routes with invalid API key
        print("\n❌ Testing admin access with invalid API key...")
        try:
            headers = {"X-API-Key": INVALID_API_KEY}
            response = await client.get(f"{BASE_URL}/admin/system/status", headers=headers)
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test 3: Admin routes with valid API key
        print("\n✅ Testing admin access with valid API key...")
        try:
            headers = {"X-API-Key": VALID_API_KEY}
            response = await client.get(f"{BASE_URL}/admin/system/status", headers=headers)
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test 4: Chat routes without company access
        print("\n❌ Testing chat without company ID...")
        try:
            chat_data = {
                "message": "Hello",
                "session_id": f"test-{int(datetime.now().timestamp())}"
            }
            response = await client.post(f"{BASE_URL}/chat", json=chat_data)
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test 5: Chat routes with company ID in header
        print("\n✅ Testing chat with company ID in header...")
        try:
            headers = {"X-Company-Id": TEST_COMPANY_ID}
            chat_data = {
                "message": "Tôi muốn biết về menu",
                "session_id": f"test-{int(datetime.now().timestamp())}"
            }
            response = await client.post(f"{BASE_URL}/chat", json=chat_data, headers=headers)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"   Response: {result.get('response', '')[:100]}...")
                print(f"   Intent: {result.get('intent', 'N/A')}")
            else:
                print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test 6: Chat routes with company ID in body
        print("\n✅ Testing chat with company ID in body...")
        try:
            chat_data = {
                "message": "Tôi muốn đặt bàn",
                "company_id": TEST_COMPANY_ID,
                "session_id": f"test-{int(datetime.now().timestamp())}"
            }
            response = await client.post(f"{BASE_URL}/chat", json=chat_data)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"   Response: {result.get('response', '')[:100]}...")
                print(f"   Intent: {result.get('intent', 'N/A')}")
            else:
                print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   Error: {e}")

async def test_admin_endpoints():
    """Test all admin endpoints with authentication"""
    print("\n🔧 Testing Admin Endpoints")
    print("=" * 30)
    
    headers = {"X-API-Key": VALID_API_KEY}
    
    admin_endpoints = [
        "/admin/system/status",
        "/admin/companies",
        "/admin/documents",
        "/admin/conversations",
        "/admin/system/health"
    ]
    
    async with httpx.AsyncClient() as client:
        for endpoint in admin_endpoints:
            try:
                print(f"\n📡 Testing: {endpoint}")
                response = await client.get(f"{BASE_URL}{endpoint}", headers=headers)
                print(f"   Status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, dict):
                        print(f"   Keys: {list(result.keys())}")
                    elif isinstance(result, list):
                        print(f"   Items: {len(result)}")
                    else:
                        print(f"   Type: {type(result)}")
                else:
                    print(f"   Error: {response.json()}")
                    
            except Exception as e:
                print(f"   Exception: {e}")

async def test_webhook_signature():
    """Test webhook signature verification"""
    print("\n🔏 Testing Webhook Signature")
    print("=" * 30)
    
    from src.services.webhook_service import webhook_service
    
    # Test data
    test_data = {
        "event": "test",
        "data": {"test": True},
        "timestamp": datetime.now().isoformat()
    }
    
    # Generate signature
    signature = webhook_service._generate_signature(json.dumps(test_data))
    print(f"   Generated signature: {signature[:20]}...")
    
    # Verify signature
    is_valid = webhook_service._verify_signature(json.dumps(test_data), signature)
    print(f"   Signature valid: {'✅ YES' if is_valid else '❌ NO'}")
    
    # Test invalid signature
    is_invalid = webhook_service._verify_signature(json.dumps(test_data), "invalid-signature")
    print(f"   Invalid signature rejected: {'✅ YES' if not is_invalid else '❌ NO'}")

if __name__ == "__main__":
    async def main():
        print("🚀 Starting Authentication & Security Tests")
        print("=" * 60)
        print(f"Base URL: {BASE_URL}")
        print(f"API Key: {VALID_API_KEY[:10]}...")
        print(f"Company ID: {TEST_COMPANY_ID}")
        
        await test_authentication()
        await test_admin_endpoints()
        await test_webhook_signature()
        
        print("\n🏁 All tests completed!")
        print("=" * 60)
    
    asyncio.run(main())
