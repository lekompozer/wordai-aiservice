#!/usr/bin/env python3
"""Test community books API"""

import requests
import json

API_URL = "https://ai.wordai.pro/api/v1"

print("=" * 60)
print("🔍 Testing Community Books API")
print("=" * 60)

# Test newest
print("\n1️⃣  Testing: /books/community/books?sort_by=newest&page=1&limit=5")
r = requests.get(
    f"{API_URL}/books/community/books?sort_by=newest&page=1&limit=5", timeout=10
)

print(f"Status: {r.status_code}")

if r.status_code == 200:
    data = r.json()
    books = data.get("books", [])
    print(f"✅ Books returned: {len(books)}")

    for idx, book in enumerate(books[:3], 1):
        print(f"\n  [{idx}] {book.get('title', 'N/A')[:50]}")
        print(f"      slug: {book.get('slug', 'N/A')}")
        print(f"      category: {book.get('category', 'N/A')}")

        recent_chapters = book.get("recent_chapters", [])
        print(f"      recent_chapters: {len(recent_chapters)}")

        if recent_chapters:
            ch = recent_chapters[0]
            print(f"        - {ch.get('title', 'N/A')}: slug={ch.get('slug', 'N/A')}")
else:
    print(f"❌ Failed: {r.status_code}")
    print(f"Response: {r.text[:500]}")

# Test popular
print("\n2️⃣  Testing: /books/community/books?sort_by=popular&page=1&limit=5")
r = requests.get(
    f"{API_URL}/books/community/books?sort_by=popular&page=1&limit=5", timeout=10
)
print(f"Status: {r.status_code} {'✅' if r.status_code == 200 else '❌'}")

print("\n" + "=" * 60)
