"""
Debug duplicate check
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.database.db_manager import DBManager
import re


def check_book(title, slug):
    """Check if book exists"""
    db_manager = DBManager()
    db = db_manager.db

    # Check by title
    title_query = {"title": {"$regex": f"^{re.escape(title)}$", "$options": "i"}}
    title_exists = db.online_books.find_one(title_query)

    # Check by slug
    slug_exists = db.online_books.find_one({"slug": slug})

    print(f"\n{'='*80}")
    print(f"Title: {title}")
    print(f"Slug: {slug}")
    print(f"{'='*80}")
    print(f"Title check: {title_exists is not None}")
    print(f"Slug check: {slug_exists is not None}")

    if title_exists:
        print(f"\n✅ Found by TITLE:")
        print(f"   DB Title: {title_exists.get('title')}")
        print(f"   DB Slug: {title_exists.get('slug')}")
        print(f"   Book ID: {title_exists.get('book_id')}")

    if slug_exists:
        print(f"\n✅ Found by SLUG:")
        print(f"   DB Title: {slug_exists.get('title')}")
        print(f"   DB Slug: {slug_exists.get('slug')}")
        print(f"   Book ID: {slug_exists.get('book_id')}")

    if not title_exists and not slug_exists:
        print(f"\n❌ Book NOT found in database")

    print(f"{'='*80}\n")

    return title_exists is not None or slug_exists is not None


if __name__ == "__main__":
    # Test with books that reported as "already exists"
    test_books = [
        ("Những Mô Hình Quản Trị Kinh Điển", "nhung-mo-hinh-quan-tri-kinh-dien"),
        ("Không Có Bữa Ăn Nào Miễn Phí", "khong-co-bua-an-nao-mien-phi"),
        (
            "Trở Thành Thiên Tài Chơi Chứng Khoán",
            "tro-thanh-thien-tai-choi-chung-khoan",
        ),
        (
            "Nghĩ Giàu, Làm Giàu – Những Trải Nghiệm Ở Việt Nam",
            "nghi-giau-lam-giau-nhung-trai-nghiem-o-viet-nam",
        ),
    ]

    for title, slug in test_books:
        check_book(title, slug)
