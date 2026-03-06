#!/usr/bin/env python3
"""Test API endpoint for book detail"""

import requests
import json

# Test with latest book
BOOK_SLUG = "kinh-nghiem-thanh-cong-cua-ong-chu-nho"
API_URL = "https://ai.wordai.pro/api/v1"

print("=" * 60)
print(f"🔍 Testing API: GET /books/slug/{BOOK_SLUG}/preview")
print("=" * 60)

try:
    # Get book detail
    response = requests.get(f"{API_URL}/books/slug/{BOOK_SLUG}/preview", timeout=10)

    print(f"\nStatus Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()

        print(f"\n📖 Book Response:")
        print(f"  Title: {data.get('title', 'N/A')}")
        print(f"  Book ID: {data.get('book_id', 'N/A')}")
        print(f"  Cover: {data.get('cover_image_url', 'N/A')[:70]}")

        # Check chapters
        chapters = data.get("chapters", [])
        print(f"\n📄 Chapters in response: {len(chapters)}")

        if chapters:
            for idx, ch in enumerate(chapters[:3], 1):
                print(f"\n  [{idx}] {ch.get('title', 'N/A')}")
                print(f"      chapter_id: {ch.get('chapter_id', 'N/A')}")
                print(f"      chapter_number: {ch.get('chapter_number', 'N/A')}")
                print(f"      chapter_type: {ch.get('chapter_type', 'N/A')}")
                print(f"      pdf_url: {ch.get('pdf_url', 'N/A')[:70]}")
        else:
            print("  ❌ NO CHAPTERS IN API RESPONSE!")

        # Show raw structure
        print(f"\n📋 Response Keys: {list(data.keys())}")

        # Save full response
        with open("/tmp/api_response.json", "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"\n💾 Full response saved to /tmp/api_response.json")

    else:
        print(f"❌ API returned {response.status_code}")
        print(f"Response: {response.text[:500]}")

    print("\n" + "=" * 60)

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
