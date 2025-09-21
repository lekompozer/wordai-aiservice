"""
Debug API Key Authentication
Script debug xác thực API key
"""

import asyncio
import aiohttp
import json
import os

# Configuration
AI_SERVICE_URL = "http://localhost:8000"
API_KEY = "agent8x-backend-secret-key-2025"


async def test_api_key():
    """Test API key authentication"""
    headers = {"Content-Type": "application/json", "X-API-Key": API_KEY}

    print(f"🔑 Testing API Key: {API_KEY}")
    print(f"🌐 Server URL: {AI_SERVICE_URL}")

    async with aiohttp.ClientSession() as session:
        # Test 1: Simple health check
        print("\n📡 Test 1: Health Check (no auth required)")
        try:
            async with session.get(f"{AI_SERVICE_URL}/health") as response:
                print(f"   Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"   Response: {data.get('status', 'Unknown')}")
        except Exception as e:
            print(f"   Error: {e}")

        # Test 2: Admin endpoint with auth
        print("\n🔐 Test 2: Admin endpoint with authentication")
        try:
            async with session.get(
                f"{AI_SERVICE_URL}/api/admin/companies/test_company_001",
                headers=headers,
            ) as response:
                print(f"   Status: {response.status}")
                if response.status == 401:
                    error_data = await response.json()
                    print(f"   Auth Error: {error_data}")
                elif response.status == 404:
                    print(f"   Company not found (expected)")
                elif response.status == 200:
                    print(f"   ✅ Authentication successful!")
                else:
                    print(f"   Unexpected status: {response.status}")
        except Exception as e:
            print(f"   Error: {e}")

        # Test 3: Check environment variable
        print("\n🌍 Test 3: Environment Variable Check")
        env_api_key = os.getenv("INTERNAL_API_KEY")
        print(f"   INTERNAL_API_KEY from env: {env_api_key}")

        if env_api_key and env_api_key != API_KEY:
            print(f"   ⚠️ Warning: Env key differs from test key!")
            print(f"   Testing with env key...")

            env_headers = {"Content-Type": "application/json", "X-API-Key": env_api_key}

            async with session.get(
                f"{AI_SERVICE_URL}/api/admin/companies/test_company_001",
                headers=env_headers,
            ) as response:
                print(f"   Env key status: {response.status}")

        # Test 4: Try creating basic info with correct key
        print("\n📝 Test 4: Create Basic Info")
        test_basic_info = {
            "company_name": "Test Company",
            "introduction": "A test company for debugging",
            "products_summary": "Test products",
            "contact_info": "test@example.com",
        }

        try:
            async with session.post(
                f"{AI_SERVICE_URL}/api/admin/companies/test_debug_001/context/basic-info",
                headers=headers,
                json=test_basic_info,
            ) as response:
                print(f"   Status: {response.status}")
                if response.status == 200:
                    print(f"   ✅ Basic info created successfully!")
                else:
                    error_text = await response.text()
                    print(f"   Error: {error_text}")
        except Exception as e:
            print(f"   Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_api_key())
