"""
MongoDB Migration Script: Add Soft Delete Fields to Books

Adds is_deleted, deleted_at, deleted_by fields to all existing books
in online_books collection.

Usage:
    python migrate_add_soft_delete_fields.py
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_add_soft_delete_fields():
    """Add soft delete fields to all existing books"""

    # Get MongoDB connection from environment
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    db_name = os.getenv("MONGODB_DB_NAME", "wordai_chatbot")

    logger.info(f"Connecting to MongoDB: {mongo_uri}")
    logger.info(f"Database: {db_name}")

    client = MongoClient(mongo_uri)
    db = client[db_name]
    books_collection = db["online_books"]

    # Check how many books need migration
    total_books = books_collection.count_documents({})
    needs_migration = books_collection.count_documents(
        {"is_deleted": {"$exists": False}}
    )

    logger.info(f"📊 Total books: {total_books}")
    logger.info(f"📊 Books needing migration: {needs_migration}")

    if needs_migration == 0:
        logger.info(
            "✅ No books need migration. All books already have soft delete fields."
        )
        return

    # Add soft delete fields to books without them
    logger.info(f"🔄 Adding soft delete fields to {needs_migration} books...")

    result = books_collection.update_many(
        {"is_deleted": {"$exists": False}},
        {
            "$set": {
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": None,
            }
        },
    )

    logger.info(f"✅ Successfully updated {result.modified_count} books")

    # Verify migration
    remaining = books_collection.count_documents({"is_deleted": {"$exists": False}})

    if remaining == 0:
        logger.info("✅ Migration completed successfully!")
    else:
        logger.warning(f"⚠️ Warning: {remaining} books still need migration")

    # Show sample data
    sample = books_collection.find_one(
        {},
        {
            "_id": 0,
            "book_id": 1,
            "title": 1,
            "is_deleted": 1,
            "deleted_at": 1,
            "deleted_by": 1,
        },
    )

    if sample:
        logger.info(f"📄 Sample book after migration:")
        logger.info(f"   - book_id: {sample.get('book_id')}")
        logger.info(f"   - title: {sample.get('title')}")
        logger.info(f"   - is_deleted: {sample.get('is_deleted')}")
        logger.info(f"   - deleted_at: {sample.get('deleted_at')}")
        logger.info(f"   - deleted_by: {sample.get('deleted_by')}")

    client.close()
    logger.info("🔌 MongoDB connection closed")


if __name__ == "__main__":
    try:
        migrate_add_soft_delete_fields()
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        sys.exit(1)
