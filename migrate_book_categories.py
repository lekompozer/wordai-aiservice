"""
Migrate Book Categories - Fix nhasachmienphi books to new category structure

Updates all books from nhasachmienphi.com to use:
- Correct child category names (33 categories)
- Parent category IDs (11 categories)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.database.db_manager import DBManager
from src.constants.book_categories import (
    map_nhasachmienphi_category,
    get_parent_category,
)


def migrate_categories():
    """Migrate all nhasachmienphi books to new category structure"""
    print("\n" + "=" * 80)
    print("🔄 Migrating Book Categories")
    print("=" * 80 + "\n")

    db_manager = DBManager()
    db = db_manager.db

    # Find all books from nhasachmienphi
    query = {"metadata.source": "nhasachmienphi.com", "deleted_at": None}

    total_books = db.online_books.count_documents(query)
    print(f"📚 Found {total_books} books from nhasachmienphi.com\n")

    if total_books == 0:
        print("⚠️  No books found to migrate")
        return

    # Get all books
    books = list(db.online_books.find(query))

    stats = {
        "updated": 0,
        "skipped": 0,
        "errors": 0,
        "category_updates": {},
    }

    for idx, book in enumerate(books, 1):
        try:
            book_id = book["book_id"]
            title = book["title"]
            community_config = book.get("community_config", {})
            old_category = community_config.get("category")

            print(f"[{idx}/{total_books}] {title}")
            print(f"  Old category: {old_category}")

            # Skip if already has parent_category (already migrated)
            if community_config.get("parent_category"):
                print(f"  ✅ Already migrated - skipped")
                stats["skipped"] += 1
                print()
                continue

            # Try to determine correct category
            new_child_category = None
            new_parent_category = None

            # Case 1: Has source_category in metadata (from recent crawls)
            source_category = book.get("metadata", {}).get("source_category")
            if source_category:
                # If it's already a proper child name, use it
                new_child_category = source_category
                new_parent_category = get_parent_category(source_category)
            # Case 2: Has old category value
            elif old_category:
                # Try to map it
                if old_category in [
                    "Kinh tế - Quản lý",
                    "Kinh Tế - Quản Lý",
                ]:
                    new_child_category = "Kinh Tế - Quản Lý"
                    new_parent_category = "business"
                elif old_category == "Văn học Việt Nam":
                    new_child_category = "Văn Học Việt Nam"
                    new_parent_category = "literature-art"
                elif old_category == "Tâm Lý - Kỹ Năng Sống":
                    new_child_category = "Tâm Lý - Kỹ Năng Sống"
                    new_parent_category = "business"
                elif old_category == "Marketing - Bán hàng":
                    new_child_category = "Marketing - Bán hàng"
                    new_parent_category = "business"
                elif old_category == "Công Nghệ Thông Tin":
                    new_child_category = "Công Nghệ Thông Tin"
                    new_parent_category = "technology"
                elif old_category == "Y Học - Sức Khỏe":
                    new_child_category = "Y Học - Sức Khỏe"
                    new_parent_category = "health"
                elif old_category == "Học Ngoại Ngữ":
                    new_child_category = "Học Ngoại Ngữ"
                    new_parent_category = "education"
                elif old_category == "Khoa Học - Kỹ Thuật":
                    new_child_category = "Khoa Học - Kỹ Thuật"
                    new_parent_category = "education"
                elif old_category == "Lịch Sử - Chính Trị":
                    new_child_category = "Lịch Sử - Chính Trị"
                    new_parent_category = "other"
                elif old_category == "Văn Hóa - Tôn Giáo":
                    new_child_category = "Văn Hóa - Tôn Giáo"
                    new_parent_category = "literature-art"
                elif old_category == "Thể Thao - Nghệ Thuật":
                    new_child_category = "Thể Thao - Nghệ Thuật"
                    new_parent_category = "lifestyle"
                elif old_category == "Ẩm thực - Nấu ăn":
                    new_child_category = "Ẩm thực - Nấu ăn"
                    new_parent_category = "lifestyle"
                # Old slug formats
                elif old_category == "kinh-te-quan-ly":
                    new_child_category = "Kinh Tế - Quản Lý"
                    new_parent_category = "business"
                elif old_category == "business":
                    new_child_category = "Kinh Tế - Quản Lý"
                    new_parent_category = "business"
                elif old_category == "technology":
                    new_child_category = "Công Nghệ Thông Tin"
                    new_parent_category = "technology"
                elif old_category == "education":
                    new_child_category = "Học Ngoại Ngữ"
                    new_parent_category = "education"
                elif old_category == "literature-art":
                    new_child_category = "Văn Học Việt Nam"
                    new_parent_category = "literature-art"
                elif old_category == "entertainment":
                    new_child_category = "Phiêu Lưu - Mạo Hiểm"
                    new_parent_category = "entertainment"
                else:
                    # Default to Khác
                    new_child_category = "Lịch Sử - Chính Trị"
                    new_parent_category = "other"
            else:
                # No category info - default
                new_child_category = "Lịch Sử - Chính Trị"
                new_parent_category = "other"

            # Update database
            update_result = db.online_books.update_one(
                {"book_id": book_id},
                {
                    "$set": {
                        "community_config.category": new_child_category,
                        "community_config.parent_category": new_parent_category,
                    }
                },
            )

            if update_result.modified_count > 0:
                print(f"  ✅ Updated: {new_child_category} ({new_parent_category})")
                stats["updated"] += 1

                # Track category changes
                key = f"{old_category} → {new_child_category}"
                stats["category_updates"][key] = (
                    stats["category_updates"].get(key, 0) + 1
                )
            else:
                print(f"  ⚠️  No changes made")
                stats["skipped"] += 1

        except Exception as e:
            print(f"  ❌ Error: {e}")
            stats["errors"] += 1

        print()

    # Print summary
    print("\n" + "=" * 80)
    print("📊 Migration Summary")
    print("=" * 80)
    print(f"Total books: {total_books}")
    print(f"✅ Updated: {stats['updated']}")
    print(f"⏭️  Skipped: {stats['skipped']}")
    print(f"❌ Errors: {stats['errors']}")

    print("\n📋 Category Updates:")
    for change, count in sorted(
        stats["category_updates"].items(), key=lambda x: x[1], reverse=True
    ):
        print(f"  {change}: {count} books")

    print("\n" + "=" * 80)
    print("✅ Migration Complete!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    migrate_categories()
