#!/usr/bin/env python3
"""
Migration Script: Add Background Fields
Add background_config fields to existing books and chapters
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.database.db_manager import DBManager
from datetime import datetime, timezone


def migrate_add_background_fields():
    """Add background_config fields to existing books and chapters"""

    print("🚀 Starting migration: Add background fields...")

    db_manager = DBManager()
    db = db_manager.db

    try:
        # ==================== MIGRATE BOOKS ====================
        print("\n📚 Migrating books collection...")

        # Count books without background_config
        books_to_migrate = db.online_books.count_documents(
            {"background_config": {"$exists": False}}
        )

        if books_to_migrate > 0:
            print(f"   Found {books_to_migrate} books to migrate")

            # Add background_config field (set to null initially)
            result_books = db.online_books.update_many(
                {"background_config": {"$exists": False}},
                {"$set": {"background_config": None}},
            )

            print(
                f"   ✅ Updated {result_books.modified_count} books with background_config field"
            )
        else:
            print("   ✅ All books already have background_config field")

        # ==================== MIGRATE CHAPTERS ====================
        print("\n📄 Migrating chapters collection...")

        # Count chapters without background fields
        chapters_to_migrate = db.book_chapters.count_documents(
            {"use_book_background": {"$exists": False}}
        )

        if chapters_to_migrate > 0:
            print(f"   Found {chapters_to_migrate} chapters to migrate")

            # Add background fields to chapters
            result_chapters = db.book_chapters.update_many(
                {"use_book_background": {"$exists": False}},
                {
                    "$set": {
                        "use_book_background": True,  # Default: inherit from book
                        "background_config": None,
                    }
                },
            )

            print(
                f"   ✅ Updated {result_chapters.modified_count} chapters with background fields"
            )
        else:
            print("   ✅ All chapters already have background fields")

        # ==================== VERIFICATION ====================
        print("\n🔍 Verification...")

        total_books = db.online_books.count_documents({})
        books_with_bg = db.online_books.count_documents(
            {"background_config": {"$exists": True}}
        )

        total_chapters = db.book_chapters.count_documents({})
        chapters_with_bg = db.book_chapters.count_documents(
            {"use_book_background": {"$exists": True}}
        )

        print(f"\n📊 Results:")
        print(f"   Books: {books_with_bg}/{total_books} have background_config")
        print(
            f"   Chapters: {chapters_with_bg}/{total_chapters} have background fields"
        )

        if books_with_bg == total_books and chapters_with_bg == total_chapters:
            print("\n✅ Migration completed successfully!")
            return True
        else:
            print("\n⚠️  Warning: Some documents may not have been migrated")
            return False

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("MIGRATION: Add Background Fields to Books & Chapters")
    print("=" * 60)

    success = migrate_add_background_fields()

    if success:
        print("\n" + "=" * 60)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ MIGRATION FAILED")
        print("=" * 60)
        sys.exit(1)
