#!/usr/bin/env python3
"""Verify crawled books have full metadata"""

from src.database.db_manager import DBManager


def check_metadata():
    db_manager = DBManager()
    db = db_manager.db

    print("=" * 80)
    print("📚 Verify Crawled Books Metadata")
    print("=" * 80)

    books = list(db.online_books.find({"source": "nhasachmienphi.com"}))

    print(f"\nTotal books: {len(books)}\n")

    for book in books:
        print(f"\n📖 {book['title']}")
        print(f"   Book ID: {book['book_id']}")
        print(f"   Slug: {book['slug']}")

        # Check metadata
        cc = book.get("community_config", {})
        ac = book.get("access_config", {})

        print(f"\n   ✅ METADATA:")
        cover = book.get("cover_image_url") or "None"
        print(f"      • cover_url: {cover if cover == 'None' else cover[:80]}")
        print(f"      • description: {len(book.get('description', ''))} chars")
        print(f"      • category: {cc.get('category', 'None')}")
        print(f"      • tags: {cc.get('tags', [])}")
        print(f"      • short_desc: {len(cc.get('short_description', ''))} chars")
        print(f"      • is_public: {cc.get('is_public', False)}")
        print(f"      • published_at: {cc.get('published_at', 'None')}")

        print(f"\n   💰 PRICING:")
        print(f"      • one_time: {ac.get('one_time_view_points', 'None')} pts")
        print(f"      • forever: {ac.get('forever_view_points', 'None')} pts")
        print(f"      • download: Disabled ({ac.get('is_download_enabled', False)})")

        # Check chapter
        chapter = db.book_chapters.find_one({"book_id": book["book_id"]})
        if chapter:
            print(f"\n   📄 CHAPTER:")
            print(f"      • content_type: {chapter.get('content_type', 'None')}")
            print(
                f"      • pdf_url: {chapter.get('pdf_file', {}).get('public_url', 'None')[:80]}"
            )

        print("\n" + "-" * 80)

    print(f"\n✅ Verification complete!")


if __name__ == "__main__":
    check_metadata()
