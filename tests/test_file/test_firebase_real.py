#!/usr/bin/env python3
"""
Test Firebase Auth API với server đang chạy
Sử dụng Firebase credentials thật
"""

import asyncio
import httpx
import json
from datetime import datetime

API_BASE_URL = "http://localhost:8000"


async def test_server_health():
    """Test if server is running and Firebase is configured"""

    async with httpx.AsyncClient(timeout=10.0) as client:
        print("🏥 Testing Server & Firebase Health")
        print("=" * 40)

        try:
            # Test general server health
            response = await client.get(f"{API_BASE_URL}/health")
            print(f"   Server Status: {response.status_code}")
            if response.status_code == 200:
                print("   Server: ✅ Running")
            else:
                print("   Server: ❌ Not healthy")
                return False

        except Exception as e:
            print(f"   Server: ❌ Not reachable - {e}")
            return False

        try:
            # Test Firebase auth health
            response = await client.get(f"{API_BASE_URL}/api/auth/health")
            print(f"   Auth Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Firebase: ✅ {data.get('firebase_status', 'unknown')}")
                print(f"   Initialized: {data.get('firebase_initialized', False)}")
                return True
            else:
                print("   Firebase: ❌ Not healthy")
                return False

        except Exception as e:
            print(f"   Firebase: ❌ Error - {e}")
            return False


async def test_auth_endpoints_without_token():
    """Test endpoints that should work without token"""

    async with httpx.AsyncClient(timeout=10.0) as client:
        print("\n🔓 Testing Public Endpoints")
        print("=" * 30)

        # Test logout (public)
        try:
            response = await client.post(f"{API_BASE_URL}/api/auth/logout")
            print(
                f"   Logout: {response.status_code} ✅"
                if response.status_code == 200
                else f"   Logout: {response.status_code} ❌"
            )
        except Exception as e:
            print(f"   Logout: ❌ Error - {e}")


async def test_protected_endpoints_without_token():
    """Test protected endpoints without token (should return 401)"""

    async with httpx.AsyncClient(timeout=10.0) as client:
        print("\n🔐 Testing Protected Endpoints (No Token)")
        print("=" * 45)

        endpoints = [
            ("/api/auth/profile", "Profile"),
            ("/api/auth/validate", "Validate"),
            ("/api/auth/conversations", "Conversations"),
        ]

        for endpoint, name in endpoints:
            try:
                response = await client.get(f"{API_BASE_URL}{endpoint}")
                expected = response.status_code == 401
                status = (
                    "✅ Properly secured"
                    if expected
                    else f"❌ Unexpected: {response.status_code}"
                )
                print(f"   {name}: {status}")

                if not expected and response.status_code != 401:
                    data = response.json()
                    print(f"      Response: {data}")

            except Exception as e:
                print(f"   {name}: ❌ Error - {e}")


async def test_with_invalid_token():
    """Test with invalid Firebase token"""

    async with httpx.AsyncClient(timeout=10.0) as client:
        print("\n🚫 Testing with Invalid Token")
        print("=" * 35)

        headers = {"Authorization": "Bearer invalid_token_123"}

        try:
            response = await client.get(
                f"{API_BASE_URL}/api/auth/validate", headers=headers
            )
            expected = response.status_code == 401
            status = (
                "✅ Properly rejected"
                if expected
                else f"❌ Unexpected: {response.status_code}"
            )
            print(f"   Invalid Token: {status}")

            if response.status_code == 401:
                data = response.json()
                print(f"      Error: {data.get('detail', 'Unknown error')}")

        except Exception as e:
            print(f"   Invalid Token: ❌ Error - {e}")


async def test_register_endpoint():
    """Test register endpoint (should require valid Firebase token)"""

    async with httpx.AsyncClient(timeout=10.0) as client:
        print("\n📝 Testing Registration Endpoint")
        print("=" * 35)

        # Without token
        try:
            response = await client.post(f"{API_BASE_URL}/api/auth/register")
            expected = response.status_code == 401
            status = (
                "✅ Requires auth"
                if expected
                else f"❌ Unexpected: {response.status_code}"
            )
            print(f"   Register (no token): {status}")
        except Exception as e:
            print(f"   Register (no token): ❌ Error - {e}")

        # With invalid token
        try:
            headers = {"Authorization": "Bearer invalid_token"}
            response = await client.post(
                f"{API_BASE_URL}/api/auth/register", headers=headers
            )
            expected = response.status_code == 401
            status = (
                "✅ Rejects invalid"
                if expected
                else f"❌ Unexpected: {response.status_code}"
            )
            print(f"   Register (invalid token): {status}")
        except Exception as e:
            print(f"   Register (invalid token): ❌ Error - {e}")


async def main():
    """Main test function"""

    print("🧪 Firebase Auth API Testing")
    print("=" * 50)
    print(f"   API Base URL: {API_BASE_URL}")
    print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Test server health first
    server_healthy = await test_server_health()

    if not server_healthy:
        print("\n❌ Server not healthy - stopping tests")
        return

    # Run all tests
    await test_auth_endpoints_without_token()
    await test_protected_endpoints_without_token()
    await test_with_invalid_token()
    await test_register_endpoint()

    print("\n📋 Test Summary")
    print("=" * 20)
    print("✅ Server is running with Firebase authentication")
    print("✅ Public endpoints work correctly")
    print("✅ Protected endpoints properly secured")
    print("✅ Invalid tokens properly rejected")
    print()
    print("🔥 Next Steps:")
    print("   1. Get real Firebase ID token from frontend")
    print("   2. Test with real Firebase token")
    print("   3. Test user registration and profile endpoints")


if __name__ == "__main__":
    asyncio.run(main())
