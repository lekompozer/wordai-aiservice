#!/usr/bin/env python3
"""Test API response for crawled book"""

import sys

sys.path.insert(0, "/app")

import requests

url = "http://localhost:8000/api/v1/books/slug/kinh-nghiem-thanh-cong-cua-ong-chu-nho/preview?language=vi"
r = requests.get(url, timeout=5)
print(f"Status: {r.status_code}")

if r.status_code == 200:
    data = r.json()
    print(f"\n📖 Book:")
    print(f"  Title: {data.get('title', 'N/A')}")
    print(f"  Book ID: {data.get('book_id', 'N/A')}")
    print(f"  Slug: {data.get('slug', 'N/A')}")

    chapters = data.get("chapters", [])
    print(f"\n📄 Chapters: {len(chapters)}")

    if chapters:
        for idx, ch in enumerate(chapters, 1):
            print(f"\n  [{idx}] {ch.get('title', 'N/A')}")
            print(f"      chapter_id: {ch.get('chapter_id', 'N/A')}")
            print(f"      chapter_number: {ch.get('chapter_number', 'N/A')}")
            print(f"      slug: {ch.get('slug', 'N/A')}")
            print(f"      chapter_type: {ch.get('chapter_type', 'N/A')}")
            print(f"      content_mode: {ch.get('content_mode', 'N/A')}")
            print(f"      pdf_url: {ch.get('pdf_url', 'N/A')[:60]}")
            print(f"      All fields: {list(ch.keys())}")
    else:
        print("  ❌ NO CHAPTERS!")
        print(f"\n  Response keys: {list(data.keys())[:20]}")
else:
    print(f"❌ Failed: {r.status_code}")
