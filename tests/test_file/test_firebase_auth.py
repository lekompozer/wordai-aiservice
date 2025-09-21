#!/usr/bin/env python3
"""
Test Firebase Authentication API Endpoints
Script để test các API endpoints mới tạo
"""

import asyncio
import httpx
import json
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"
FIREBASE_TOKEN = "YOUR_FIREBASE_ID_TOKEN_HERE"  # Cần lấy từ frontend


async def test_auth_endpoints():
    """Test all authentication endpoints"""

    headers = {
        "Authorization": f"Bearer {FIREBASE_TOKEN}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        print("🔐 Testing Firebase Authentication Endpoints")
        print("=" * 50)

        # 1. Test health check
        print("\n1. Testing Auth Health Check...")
        try:
            response = await client.get(f"{API_BASE_URL}/api/auth/health")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # 2. Test token validation
        print("\n2. Testing Token Validation...")
        try:
            response = await client.get(
                f"{API_BASE_URL}/api/auth/validate", headers=headers
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # 3. Test user registration/login
        print("\n3. Testing User Registration...")
        try:
            response = await client.post(
                f"{API_BASE_URL}/api/auth/register", headers=headers
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # 4. Test get user profile
        print("\n4. Testing Get User Profile...")
        try:
            response = await client.get(
                f"{API_BASE_URL}/api/auth/profile", headers=headers
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # 5. Test get conversations
        print("\n5. Testing Get User Conversations...")
        try:
            response = await client.get(
                f"{API_BASE_URL}/api/auth/conversations", headers=headers
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # 6. Test logout
        print("\n6. Testing Logout...")
        try:
            response = await client.post(f"{API_BASE_URL}/api/auth/logout")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   ❌ Error: {e}")


async def test_without_token():
    """Test endpoints without authentication token"""

    async with httpx.AsyncClient() as client:
        print("\n🚫 Testing Endpoints Without Token")
        print("=" * 50)

        # Test protected endpoint without token
        print("\n1. Testing Protected Endpoint Without Token...")
        try:
            response = await client.get(f"{API_BASE_URL}/api/auth/profile")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Test public endpoint
        print("\n2. Testing Public Health Check...")
        try:
            response = await client.get(f"{API_BASE_URL}/api/auth/health")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
        except Exception as e:
            print(f"   ❌ Error: {e}")


def generate_curl_commands():
    """Generate curl commands for testing"""

    print("\n📋 Curl Commands for Testing")
    print("=" * 50)

    commands = [
        {
            "name": "Health Check",
            "command": f"curl -X GET '{API_BASE_URL}/api/auth/health'",
        },
        {
            "name": "Token Validation",
            "command": f"curl -X GET '{API_BASE_URL}/api/auth/validate' -H 'Authorization: Bearer YOUR_FIREBASE_TOKEN'",
        },
        {
            "name": "User Registration",
            "command": f"curl -X POST '{API_BASE_URL}/api/auth/register' -H 'Authorization: Bearer YOUR_FIREBASE_TOKEN'",
        },
        {
            "name": "Get Profile",
            "command": f"curl -X GET '{API_BASE_URL}/api/auth/profile' -H 'Authorization: Bearer YOUR_FIREBASE_TOKEN'",
        },
        {
            "name": "Get Conversations",
            "command": f"curl -X GET '{API_BASE_URL}/api/auth/conversations' -H 'Authorization: Bearer YOUR_FIREBASE_TOKEN'",
        },
    ]

    for cmd in commands:
        print(f"\n{cmd['name']}:")
        print(f"   {cmd['command']}")


async def main():
    """Main test function"""

    print("🧪 Firebase Auth API Testing")
    print(f"   API Base URL: {API_BASE_URL}")
    print(f"   Timestamp: {datetime.now().isoformat()}")

    if FIREBASE_TOKEN == "YOUR_FIREBASE_ID_TOKEN_HERE":
        print("\n⚠️  Warning: Firebase token not set!")
        print(
            "   Update FIREBASE_TOKEN variable with real token to test authenticated endpoints"
        )

        await test_without_token()
        generate_curl_commands()
    else:
        await test_auth_endpoints()
        await test_without_token()
        generate_curl_commands()


if __name__ == "__main__":
    asyncio.run(main())
