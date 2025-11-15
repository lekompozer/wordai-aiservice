#!/usr/bin/env python3
"""
Update test files for Guide → Book migration
"""

import os
import re

TEST_FILES = [
    "test_book_api.py",
    "test_book_models.py",
    "test_book_permissions_api.py",
    "test_public_book_view_api.py",
]

REPLACEMENTS = [
    # Imports
    ("from src.api.user_guide_routes", "from src.api.book_routes"),
    ("from src.services.user_guide_manager", "from src.services.book_manager"),
    (
        "from src.services.guide_chapter_manager",
        "from src.services.book_chapter_manager",
    ),
    (
        "from src.services.guide_permission_manager",
        "from src.services.book_permission_manager",
    ),
    ("from src.models.user_guide_models", "from src.models.book_models"),
    ("from src.models.guide_chapter_models", "from src.models.book_chapter_models"),
    (
        "from src.models.guide_permission_models",
        "from src.models.book_permission_models",
    ),
    ("from src.models.public_guide_models", "from src.models.public_book_models"),
    # URL paths
    ('"/api/v1/guides', '"/api/v1/books'),
    ("'/api/v1/guides", "'/api/v1/books"),
    # Collection names
    ('"user_guides"', '"online_books"'),
    ("'user_guides'", "'online_books'"),
    ('"guide_chapters"', '"book_chapters"'),
    ("'guide_chapters'", "'book_chapters'"),
    ('"guide_permissions"', '"book_permissions"'),
    ("'guide_permissions'", "'book_permissions'"),
    # Field names
    ('"guide_id"', '"book_id"'),
    ("'guide_id'", "'book_id'"),
    ("guide_id:", "book_id:"),
    ("guide_id =", "book_id ="),
    ('["guide_id"]', '["book_id"]'),
    ("['guide_id']", "['book_id']"),
    # Variable names in test functions
    ("test_guide_", "test_book_"),
    ("create_guide", "create_book"),
    ("guide_data", "book_data"),
    ("guide1", "book1"),
    ("guide2", "book2"),
    # Comments
    ("User Guide", "Online Book"),
    ("user guide", "book"),
    ("Guide Management", "Book Management"),
]


def update_test_file(filepath):
    """Update a test file"""
    print(f"\n📝 Updating: {filepath}")

    if not os.path.exists(filepath):
        print(f"   ⚠️  File not found, skipping")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original = content
    count = 0

    for old, new in REPLACEMENTS:
        if old in content:
            occurrences = content.count(old)
            content = content.replace(old, new)
            count += occurrences
            if occurrences > 0:
                print(f"   ✅ {old} → {new} ({occurrences}x)")

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"   💾 Saved with {count} replacements")
    else:
        print(f"   ℹ️  No changes needed")


def main():
    print("=" * 80)
    print("🧪 Updating Test Files: Guide → Book")
    print("=" * 80)

    for filepath in TEST_FILES:
        update_test_file(filepath)

    print("\n" + "=" * 80)
    print("✅ Test files updated!")
    print("=" * 80)


if __name__ == "__main__":
    main()
