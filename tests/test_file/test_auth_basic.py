#!/usr/bin/env python3
"""
Test Firebase Authentication Setup (No Real Firebase)
Test các API endpoints mà không cần Firebase config thật
"""

import asyncio
import httpx
import json
from datetime import datetime

API_BASE_URL = "http://localhost:8000"


async def test_auth_endpoints_basic():
    """Test basic auth endpoints without real Firebase"""

    async with httpx.AsyncClient() as client:
        print("🔐 Testing Firebase Authentication Endpoints (Basic)")
        print("=" * 60)

        # 1. Test health check (should work without Firebase config)
        print("\n1. Testing Auth Health Check...")
        try:
            response = await client.get(f"{API_BASE_URL}/api/auth/health")
            print(f"   Status: {response.status_code}")
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # 2. Test logout endpoint (public)
        print("\n2. Testing Logout Endpoint...")
        try:
            response = await client.post(f"{API_BASE_URL}/api/auth/logout")
            print(f"   Status: {response.status_code}")
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # 3. Test protected endpoint without token (should return 401)
        print("\n3. Testing Protected Endpoint Without Token...")
        try:
            response = await client.get(f"{API_BASE_URL}/api/auth/profile")
            print(f"   Status: {response.status_code}")
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # 4. Test with invalid token (should return 401)
        print("\n4. Testing With Invalid Token...")
        try:
            headers = {"Authorization": "Bearer invalid_token_here"}
            response = await client.get(
                f"{API_BASE_URL}/api/auth/validate", headers=headers
            )
            print(f"   Status: {response.status_code}")
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)}")
        except Exception as e:
            print(f"   ❌ Error: {e}")


async def test_server_health():
    """Test if server is running"""

    async with httpx.AsyncClient() as client:
        print("🏥 Testing Server Health")
        print("=" * 30)

        # Test general health endpoint
        try:
            response = await client.get(f"{API_BASE_URL}/health")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Server: ✅ Running")
                print(f"   Uptime: {data.get('uptime_minutes', 'unknown')} minutes")
            else:
                print(f"   Server: ❌ Not responding correctly")
        except Exception as e:
            print(f"   Server: ❌ Not reachable - {e}")


async def main():
    """Main test function"""

    print("🧪 Firebase Auth API Basic Testing")
    print(f"   API Base URL: {API_BASE_URL}")
    print(f"   Timestamp: {datetime.now().isoformat()}")

    # Test if server is running first
    await test_server_health()

    # Test auth endpoints
    await test_auth_endpoints_basic()

    print("\n📋 Summary:")
    print("   - Health endpoints should return 200 with status info")
    print("   - Public endpoints (logout) should return 200")
    print("   - Protected endpoints should return 401 without valid token")
    print("   - Invalid token should return 401")

    print("\n🚀 Next Steps:")
    print("   1. Set up Firebase service account")
    print("   2. Add Firebase environment variables")
    print("   3. Test with real Firebase tokens")


if __name__ == "__main__":
    asyncio.run(main())
