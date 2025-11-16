#!/usr/bin/env python3
"""
Comprehensive script to rename all 'guide' references to 'book' in the codebase
"""

import os
import re

# Files to update
files_to_update = [
    "src/services/book_manager.py",
    "src/api/book_routes.py",
]

# Replacement mappings (order matters!)
replacements = [
    # Method names
    (r"\bguide_manager\b", "book_manager"),
    (r"\bguides_collection\b", "books_collection"),
    (r"\bcreate_guide\b", "create_book"),
    (r"\bget_guide\b", "get_book"),
    (r"\bget_guide_by_slug\b", "get_book_by_slug"),
    (r"\bget_guide_by_domain\b", "get_book_by_domain"),
    (r"\bupdate_guide\b", "update_book"),
    (r"\bdelete_guide\b", "delete_book"),
    (r"\blist_user_guides\b", "list_user_books"),
    (r"\bcount_user_guides\b", "count_user_books"),
    # Variable names (be careful with these)
    (r"guide = ", "book = "),
    (r"guide\.", "book."),
    (r"guide\[", "book["),
    (r"\(guide\)", "(book)"),
    (r" guide\b", " book"),
    (r"updated_guide", "updated_book"),
    (r"deleted = guide", "deleted = book"),
    # Comments and docstrings
    (r"User Guide Manager", "User Book Manager"),
    (r"guide document", "book document"),
    (r"guide's ", "book's "),
    (r"Create guide", "Create book"),
    (r"Get guide", "Get book"),
    (r"Update guide", "Update book"),
    (r"Delete guide", "Delete book"),
    (r"List guides", "List books"),
    (r"guide indexes", "book indexes"),
    (r"guide mới", "book mới"),
    (r"Quản lý Online Books", "Manage Online Books"),
    (r"guides của user", "books của user"),
    (r"User's guides", "User's books"),
    (r"guide listing", "book listing"),
    (r"Public guide lookup", "Public book lookup"),
    # Log messages
    (r"Created guide:", "Created book:"),
    (r"Found guide:", "Found book:"),
    (r"Updated guide:", "Updated book:"),
    (r"Deleted guide:", "Deleted book:"),
    (r"Found .* guides", "Found {count} books"),
    (r"listed guides:", "listed books:"),
    (r"Failed to create guide", "Failed to create book"),
    (r"Failed to get guide", "Failed to get book"),
    (r"Failed to update guide", "Failed to update book"),
    (r"Failed to delete guide", "Failed to delete book"),
    (r"Failed to list guides", "Failed to list books"),
    (r"Guide not found", "Book not found"),
]


def update_file(filepath):
    """Update a single file with all replacements"""
    print(f"\n📝 Processing: {filepath}")

    if not os.path.exists(filepath):
        print(f"   ⚠️  File not found: {filepath}")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original_content = content
    changes_made = 0

    for pattern, replacement in replacements:
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
            changes_made += 1

    if content != original_content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"   ✅ Updated with {changes_made} pattern changes")
    else:
        print(f"   ℹ️  No changes needed")


def main():
    print("=" * 60)
    print("🔄 COMPREHENSIVE GUIDE → BOOK RENAME")
    print("=" * 60)

    for filepath in files_to_update:
        update_file(filepath)

    print("\n" + "=" * 60)
    print("✅ RENAME COMPLETE!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Review the changes with: git diff")
    print("2. Test the application")
    print(
        "3. Commit: git add -A && git commit -m 'refactor: Rename guide to book throughout codebase'"
    )


if __name__ == "__main__":
    main()
