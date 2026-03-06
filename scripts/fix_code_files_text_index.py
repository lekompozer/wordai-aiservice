#!/usr/bin/env python3
"""
Fix code_files text index to prevent 'language override unsupported: python' error

The issue: MongoDB text indexes have a special 'language' field that determines the
text analyzer. When a document has a 'language' field (like 'python', 'javascript'),
MongoDB tries to use it as a text search language, which fails because these are
programming languages, not human languages.

Solution: Drop the old text index and recreate it with explicit language configuration.
"""

from src.database.db_manager import DBManager


def fix_code_files_text_index():
    """Drop and recreate text index with proper language settings"""
    db_manager = DBManager()
    db = db_manager.db

    print("🔧 Fixing code_files text index...")

    # Drop existing text index
    try:
        db.code_files.drop_index("name_text_description_text")
        print("  ✅ Dropped old text index")
    except Exception as e:
        print(f"  ⚠️ No existing text index to drop: {e}")

    # Create new text index with explicit configuration
    # - default_language: "english" (for text analysis)
    # - language_override: "text_language" (custom field name to avoid conflict with 'language' field)
    db.code_files.create_index(
        [("name", "text"), ("description", "text")],
        default_language="english",
        language_override="text_language",  # Use custom field name instead of 'language'
        name="name_text_description_text",
    )
    print("  ✅ Created new text index with language_override='text_language'")

    print("\n✅ Text index fixed!")
    print("\nℹ️ Documents can now have a 'language' field (python, javascript, etc.)")
    print("   without interfering with MongoDB's text search feature.")


if __name__ == "__main__":
    fix_code_files_text_index()
