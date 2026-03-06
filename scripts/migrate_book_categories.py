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
    NHASACHMIENPHI_TO_WORDAI,
    CHILD_CATEGORIES,
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

            # Skip if already has correct parent_category (not "other")
            current_parent = community_config.get("parent_category")
            if current_parent and current_parent != "other":
                print(f"  ✅ Already migrated correctly - skipped")
                stats["skipped"] += 1
                print()
                continue
            elif current_parent == "other":
                print(f"  ⚠️  Has wrong parent_category='other', will fix...")

            # Try to determine correct category
            new_child_category = None
            new_parent_category = None

            # Get source category from metadata
            source_category = book.get("metadata", {}).get("source_category")

            # Strategy:
            # 1. If old_category is a slug (has dashes) → Use map_nhasachmienphi_category
            # 2. If old_category is a child category name → Look up parent
            # 3. If source_category exists → Use map_nhasachmienphi_category
            # 4. Default to "Lịch Sử - Chính Trị" (other)

            if old_category:
                # Check if it's a slug format (e.g., "kinh-te-quan-ly")
                if "-" in old_category and old_category in NHASACHMIENPHI_TO_WORDAI:
                    # Map slug to child category name
                    new_child_category, new_parent_category = (
                        map_nhasachmienphi_category(old_category)
                    )
                else:
                    # It's already a child category name, look up parent
                    found = False
                    for child in CHILD_CATEGORIES:
                        if child["name"] == old_category:
                            new_child_category = old_category
                            new_parent_category = child["parent"]
                            found = True
                            break

                    if not found:
                        # Try case-insensitive match
                        for child in CHILD_CATEGORIES:
                            if child["name"].lower() == old_category.lower():
                                new_child_category = child["name"]
                                new_parent_category = child["parent"]
                                found = True
                                break

                    if not found:
                        # Category not recognized, keep as-is but set parent to other
                        new_child_category = old_category
                        new_parent_category = "other"

            elif source_category:
                # Try to map source_category
                if source_category in NHASACHMIENPHI_TO_WORDAI:
                    new_child_category, new_parent_category = (
                        map_nhasachmienphi_category(source_category)
                    )
                else:
                    # If it's already a proper child name, use it
                    new_child_category = source_category
                    new_parent_category = get_parent_category(source_category)
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
