#!/usr/bin/env python3
"""
Test company registration flow
"""
import asyncio
import json
import aiohttp
import os
from datetime import datetime

# Load environment
from dotenv import load_dotenv

load_dotenv("development.env")

AI_SERVICE_URL = "http://localhost:8080"  # AI Service URL
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "internal-api-key-12345")


async def test_company_registration():
    """Test if AI Service can register a company properly"""
    print("🧪 TESTING COMPANY REGISTRATION FLOW")
    print("=" * 50)

    # Test data
    test_company_id = "test-company-12345"
    test_company_name = "Test Company for Registration"
    test_industry = "hospitality"  # Valid industry

    print(f"📊 Test Company ID: {test_company_id}")
    print(f"🏢 Company Name: {test_company_name}")
    print(f"🏭 Industry: {test_industry}")
    print()

    async with aiohttp.ClientSession() as session:
        # 1. First check if company already exists
        print("1️⃣ Checking if company already exists...")
        try:
            async with session.get(
                f"{AI_SERVICE_URL}/api/admin/companies/{test_company_id}",
                headers={"X-API-Key": INTERNAL_API_KEY},
            ) as response:
                if response.status == 200:
                    print("✅ Company already exists")
                    data = await response.json()
                    print(
                        f"   📋 Existing data: {json.dumps(data, indent=2, ensure_ascii=False)}"
                    )
                    return
                elif response.status == 404:
                    print("ℹ️  Company does not exist, will register")
                else:
                    print(f"⚠️  Unexpected status: {response.status}")
        except Exception as e:
            print(f"❌ Error checking company: {e}")

        print()

        # 2. Register the company
        print("2️⃣ Registering new company...")
        registration_payload = {
            "company_id": test_company_id,
            "company_name": test_company_name,
            "industry": test_industry,
        }

        try:
            async with session.post(
                f"{AI_SERVICE_URL}/api/admin/companies/register",
                headers={
                    "X-API-Key": INTERNAL_API_KEY,
                    "Content-Type": "application/json",
                },
                json=registration_payload,
            ) as response:
                print(f"📡 Registration response status: {response.status}")

                if response.status == 200:
                    data = await response.json()
                    print("✅ Company registered successfully!")
                    print(
                        f"   📋 Registration result: {json.dumps(data, indent=2, ensure_ascii=False)}"
                    )
                else:
                    error_text = await response.text()
                    print(f"❌ Registration failed: {error_text}")
                    return

        except Exception as e:
            print(f"❌ Error registering company: {e}")
            return

        print()

        # 3. Verify registration by querying again
        print("3️⃣ Verifying registration...")
        try:
            async with session.get(
                f"{AI_SERVICE_URL}/api/admin/companies/{test_company_id}",
                headers={"X-API-Key": INTERNAL_API_KEY},
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Company verification successful!")
                    print(
                        f"   📋 Verified data: {json.dumps(data, indent=2, ensure_ascii=False)}"
                    )
                else:
                    error_text = await response.text()
                    print(f"❌ Verification failed: {error_text}")
        except Exception as e:
            print(f"❌ Error verifying company: {e}")

    print()
    print("🎯 SUMMARY:")
    print("   - AI Service has company registration endpoint")
    print("   - Registration saves to both database and memory")
    print("   - Backend should call this endpoint when creating companies")
    print(
        "   - If Backend doesn't call this, AI Service won't know about new companies"
    )


if __name__ == "__main__":
    asyncio.run(test_company_registration())
