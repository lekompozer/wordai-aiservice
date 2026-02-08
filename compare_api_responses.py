#!/usr/bin/env python3
"""Compare API responses for crawled vs working books"""

import requests
import json

API_URL = "https://ai.wordai.pro/api/v1"

# Test slugs
CRAWLED_BOOK = "kinh-nghiem-thanh-cong-cua-ong-chu-nho"
WORKING_BOOK = "tieu-su-cac-quoc-gia-qua-goc-nhin-lay-loi"  # Book with chapters visible

print("=" * 70)
print("🔍 Compare API Responses: Crawled vs Working Book")
print("=" * 70)

for label, slug in [("CRAWLED BOOK", CRAWLED_BOOK), ("WORKING BOOK", WORKING_BOOK)]:
    print(f"\n{'='*70}")
    print(f"{label}: {slug}")
    print("=" * 70)

    url = f"{API_URL}/books/slug/{slug}/preview"
    r = requests.get(url, timeout=10)

    print(f"URL: {url}")
    print(f"Status: {r.status_code}")

    if r.status_code == 200:
        data = r.json()

        print(f"\n📖 Book Info:")
        print(f"  title: {data.get('title', 'N/A')[:60]}")
        print(f"  book_id: {data.get('book_id', 'N/A')}")
        print(f"  slug: {data.get('slug', 'N/A')}")

        # Check chapters
        chapters = data.get("chapters", [])
        print(f"\n📄 Chapters: {len(chapters)}")

        if chapters:
            for idx, ch in enumerate(chapters[:3], 1):
                print(f"\n  [{idx}] {ch.get('title', 'N/A')[:50]}")
                print(f"      chapter_id: {ch.get('chapter_id', 'N/A')}")
                print(f"      chapter_number: {ch.get('chapter_number', 'N/A')}")
                print(f"      slug: {ch.get('slug', 'N/A')}")
                print(f"      chapter_type: {ch.get('chapter_type', 'N/A')}")
                print(f"      content_mode: {ch.get('content_mode', 'N/A')}")
                print(f"      pdf_url: {ch.get('pdf_url', 'N/A')[:60]}")

                # Show all keys
                print(f"      Fields: {list(ch.keys())}")
        else:
            print("  ❌ NO CHAPTERS IN RESPONSE!")
            print(f"\n  Response keys: {list(data.keys())}")

            # Try to find chapters field
            if "table_of_contents" in data:
                print(
                    f"  Found table_of_contents: {len(data.get('table_of_contents', []))} items"
                )
    else:
        print(f"❌ Failed: {r.status_code}")
        print(f"Response: {r.text[:300]}")

print("\n" + "=" * 70)
