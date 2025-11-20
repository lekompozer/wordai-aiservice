"""
Test script for Book Cover AI Generation API
Tests the OpenAI gpt-image-1 integration
"""

import requests
import json
import base64
import os
from datetime import datetime

# Configuration
# BASE_URL = "http://localhost:8000"  # Change to production URL when needed
BASE_URL = "https://wordai.tech"  # Production

# Get Firebase ID token (you need to login first)
# For testing, you can get this from browser DevTools after logging in
FIREBASE_TOKEN = os.getenv("FIREBASE_TOKEN", "YOUR_FIREBASE_ID_TOKEN_HERE")


def save_image(image_base64: str, filename: str):
    """Save base64 image to file"""
    image_data = base64.b64decode(image_base64)
    with open(filename, "wb") as f:
        f.write(image_data)
    print(f"✅ Saved image to {filename}")


def test_get_styles():
    """Test GET /api/v1/books/ai/cover/styles"""
    print("\n" + "=" * 80)
    print("TEST 1: Get Available Styles (No Auth Required)")
    print("=" * 80)

    url = f"{BASE_URL}/api/v1/books/ai/cover/styles"
    response = requests.get(url)

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    return response.status_code == 200


def test_generate_cover_fantasy():
    """Test POST /api/v1/books/ai/cover/generate with fantasy style"""
    print("\n" + "=" * 80)
    print("TEST 2: Generate Fantasy Book Cover")
    print("=" * 80)

    url = f"{BASE_URL}/api/v1/books/ai/cover/generate"
    headers = {
        "Authorization": f"Bearer {FIREBASE_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": "A magical castle floating in the sky surrounded by dragons and mystical clouds, epic fantasy book cover",
        "style": "fantasy art",
    }

    print(f"Request: {json.dumps(payload, indent=2)}")
    print("⏳ Generating image (this may take 10-15 seconds)...\n")

    response = requests.post(url, headers=headers, json=payload)

    print(f"Status Code: {response.status_code}")

    result = response.json()
    print(f"Success: {result.get('success')}")
    print(f"Prompt Used: {result.get('prompt_used')}")
    print(f"Style: {result.get('style')}")
    print(f"Model: {result.get('model')}")
    print(f"Timestamp: {result.get('timestamp')}")
    print(f"Generation Time: {result.get('generation_time_ms')}ms")

    if result.get("error"):
        print(f"❌ Error: {result.get('error')}")
        return False

    if result.get("image_base64"):
        image_base64 = result["image_base64"]
        print(f"Image Size: {len(image_base64)} bytes (base64)")

        # Save image
        filename = f"test_fantasy_cover_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        save_image(image_base64, filename)

        return True

    return False


def test_generate_cover_minimalist():
    """Test POST /api/v1/books/ai/cover/generate with minimalist style"""
    print("\n" + "=" * 80)
    print("TEST 3: Generate Minimalist Book Cover")
    print("=" * 80)

    url = f"{BASE_URL}/api/v1/books/ai/cover/generate"
    headers = {
        "Authorization": f"Bearer {FIREBASE_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": "A modern business book about leadership, clean design with geometric shapes",
        "style": "minimalist",
    }

    print(f"Request: {json.dumps(payload, indent=2)}")
    print("⏳ Generating image (this may take 10-15 seconds)...\n")

    response = requests.post(url, headers=headers, json=payload)

    print(f"Status Code: {response.status_code}")

    result = response.json()
    print(f"Success: {result.get('success')}")
    print(f"Prompt Used: {result.get('prompt_used')}")
    print(f"Style: {result.get('style')}")
    print(f"Model: {result.get('model')}")
    print(f"Generation Time: {result.get('generation_time_ms')}ms")

    if result.get("error"):
        print(f"❌ Error: {result.get('error')}")
        return False

    if result.get("image_base64"):
        image_base64 = result["image_base64"]
        print(f"Image Size: {len(image_base64)} bytes (base64)")

        # Save image
        filename = f"test_minimalist_cover_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        save_image(image_base64, filename)

        return True

    return False


def test_generate_cover_no_style():
    """Test POST /api/v1/books/ai/cover/generate without style"""
    print("\n" + "=" * 80)
    print("TEST 4: Generate Book Cover Without Style")
    print("=" * 80)

    url = f"{BASE_URL}/api/v1/books/ai/cover/generate"
    headers = {
        "Authorization": f"Bearer {FIREBASE_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": "A sci-fi book cover with a futuristic city and flying cars",
    }

    print(f"Request: {json.dumps(payload, indent=2)}")
    print("⏳ Generating image (this may take 10-15 seconds)...\n")

    response = requests.post(url, headers=headers, json=payload)

    print(f"Status Code: {response.status_code}")

    result = response.json()
    print(f"Success: {result.get('success')}")
    print(f"Prompt Used: {result.get('prompt_used')}")
    print(f"Model: {result.get('model')}")
    print(f"Generation Time: {result.get('generation_time_ms')}ms")

    if result.get("error"):
        print(f"❌ Error: {result.get('error')}")
        return False

    if result.get("image_base64"):
        image_base64 = result["image_base64"]
        filename = f"test_scifi_cover_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        save_image(image_base64, filename)
        return True

    return False


def test_generate_cover_invalid_auth():
    """Test POST with invalid authentication"""
    print("\n" + "=" * 80)
    print("TEST 5: Generate Cover with Invalid Auth (Should Fail)")
    print("=" * 80)

    url = f"{BASE_URL}/api/v1/books/ai/cover/generate"
    headers = {
        "Authorization": "Bearer INVALID_TOKEN",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": "Test image",
        "style": "minimalist",
    }

    response = requests.post(url, headers=headers, json=payload)

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    # Should return 401 or 403
    return response.status_code in [401, 403]


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("BOOK COVER AI GENERATION API - TEST SUITE")
    print("=" * 80)
    print(f"Base URL: {BASE_URL}")
    print(f"Auth Token: {'✅ Set' if FIREBASE_TOKEN != 'YOUR_FIREBASE_ID_TOKEN_HERE' else '❌ Not Set'}")

    if FIREBASE_TOKEN == "YOUR_FIREBASE_ID_TOKEN_HERE":
        print("\n⚠️  WARNING: Please set FIREBASE_TOKEN environment variable or update the script")
        print("   You can get your token from browser DevTools after logging in")
        print("   Or run: export FIREBASE_TOKEN='your_token_here'\n")

    results = []

    # Test 1: Get styles (no auth)
    results.append(("Get Styles", test_get_styles()))

    # Only run auth-required tests if token is set
    if FIREBASE_TOKEN != "YOUR_FIREBASE_ID_TOKEN_HERE":
        # Test 2: Generate fantasy cover
        results.append(("Generate Fantasy Cover", test_generate_cover_fantasy()))

        # Test 3: Generate minimalist cover
        results.append(("Generate Minimalist Cover", test_generate_cover_minimalist()))

        # Test 4: Generate without style
        results.append(("Generate Without Style", test_generate_cover_no_style()))

        # Test 5: Invalid auth
        results.append(("Invalid Auth Test", test_generate_cover_invalid_auth()))
    else:
        print("\n⏭️  Skipping auth-required tests (token not set)")

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 80)


if __name__ == "__main__":
    run_all_tests()
