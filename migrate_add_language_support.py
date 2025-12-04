"""
Migration Script: Add Multi-Language Support to Books and Chapters
Adds language fields to enable translation features

Run: python migrate_add_language_support.py
"""

import logging
from datetime import datetime
from src.database.db_manager import DBManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 17 Supported Languages
SUPPORTED_LANGUAGES = [
    {"code": "en", "name": "English", "flag": "🇬🇧"},
    {"code": "vi", "name": "Tiếng Việt", "flag": "🇻🇳"},
    {"code": "zh-CN", "name": "Chinese (Simplified)", "flag": "🇨🇳"},
    {"code": "zh-TW", "name": "Chinese (Traditional)", "flag": "🇹🇼"},
    {"code": "ja", "name": "Japanese", "flag": "🇯🇵"},
    {"code": "ko", "name": "Korean", "flag": "🇰🇷"},
    {"code": "th", "name": "Thai", "flag": "🇹🇭"},
    {"code": "id", "name": "Indonesian", "flag": "🇮🇩"},
    {"code": "km", "name": "Khmer", "flag": "🇰🇭"},
    {"code": "lo", "name": "Lao", "flag": "🇱🇦"},
    {"code": "hi", "name": "Hindi", "flag": "🇮🇳"},
    {"code": "ms", "name": "Malay", "flag": "🇲🇾"},
    {"code": "pt", "name": "Portuguese", "flag": "🇵🇹"},
    {"code": "ru", "name": "Russian", "flag": "🇷🇺"},
    {"code": "fr", "name": "French", "flag": "🇫🇷"},
    {"code": "de", "name": "German", "flag": "🇩🇪"},
    {"code": "es", "name": "Spanish", "flag": "🇪🇸"},
]


def migrate_books_collection():
    """Add language support fields to online_books collection"""
    db_manager = DBManager()
    db = db_manager.db
    collection = db["online_books"]

    logger.info("🔄 Starting migration for online_books collection...")

    # Check existing books without language fields
    books_to_update = collection.count_documents(
        {"default_language": {"$exists": False}}
    )

    if books_to_update == 0:
        logger.info("✅ All books already have language fields")
        return

    logger.info(f"📊 Found {books_to_update} books to update")

    # Update all books without language fields
    result = collection.update_many(
        {"default_language": {"$exists": False}},
        {
            "$set": {
                "default_language": "vi",  # Vietnamese as default for existing books
                "current_language": "vi",
                "available_languages": ["vi"],
                "translations": {},
                "background_translations": {},
                "updated_at": datetime.utcnow(),
            }
        },
    )

    logger.info(
        f"✅ Updated {result.modified_count} books with language support fields"
    )


def migrate_chapters_collection():
    """Add language support fields to book_chapters collection"""
    db_manager = DBManager()
    db = db_manager.db
    collection = db["book_chapters"]

    logger.info("🔄 Starting migration for book_chapters collection...")

    # Check existing chapters without language fields
    chapters_to_update = collection.count_documents(
        {"default_language": {"$exists": False}}
    )

    if chapters_to_update == 0:
        logger.info("✅ All chapters already have language fields")
        return

    logger.info(f"📊 Found {chapters_to_update} chapters to update")

    # Update all chapters without language fields
    result = collection.update_many(
        {"default_language": {"$exists": False}},
        {
            "$set": {
                "default_language": "vi",  # Vietnamese as default
                "available_languages": ["vi"],
                "translations": {},
                "background_translations": {},
                "updated_at": datetime.utcnow(),
            }
        },
    )

    logger.info(
        f"✅ Updated {result.modified_count} chapters with language support fields"
    )


def create_indexes():
    """Create indexes for language queries"""
    db_manager = DBManager()
    db = db_manager.db

    logger.info("🔄 Creating indexes for language support...")

    # Books collection indexes
    books_collection = db["online_books"]
    existing_book_indexes = [idx["name"] for idx in books_collection.list_indexes()]

    if "available_languages_idx" not in existing_book_indexes:
        books_collection.create_index(
            [("available_languages", 1)], name="available_languages_idx"
        )
        logger.info("✅ Created index: available_languages_idx on online_books")
    else:
        logger.info("✓ Index available_languages_idx already exists on online_books")

    if "default_language_idx" not in existing_book_indexes:
        books_collection.create_index(
            [("default_language", 1)], name="default_language_idx"
        )
        logger.info("✅ Created index: default_language_idx on online_books")
    else:
        logger.info("✓ Index default_language_idx already exists on online_books")

    # Chapters collection indexes
    chapters_collection = db["book_chapters"]
    existing_chapter_indexes = [
        idx["name"] for idx in chapters_collection.list_indexes()
    ]

    if "chapter_available_languages_idx" not in existing_chapter_indexes:
        chapters_collection.create_index(
            [("available_languages", 1)], name="chapter_available_languages_idx"
        )
        logger.info(
            "✅ Created index: chapter_available_languages_idx on book_chapters"
        )
    else:
        logger.info(
            "✓ Index chapter_available_languages_idx already exists on book_chapters"
        )

    if "chapter_default_language_idx" not in existing_chapter_indexes:
        chapters_collection.create_index(
            [("default_language", 1)], name="chapter_default_language_idx"
        )
        logger.info("✅ Created index: chapter_default_language_idx on book_chapters")
    else:
        logger.info(
            "✓ Index chapter_default_language_idx already exists on book_chapters"
        )


