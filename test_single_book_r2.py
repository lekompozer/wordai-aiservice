#!/usr/bin/env python3
"""Test single book with cover + PDF upload to R2"""

import sys

sys.path.insert(0, "/app")

from crawler.test_crawler_clean import TestBookCrawler


def main():
    print("=" * 60)
    print("📚 Test Single Book - Cover + PDF Upload")
    print("=" * 60)

    crawler = TestBookCrawler()
    book_ids = crawler.crawl_test_books(category_slug="kinh-te-quan-ly", limit=1)

    print("\n" + "=" * 60)
    print("📊 TEST RESULT")
    print("=" * 60)

    if book_ids:
        print(f"✅ Successfully created: {book_ids[0]}")

        # Check database for cover URL
        from src.database.db_manager import DBManager

        db_manager = DBManager()
        db = db_manager.db

        book = db.online_books.find_one({"book_id": book_ids[0]})
        if book:
            print(f"\n📖 Book Details:")
            print(f"   Title: {book['title']}")
            print(f"   Cover URL: {book.get('cover_image_url', 'N/A')}")
            print(
                f"   Community Cover: {book.get('community_config', {}).get('cover_image_url', 'N/A')}"
            )

            # Check chapter
            chapter = db.book_chapters.find_one({"book_id": book_ids[0]})
            if chapter:
                print(f"   PDF URL: {chapter.get('pdf_url', 'N/A')}")

                # Verify both URLs are R2 URLs
                cover_ok = book.get("cover_image_url", "").startswith(
                    "https://static.wordai.pro/books/covers/"
                )
                pdf_ok = chapter.get("pdf_url", "").startswith(
                    "https://static.wordai.pro/books/crawled/"
                )

                print(f"\n🔍 Validation:")
                print(
                    f"   Cover R2: {'✅' if cover_ok else '❌'} {book.get('cover_image_url', '')[:80]}"
                )
                print(
                    f"   PDF R2:   {'✅' if pdf_ok else '❌'} {chapter.get('pdf_url', '')[:80]}"
                )

                if cover_ok and pdf_ok:
                    print(f"\n✅ ALL R2 URLS CORRECT!")
                else:
                    print(f"\n❌ R2 URLs NOT CORRECT!")
    else:
        print("❌ Book creation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
