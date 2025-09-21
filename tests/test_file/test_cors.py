#!/usr/bin/env python3
"""
Test CORS configuration for production deployment
"""

import requests
import json


def test_cors():
    """Test CORS configuration"""
    api_url = "https://ai.aimoney.io.vn"
    frontend_origin = "https://aivungtau.com"

    print("🔍 Testing CORS configuration...")
    print(f"   API URL: {api_url}")
    print(f"   Frontend Origin: {frontend_origin}")
    print("")

    # Test endpoints
    endpoints = ["/health", "/providers", "/api/chat/providers"]

    for endpoint in endpoints:
        url = f"{api_url}{endpoint}"
        print(f"📡 Testing endpoint: {endpoint}")

        try:
            # Test preflight OPTIONS request
            print(f"   🔍 OPTIONS request...")
            headers = {
                "Origin": frontend_origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type",
            }

            response = requests.options(url, headers=headers, timeout=10)
            print(f"   Status: {response.status_code}")

            # Check CORS headers
            cors_headers = [
                "Access-Control-Allow-Origin",
                "Access-Control-Allow-Methods",
                "Access-Control-Allow-Headers",
                "Access-Control-Allow-Credentials",
            ]

            for header in cors_headers:
                if header in response.headers:
                    print(f"   ✅ {header}: {response.headers[header]}")
                else:
                    print(f"   ❌ {header}: NOT PRESENT")

            # Test actual GET request
            print(f"   🔍 GET request...")
            headers = {"Origin": frontend_origin}
            response = requests.get(url, headers=headers, timeout=10)
            print(f"   Status: {response.status_code}")

            if "Access-Control-Allow-Origin" in response.headers:
                print(
                    f"   ✅ Access-Control-Allow-Origin: {response.headers['Access-Control-Allow-Origin']}"
                )
            else:
                print(f"   ❌ Access-Control-Allow-Origin: NOT PRESENT")

        except requests.exceptions.RequestException as e:
            print(f"   ❌ Request failed: {e}")

        print("")


def test_providers_api():
    """Test the specific /providers endpoint"""
    print("🎯 Testing /providers endpoint specifically...")

    api_url = "https://ai.aimoney.io.vn"
    endpoints = ["/providers", "/api/chat/providers"]

    for endpoint in endpoints:
        url = f"{api_url}{endpoint}"
        print(f"📡 Testing: {url}")

        try:
            headers = {
                "Origin": "https://aivungtau.com",
                "User-Agent": "Mozilla/5.0 (compatible; CORS-Test/1.0)",
            }

            response = requests.get(url, headers=headers, timeout=10)
            print(f"   Status: {response.status_code}")
            print(f"   Content-Type: {response.headers.get('Content-Type', 'N/A')}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    if "providers" in data:
                        print(f"   ✅ Found {len(data['providers'])} providers")
                        for provider in data["providers"][:3]:  # Show first 3
                            print(
                                f"      - {provider.get('id', 'N/A')}: {provider.get('name', 'N/A')}"
                            )
                    else:
                        print(f"   ⚠️ Response structure: {list(data.keys())}")
                except json.JSONDecodeError:
                    print(f"   ❌ Invalid JSON response")
                    print(f"   Response: {response.text[:200]}...")
            else:
                print(f"   ❌ Error response: {response.text[:200]}...")

        except requests.exceptions.RequestException as e:
            print(f"   ❌ Request failed: {e}")

        print("")


if __name__ == "__main__":
    print("🧪 CORS Configuration Test")
    print("=" * 50)

    test_cors()
    test_providers_api()

    print("✅ CORS test completed")
