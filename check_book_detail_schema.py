#!/usr/bin/env python3
from src.database.db_manager import DBManager

db = DBManager().db

# Lấy book "Tiểu Sử Các Quốc Gia..." làm mẫu (working book)
print("=== WORKING BOOK (Tiểu Sử...) ===\n")
working_book = db.online_books.find_one(
    {"slug": "tieu-su-cac-quoc-gia-qua-goc-nhin-lay-loi"}
)
if working_book:
    print(f"book_id: {working_book.get('book_id')}")
    print(f"title: {working_book.get('title')}")
    print(
        f"description: {working_book.get('description')[:100] if working_book.get('description') else 'NONE'}"
    )
    print(f"cover_image_url: {working_book.get('cover_image_url')}")
    print(f"visibility: {working_book.get('visibility')}")
    print(f"authors: {working_book.get('authors')}")

    cc = working_book.get("community_config", {})
    print(f"\ncommunity_config:")
    print(f"  is_public: {cc.get('is_public')}")
    print(f"  category: {cc.get('category')}")
    print(f"  tags: {cc.get('tags')}")
    print(f"  short_description: {cc.get('short_description')}")
    print(f"  published_at: {cc.get('published_at')}")

    ac = working_book.get("access_config")
    print(f"\naccess_config: {ac}")

    # Check chapters
    print("\n=== CHAPTERS ===")
    chapters = list(db.book_chapters.find({"book_id": working_book["book_id"]}))
    print(f"Total chapters: {len(chapters)}")
    if chapters:
        ch = chapters[0]
        print(f"Chapter 1: {ch.get('title')}")
        print(f"  content_type: {ch.get('content_type')}")
        print(f"  has pdf_file: {bool(ch.get('pdf_file'))}")
        if ch.get("pdf_file"):
            print(f"  pdf_file.public_url: {ch['pdf_file'].get('public_url')}")

# Lấy book crawled mới
print("\n\n=== CRAWLED BOOK (Để xây dựng...) ===\n")
crawled = db.online_books.find_one({"slug": "de-xay-dung-doanh-nghiep-hieu-qua"})
if crawled:
    print(f"book_id: {crawled.get('book_id')}")
    print(f"title: {crawled.get('title')}")
    print(
        f"description: {crawled.get('description')[:100] if crawled.get('description') else 'NONE'}"
    )
    print(f"cover_image_url: {crawled.get('cover_image_url')}")

    cc = crawled.get("community_config", {})
    print(f"\ncommunity_config:")
    print(f"  is_public: {cc.get('is_public')}")
    print(f"  category: {cc.get('category')}")
    print(f"  tags: {cc.get('tags')}")
    print(f"  short_description: {cc.get('short_description')}")

    ac = crawled.get("access_config")
    print(f"\naccess_config: {ac}")

    print("\n=== CHAPTERS ===")
    chapters = list(db.book_chapters.find({"book_id": crawled["book_id"]}))
    print(f"Total chapters: {len(chapters)}")
    if chapters:
        ch = chapters[0]
        print(f"Chapter: {ch.get('title')}")
        print(f"  content_type: {ch.get('content_type')}")
        if ch.get("pdf_file"):
            print(f"  pdf_file: {ch['pdf_file']}")
