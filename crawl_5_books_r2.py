#!/usr/bin/env python3
"""Crawl 5 books from Kinh Tế - Quản Lý"""

import sys

sys.path.insert(0, "/app")

from crawler.test_crawler_clean import TestBookCrawler
from src.database.db_manager import DBManager


def main():
    print("=" * 60)
    print("📚 Crawl 5 Books - Full R2 Upload Test")
    print("=" * 60)

    # Cleanup old books first
    print("\n🧹 Cleaning up old crawled books...")
    db_manager = DBManager()
    db = db_manager.db

    deleted_books = db.online_books.delete_many(
        {"metadata.source": "nhasachmienphi.com"}
    )
    deleted_chapters = db.book_chapters.delete_many(
        {
            "book_id": {
                "$in": [
                    b["book_id"] for b in deleted_books.deleted_count > 0 and [] or []
                ]
            }
        }
    )
    print(f"   ✅ Deleted {deleted_books.deleted_count} old books")

    # Crawl 5 books
    crawler = TestBookCrawler()
    book_ids = crawler.crawl_test_books(category_slug="kinh-te-quan-ly", limit=5)

    print("\n" + "=" * 60)
    print("📊 CRAWL SUMMARY")
    print("=" * 60)

    if book_ids:
        print(f"✅ Successfully created: {len(book_ids)} books\n")

        # Verify all R2 URLs
        all_correct = True
        for idx, book_id in enumerate(book_ids, 1):
            book = db.online_books.find_one({"book_id": book_id})
            chapter = db.book_chapters.find_one({"book_id": book_id})

            if book and chapter:
                cover_ok = book.get("cover_image_url", "").startswith(
                    "https://static.wordai.pro/books/covers/"
                )
                pdf_ok = chapter.get("pdf_url", "").startswith(
                    "https://static.wordai.pro/books/crawled/"
                )

                status = "✅" if (cover_ok and pdf_ok) else "❌"
                print(f"{status} [{idx}] {book['title'][:50]}")
                print(
                    f"       Cover: {cover_ok and '✅' or '❌'} {book.get('cover_image_url', '')[:60]}..."
                )
                print(
                    f"       PDF:   {pdf_ok and '✅' or '❌'} {chapter.get('pdf_url', '')[:60]}..."
                )

                if not (cover_ok and pdf_ok):
                    all_correct = False

        print("\n" + "=" * 60)
        if all_correct:
            print("✅ ALL BOOKS HAVE CORRECT R2 URLS!")
        else:
            print("❌ SOME BOOKS HAVE INCORRECT URLS!")
        print("=" * 60)

    else:
        print("❌ No books created")
        sys.exit(1)


if __name__ == "__main__":
    main()
