"""
Migration: Add community subject fields to studyhub_subjects
Adds new fields needed for marketplace publishing

Run: python migrate_add_community_subject_fields.py
"""

from src.database.db_manager import DBManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_community_subject_fields():
    """Add community subject fields to existing subjects"""
    try:
        db_manager = DBManager()
        db = db_manager.db
        collection = db["studyhub_subjects"]

        logger.info("Starting migration: Adding community subject fields...")

        # Update all subjects with new fields
        result = collection.update_many(
            {},  # All documents
            {
                "$set": {
                    "community_subject_id": None,
                    "organization": None,
                    "is_verified_organization": False,
                    "marketplace_published_at": None,
                }
            },
        )

        logger.info(f"✅ Updated {result.modified_count} subjects")

        # Create indexes
        logger.info("Creating indexes...")
        collection.create_index([("community_subject_id", 1)])
        collection.create_index(
            [
                ("community_subject_id", 1),
                ("is_public_marketplace", 1),
                ("total_views", -1),
            ]
        )
        collection.create_index([("organization", 1)])
        collection.create_index([("is_verified_organization", -1)])
        logger.info("✅ Created indexes for community subject fields")

        logger.info("\n✅ Migration completed successfully!")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    migrate_community_subject_fields()
