#!/usr/bin/env python3
"""
Inspect slide HTML content in MongoDB
"""
import sys

sys.path.insert(0, "/app")

from config.config import get_mongodb
from bs4 import BeautifulSoup

file_id = "file_66e18e975d12"
user_id = "17BeaeikPBQYk8OWeDUkqm0Ov8e2"

print(f"\n🔍 Inspecting HTML for file {file_id}")
print("=" * 80)

db = get_mongodb()
documents = db.documents

# Get documents for this file
docs = documents.find({"file_id": file_id, "user_id": user_id}).sort("created_at", -1)

for idx, doc in enumerate(docs):
    print(f"\n📄 Document {idx + 1}:")
    print(f"   Document ID: {doc.get('document_id')}")
    print(f"   Title: {doc.get('title')}")
    print(f"   Created: {doc.get('created_at')}")

    html_content = doc.get("content_html", "")

    if html_content:
        print(f"\n   📝 HTML Content ({len(html_content)} chars):")
        print("   " + "=" * 76)

        # Parse HTML to extract slide divs
        soup = BeautifulSoup(html_content, "html.parser")

        # Find slide divs (width:1920px)
        slide_divs = soup.find_all("div", style=lambda s: s and "1920px" in s)

        if slide_divs:
            print(f"   ✅ Found {len(slide_divs)} slide div(s)")

            for i, slide_div in enumerate(slide_divs[:2], 1):  # Show first 2 slides
                print(f"\n   🎬 Slide {i}:")
                slide_html = str(slide_div)
                print(f"      Length: {len(slide_html)} chars")
                print(f"      Preview: {slide_html[:300]}...")

                # Check for inline styles
                style_attr = slide_div.get("style", "")
                if style_attr:
                    print(f"\n      Styles found: {style_attr[:200]}...")
                else:
                    print(f"      ⚠️ NO inline styles!")

                # Check for nested elements
                children = slide_div.find_all(["h1", "h2", "h3", "p", "div", "span"])
                print(f"      Elements: {len(children)} nested tags")

                # Check if elements have styles
                styled_count = sum(1 for child in children if child.get("style"))
                print(f"      Styled elements: {styled_count}/{len(children)}")
        else:
            print(f"   ⚠️ No slide divs with width:1920px found!")
            print(f"\n   Raw HTML (first 1000 chars):")
            print(f"   {html_content[:1000]}")
    else:
        print(f"   ❌ No HTML content!")

    print("\n   " + "=" * 76)

    if idx >= 0:  # Show only latest document
        break

print("\n" + "=" * 80)
