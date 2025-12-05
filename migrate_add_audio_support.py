"""
Migration Script: Add Audio Support to Book Chapters
Creates indexes for audio_config and audio_translations fields
Run this once to prepare database for audio feature
"""

import logging
from pymongo import MongoClient
from pymongo.errors import OperationFailure
import os
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
# Use development.env for local testing
load_dotenv("development.env")


def get_mongodb_connection():
    """Get MongoDB connection from environment"""
    mongo_uri = os.getenv("MONGODB_URI_AUTH") or os.getenv(
        "MONGODB_URI", "mongodb://localhost:27017/"
    )
    db_name = os.getenv("MONGODB_NAME", "ai_service_db")

    logger.info(f"Connecting to MongoDB: {db_name}")
    client = MongoClient(mongo_uri)
    db = client[db_name]

    return client, db


def create_audio_indexes(db):
    """Create indexes for audio support"""

    logger.info("=" * 60)
    logger.info("CREATING AUDIO INDEXES")
    logger.info("=" * 60)

    # 1. book_chapters collection indexes
    logger.info("\n📚 book_chapters collection:")

    try:
        # Index for audio_config.enabled (find chapters with audio)
        result = db.book_chapters.create_index(
            [("audio_config.enabled", 1)], name="audio_config_enabled_1", sparse=True
        )
        logger.info(f"  ✅ Created index: {result}")
    except OperationFailure as e:
        if "already exists" in str(e):
            logger.info(f"  ⚠️  Index already exists: audio_config_enabled_1")
        else:
            logger.error(f"  ❌ Error creating index: {e}")

    try:
        # Index for audio_config.audio_file_id (link to library)
        result = db.book_chapters.create_index(
            [("audio_config.audio_file_id", 1)],
            name="audio_config_file_id_1",
            sparse=True,
        )
        logger.info(f"  ✅ Created index: {result}")
    except OperationFailure as e:
        if "already exists" in str(e):
            logger.info(f"  ⚠️  Index already exists: audio_config_file_id_1")
        else:
            logger.error(f"  ❌ Error creating index: {e}")

    try:
        # Index for audio_translations lookup
        result = db.book_chapters.create_index(
            [("audio_translations", 1)], name="audio_translations_1", sparse=True
        )
        logger.info(f"  ✅ Created index: {result}")
    except OperationFailure as e:
        if "already exists" in str(e):
            logger.info(f"  ⚠️  Index already exists: audio_translations_1")
        else:
            logger.error(f"  ❌ Error creating index: {e}")

    # 2. library_files collection indexes
    logger.info("\n📁 library_files collection:")

    try:
        # Index for audio file type
        result = db.library_files.create_index(
            [("user_id", 1), ("file_type", 1), ("category", 1)],
            name="user_file_type_category_1",
        )
        logger.info(f"  ✅ Created index: {result}")
    except OperationFailure as e:
        if "already exists" in str(e):
            logger.info(f"  ⚠️  Index already exists: user_file_type_category_1")
        else:
            logger.error(f"  ❌ Error creating index: {e}")

    try:
        # Index for linked_to queries (user's audio for specific chapter)
        result = db.library_files.create_index(
            [
                ("user_id", 1),
                ("metadata.linked_to.type", 1),
                ("metadata.linked_to.chapter_id", 1),
                ("is_deleted", 1),
            ],
            name="user_linked_chapter_1",
        )
        logger.info(f"  ✅ Created index: {result}")
    except OperationFailure as e:
        if "already exists" in str(e):
            logger.info(f"  ⚠️  Index already exists: user_linked_chapter_1")
        else:
            logger.error(f"  ❌ Error creating index: {e}")

    try:
        # Index for audio file queries by book
        result = db.library_files.create_index(
            [("user_id", 1), ("metadata.linked_to.book_id", 1), ("category", 1)],
            name="user_book_audio_1",
            sparse=True,
        )
        logger.info(f"  ✅ Created index: {result}")
    except OperationFailure as e:
        if "already exists" in str(e):
            logger.info(f"  ⚠️  Index already exists: user_book_audio_1")
        else:
            logger.error(f"  ❌ Error creating index: {e}")


def verify_indexes(db):
    """Verify created indexes"""

    logger.info("\n" + "=" * 60)
    logger.info("VERIFYING INDEXES")
    logger.info("=" * 60)

    # Check book_chapters indexes
    logger.info("\n📚 book_chapters indexes:")
    indexes = list(db.book_chapters.list_indexes())
    audio_indexes = [idx for idx in indexes if "audio" in idx.get("name", "").lower()]
    for idx in audio_indexes:
        logger.info(f"  ✅ {idx['name']}: {idx['key']}")

    # Check library_files indexes
    logger.info("\n📁 library_files indexes:")
    indexes = list(db.library_files.list_indexes())
    relevant_indexes = [
        idx
        for idx in indexes
        if any(
            term in idx.get("name", "").lower()
            for term in ["audio", "linked", "category"]
        )
    ]
    for idx in relevant_indexes:
        logger.info(f"  ✅ {idx['name']}: {idx['key']}")


def main():
    """Main migration function"""
    try:
        logger.info("🚀 Starting Audio Feature Migration")
        logger.info("=" * 60)

        # Connect to MongoDB
        client, db = get_mongodb_connection()

        # Create indexes
        create_audio_indexes(db)

        # Verify indexes
        verify_indexes(db)

        # Close connection
        client.close()

        logger.info("\n" + "=" * 60)
        logger.info("✅ MIGRATION COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        logger.info("\nDatabase is ready for audio feature!")
        logger.info("Next steps:")
        logger.info("  1. Test audio upload endpoint")
        logger.info("  2. Test audio retrieval endpoint")
        logger.info("  3. Verify audio saved to library")

    except Exception as e:
        logger.error(f"\n❌ MIGRATION FAILED: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
