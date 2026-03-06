#!/usr/bin/env python3
"""
Test USDT Subscription Endpoint
Quick test to verify endpoint is accessible
"""

import requests
import json

# Test endpoint
BASE_URL = "https://ai.wordai.pro"
ENDPOINT = f"{BASE_URL}/api/v1/payments/usdt/subscription/create"

print(f"🧪 Testing USDT Subscription Endpoint")
print(f"📍 URL: {ENDPOINT}")
print("-" * 60)

# Test 1: Check if endpoint exists (should get 401/403, not 404)
print("\n1️⃣ Testing without authentication (should get 401/403, NOT 404)...")
try:
    response = requests.post(
        ENDPOINT, json={"plan": "premium", "duration": "3_months"}, timeout=10
    )
    print(f"   Status Code: {response.status_code}")

    if response.status_code == 404:
        print("   ❌ ERROR: Endpoint not found (404) - Router not mounted!")
    elif response.status_code in [401, 403]:
        print("   ✅ SUCCESS: Endpoint exists (requires authentication)")
    elif response.status_code == 422:
        print("   ✅ SUCCESS: Endpoint exists (validation error)")
    else:
        print(f"   ⚠️  Unexpected status: {response.status_code}")

    print(f"   Response: {response.text[:200]}")

except Exception as e:
    print(f"   ❌ Request failed: {e}")

# Test 2: Check rate endpoint (no auth required)
print("\n2️⃣ Testing rate endpoint (no auth)...")
try:
    rate_endpoint = f"{BASE_URL}/api/v1/payments/usdt/subscription/rate"
    response = requests.get(rate_endpoint, timeout=10)
    print(f"   Status Code: {response.status_code}")

    if response.status_code == 200:
        print("   ✅ SUCCESS: Rate endpoint works")
        data = response.json()
        print(f"   Rate: {data}")
    elif response.status_code == 404:
        print("   ❌ ERROR: Rate endpoint not found - Router not mounted!")
    else:
        print(f"   Response: {response.text[:200]}")

except Exception as e:
    print(f"   ❌ Request failed: {e}")

# Test 3: List all available routes
print("\n3️⃣ Testing OpenAPI docs...")
try:
    docs_url = f"{BASE_URL}/docs"
    print(f"   Docs URL: {docs_url}")
    print("   Please check if '/api/v1/payments/usdt/subscription' routes are listed")
except Exception as e:
    print(f"   ❌ Failed: {e}")

print("\n" + "=" * 60)
print("🔍 DIAGNOSIS:")
print("=" * 60)
print(
    """
If you see 404 errors:
1. Router not included in app.py
2. Server needs restart
3. Import error in usdt_subscription_routes.py

If you see 401/403 errors:
✅ Endpoint exists, authentication required

If you see 422 errors:
✅ Endpoint exists, validation error
"""
)