def verify_migration():
    """Verify migration was successful"""
    db_manager = DBManager()
    db = db_manager.db

    logger.info("🔍 Verifying migration...")

    # Check books
    books_with_language = db["online_books"].count_documents(
        {"default_language": {"$exists": True}}
    )
    total_books = db["online_books"].count_documents({})
    logger.info(f"📊 Books with language support: {books_with_language}/{total_books}")

    # Check chapters
    chapters_with_language = db["book_chapters"].count_documents(
        {"default_language": {"$exists": True}}
    )
    total_chapters = db["book_chapters"].count_documents({})
    logger.info(
        f"📊 Chapters with language support: {chapters_with_language}/{total_chapters}"
    )

    # Sample a book to show structure
    sample_book = db["online_books"].find_one(
        {"default_language": {"$exists": True}},
        {
            "book_id": 1,
            "title": 1,
            "default_language": 1,
            "available_languages": 1,
            "translations": 1,
        },
    )
    if sample_book:
        logger.info(f"\n📖 Sample book structure:")
        logger.info(f"   Book ID: {sample_book.get('book_id')}")
        logger.info(f"   Title: {sample_book.get('title')}")
        logger.info(f"   Default Language: {sample_book.get('default_language')}")
        logger.info(f"   Available Languages: {sample_book.get('available_languages')}")
        logger.info(f"   Translations: {sample_book.get('translations')}")

    if books_with_language == total_books and chapters_with_language == total_chapters:
        logger.info("✅ Migration completed successfully!")
    else:
        logger.warning("⚠️ Some documents may not have been migrated")


def rollback_migration():
    """Rollback migration (remove language fields)"""
    db_manager = DBManager()
    db = db_manager.db

    logger.warning("⚠️ Rolling back migration...")
    response = input("Are you sure you want to rollback? (yes/no): ")

    if response.lower() != "yes":
        logger.info("❌ Rollback cancelled")
        return

    # Remove language fields from books
    result_books = db["online_books"].update_many(
        {},
        {
            "$unset": {
                "default_language": "",
                "current_language": "",
                "available_languages": "",
                "translations": "",
                "background_translations": "",
            }
        },
    )
    logger.info(f"✅ Removed language fields from {result_books.modified_count} books")

    # Remove language fields from chapters
    result_chapters = db["book_chapters"].update_many(
        {},
        {
            "$unset": {
                "default_language": "",
                "available_languages": "",
                "translations": "",
                "background_translations": "",
            }
        },
    )
    logger.info(
        f"✅ Removed language fields from {result_chapters.modified_count} chapters"
    )

    # Drop indexes
    db["online_books"].drop_index("available_languages_idx")
    db["online_books"].drop_index("default_language_idx")
    db["book_chapters"].drop_index("chapter_available_languages_idx")
    db["book_chapters"].drop_index("chapter_default_language_idx")
    logger.info("✅ Dropped language indexes")

    logger.info("✅ Rollback completed")


def main():
    """Run migration"""
    logger.info("=" * 60)
    logger.info("📚 Book Translation Feature - Database Migration")
    logger.info("=" * 60)
    logger.info(f"Supported Languages: {len(SUPPORTED_LANGUAGES)}")
    for lang in SUPPORTED_LANGUAGES:
        logger.info(f"  {lang['flag']} {lang['code']}: {lang['name']}")
    logger.info("=" * 60)

    try:
        # Step 1: Migrate books
        migrate_books_collection()

        # Step 2: Migrate chapters
        migrate_chapters_collection()

        # Step 3: Create indexes
        create_indexes()

        # Step 4: Verify
        verify_migration()

        logger.info("\n" + "=" * 60)
        logger.info("✅ Migration completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        logger.error("You may need to rollback the migration")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        rollback_migration()
    else:
        main()
