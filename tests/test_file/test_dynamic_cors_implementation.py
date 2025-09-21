"""
Test Dynamic CORS and Internal API Implementation
Kiểm tra implement Dynamic CORS và Internal API
"""

import asyncio
import httpx
import json
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


async def test_dynamic_cors_implementation():
    """Test dynamic CORS and internal API functionality"""

    print("🧪 Testing Dynamic CORS Implementation")
    print("=" * 50)

    base_url = "http://localhost:8000"
    backend_url = "http://localhost:8001"

    # Test data
    test_plugin_id = "plugin_test_123"
    test_company_id = "comp_test_456"
    test_domains = [
        "https://customer-website.com",
        "https://www.customer-website.com",
        "https://staging.customer-website.com",
    ]

    async with httpx.AsyncClient() as client:

        # 1. Test CORS status endpoint
        print("\n1. Testing CORS status endpoint...")
        try:
            response = await client.get(
                f"{base_url}/api/internal/cors/status",
                headers={"X-Internal-Auth": "internal-cors-update-token"},
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"   Response: {response.json()}")
            else:
                print(f"   Error: {response.text}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # 2. Test domain update endpoint
        print("\n2. Testing domain update endpoint...")
        try:
            update_payload = {
                "pluginId": test_plugin_id,
                "domains": test_domains,
                "companyId": test_company_id,
            }

            response = await client.post(
                f"{base_url}/api/internal/cors/update-domains",
                headers={
                    "X-Internal-Auth": "internal-cors-update-token",
                    "Content-Type": "application/json",
                },
                json=update_payload,
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"   Response: {response.json()}")
            else:
                print(f"   Error: {response.text}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # 3. Test chat-plugin request with CORS
        print("\n3. Testing chat-plugin request with CORS...")
        try:
            chat_payload = {
                "message": "Hello from customer website",
                "company_id": test_company_id,
                "channel": "chat-plugin",
                "plugin_id": test_plugin_id,
                "customer_domain": "https://customer-website.com",
                "user_info": {
                    "user_id": "customer_user_123",
                    "source": "chat_plugin",
                    "device_id": "device_456",
                },
            }

            # Simulate request from customer domain
            response = await client.post(
                f"{base_url}/api/unified/chat-stream",
                headers={
                    "Origin": "https://customer-website.com",
                    "X-Plugin-Id": test_plugin_id,
                    "Content-Type": "application/json",
                },
                json=chat_payload,
                timeout=30.0,
            )
            print(f"   Status: {response.status_code}")
            print(f"   CORS Headers: {dict(response.headers)}")

            if response.status_code == 200:
                print("   ✅ Chat request successful")
            else:
                print(f"   ❌ Chat request failed: {response.text}")

        except Exception as e:
            print(f"   ❌ Error: {e}")

        # 4. Test clear cache endpoint
        print("\n4. Testing clear cache endpoint...")
        try:
            response = await client.delete(
                f"{base_url}/api/internal/cors/clear-cache/{test_plugin_id}",
                headers={"X-Internal-Auth": "internal-cors-update-token"},
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"   Response: {response.json()}")
            else:
                print(f"   Error: {response.text}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # 5. Test unauthorized access
        print("\n5. Testing unauthorized access...")
        try:
            response = await client.get(
                f"{base_url}/api/internal/cors/status",
                headers={"X-Internal-Auth": "wrong-token"},
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 401:
                print("   ✅ Unauthorized access properly blocked")
            else:
                print(f"   ❌ Security issue: {response.text}")
        except Exception as e:
            print(f"   ❌ Error: {e}")


async def test_webhook_payload_generation():
    """Test webhook payload generation for different channels"""

    print("\n🔗 Testing Webhook Payload Generation")
    print("=" * 50)

    base_url = "http://localhost:8000"

    test_scenarios = [
        {
            "name": "Frontend Channel (chat-plugin)",
            "payload": {
                "message": "Test message from chat plugin",
                "company_id": "comp_123",
                "channel": "chat-plugin",
                "plugin_id": "plugin_abc",
                "customer_domain": "https://customer.com",
                "user_info": {
                    "user_id": "user_123",
                    "source": "chat_plugin",
                    "device_id": "device_456",
                },
            },
        },
        {
            "name": "Backend Channel (messenger)",
            "payload": {
                "message": "Test message from messenger",
                "company_id": "comp_123",
                "channel": "messenger",
                "user_info": {
                    "user_id": "fb_user_123",
                    "source": "facebook_messenger",
                    "device_id": "fb_device_456",
                },
            },
        },
    ]

    async with httpx.AsyncClient() as client:
        for scenario in test_scenarios:
            print(f"\n{scenario['name']}:")
            try:
                response = await client.post(
                    f"{base_url}/api/unified/chat-stream",
                    headers={"Content-Type": "application/json"},
                    json=scenario["payload"],
                    timeout=30.0,
                )
                print(f"   Status: {response.status_code}")
                print(f"   Headers: {dict(response.headers)}")

                if response.status_code == 200:
                    print("   ✅ Request successful")
                else:
                    print(f"   ❌ Request failed: {response.text}")

            except Exception as e:
                print(f"   ❌ Error: {e}")


async def main():
    """Run all tests"""
    print("🚀 Dynamic CORS and Webhook Implementation Tests")
    print("=" * 60)

    try:
        await test_dynamic_cors_implementation()
        await test_webhook_payload_generation()

        print("\n" + "=" * 60)
        print("✅ Tests completed!")
        print("\n📋 Summary:")
        print("1. Dynamic CORS middleware implemented")
        print("2. Internal API endpoints created")
        print("3. Webhook payload generation updated")
        print("4. Chat-plugin support added")
        print("\n🔧 Next steps:")
        print("- Start AI Service with new configuration")
        print("- Update nginx to remove static CORS for chat routes")
        print("- Test with real customer domains")

    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
