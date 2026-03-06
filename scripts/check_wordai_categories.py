#!/usr/bin/env python3
"""
Check WordAI's actual category list from database
"""

from src.database.db_manager import DBManager


def check_categories():
    """Check all categories in book_categories collection"""

    db_manager = DBManager()
    db = db_manager.db

    print("=" * 80)
    print("📂 WordAI Book Categories")
    print("=" * 80)

    # Get all categories
    categories = list(
        db.book_categories.find(
            {"is_active": True},
            {"category_id": 1, "name_vi": 1, "name_en": 1, "parent": 1, "_id": 0},
        ).sort("category_id", 1)
    )

    if not categories:
        print("❌ No categories found!")
        return

    print(f"\nTotal categories: {len(categories)}\n")

    # Group by parent
    parent_groups = {}
    for cat in categories:
        parent = cat.get("parent", "no-parent")
        if parent not in parent_groups:
            parent_groups[parent] = []
        parent_groups[parent].append(cat)

    # Display by parent
    for parent, cats in sorted(parent_groups.items()):
        print(f"\n🏷️  Parent: {parent}")
        print("-" * 80)
        for cat in cats:
            print(
                f"   • {cat['category_id']:30} | {cat['name_vi']:40} | {cat.get('name_en', 'N/A')}"
            )

    print("\n" + "=" * 80)
    print(f"✅ Found {len(categories)} categories")
    print("=" * 80)


if __name__ == "__main__":
    check_categories()
