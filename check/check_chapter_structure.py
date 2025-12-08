#!/usr/bin/env python3
"""
Check chapter and document structure for book
"""

import sys
from pathlib import Path
from pprint import pprint

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from database.db_manager import DBManager

# Get DB connection
db_manager = DBManager()
db = db_manager.db

book_id = "book_df213acf187b"
chapter_id = "chapter_8fa174dd3f71"

print("\n" + "=" * 70)
print("📚 CHECKING CHAPTER AND DOCUMENT STRUCTURE")
print("=" * 70)

# Get chapter
chapter = db.book_chapters.find_one({"chapter_id": chapter_id}, {"_id": 0})

print(f"\n📖 Chapter: {chapter_id}")
if chapter:
    print(f"   Title: {chapter.get('title')}")
    print(f"   content_source: {chapter.get('content_source', 'NOT SET')}")
    print(f"   document_id: {chapter.get('document_id', 'NOT SET')}")
    print(f"   Has content_html field: {'content_html' in chapter}")
    if "content_html" in chapter:
        content = chapter.get("content_html") or ""
        print(f"   content_html length: {len(content)} chars")
        if len(content) > 0:
            print(f"   content_html preview: {content[:200]}...")
    print("\n   Full chapter structure:")
    pprint(chapter, width=100)
else:
    print("   ❌ Chapter not found!")

# If has document_id, check document
if chapter and chapter.get("document_id"):
    doc_id = chapter["document_id"]
    print(f"\n📄 Document: {doc_id}")

    document = db.documents.find_one(
        {"document_id": doc_id},
        {
            "_id": 0,
            "document_id": 1,
            "name": 1,
            "title": 1,
            "content": 1,
            "content_html": 1,
            "file_size_bytes": 1,
        },
    )

    if document:
        print(f"   Name: {document.get('name', 'N/A')}")
        print(f"   Title: {document.get('title', 'N/A')}")
        print(f"   Has 'content' field: {'content' in document}")
        print(f"   Has 'content_html' field: {'content_html' in document}")

        if "content" in document:
            content = document.get("content") or ""
            print(f"   'content' length: {len(content)} chars")
            if len(content) > 0:
                print(f"   'content' preview: {content[:200]}...")

        if "content_html" in document:
            content_html = document.get("content_html") or ""
            print(f"   'content_html' length: {len(content_html)} chars")
            if len(content_html) > 0:
                print(f"   'content_html' preview: {content_html[:200]}...")

        print(f"   File size: {document.get('file_size_bytes', 0)} bytes")
    else:
        print("   ❌ Document not found!")

print("\n" + "=" * 70)
print("💡 RECOMMENDATIONS:")
print("=" * 70)

if chapter:
    content_source = chapter.get("content_source", "NOT SET")

    if content_source == "document":
        print("✅ Chapter uses 'document' source (correct)")
        print("   Content should be loaded from documents collection")
        if chapter.get("document_id"):
            print(f"   Linked to document: {chapter['document_id']}")
            if document:
                if "content_html" in document and document.get("content_html"):
                    print("   ✅ Document has content_html - GOOD!")
                elif "content" in document and document.get("content"):
                    print(
                        "   ⚠️  Document has 'content' field (should be 'content_html')"
                    )
                else:
                    print("   ❌ Document has NO content!")
        else:
            print("   ❌ No document_id linked!")

    elif content_source == "inline":
        print("✅ Chapter uses 'inline' source")
        print("   Content should be in chapter.content_html field")
        if "content_html" in chapter and chapter.get("content_html"):
            print("   ✅ Chapter has content_html - GOOD!")
        else:
            print("   ❌ Chapter missing content_html!")

    else:
        print(f"⚠️  Unknown content_source: {content_source}")

print("=" * 70 + "\n")
