#!/usr/bin/env python3
"""
Test script to verify marketplace API response structures
"""
import requests
import json

BASE_URL = "https://ai.wordai.pro/api/v1/marketplace"


def test_endpoint(name, url):
    """Test an endpoint and print response structure"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    print(f"{'='*60}")

    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Response Keys: {list(data.keys())}")

            if "data" in data:
                print(f"Data Keys: {list(data['data'].keys())}")

                # Print sample of arrays
                for key in data["data"]:
                    value = data["data"][key]
                    if isinstance(value, list):
                        print(f"  - {key}: array with {len(value)} items")
                        if len(value) > 0:
                            print(f"    First item keys: {list(value[0].keys())}")
                    elif isinstance(value, dict):
                        print(f"  - {key}: {value}")
                    else:
                        print(f"  - {key}: {value}")

            print(f"\n✅ Success")
        else:
            print(f"❌ Error: {response.text}")

    except Exception as e:
        print(f"❌ Exception: {e}")


def main():
    """Run all tests"""
    print("🧪 Testing Marketplace API Endpoints")
    print("=" * 60)

    # Test browse tests
    test_endpoint(
        "Browse Tests - Top Rated", f"{BASE_URL}/tests?sort=top_rated&page_size=8"
    )

    test_endpoint("Browse Tests - Newest", f"{BASE_URL}/tests?sort=newest&page_size=8")

    # Test leaderboards
    test_endpoint("Leaderboard - Top Tests", f"{BASE_URL}/leaderboard/tests?period=all")

    test_endpoint("Leaderboard - Top Users", f"{BASE_URL}/leaderboard/users?period=all")

    print("\n" + "=" * 60)
    print("🎉 All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
