"""
Create StudyHub Indexes - For new collections
Creates indexes for discussions, reviews, and wishlist collections

Run: python create_studyhub_community_indexes.py
"""

from src.database.db_manager import DBManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_discussions_indexes(db):
    """Create indexes for studyhub_discussions collection"""
    collection = db["studyhub_discussions"]

    logger.info("Creating indexes for studyhub_discussions...")
    collection.create_index([("community_subject_id", 1), ("created_at", -1)])
    collection.create_index([("community_subject_id", 1), ("replies_count", -1)])
    collection.create_index([("author_id", 1)])
    collection.create_index([("is_pinned", -1), ("created_at", -1)])
    logger.info("✅ Created 4 indexes for studyhub_discussions")


def create_discussion_comments_indexes(db):
    """Create indexes for studyhub_discussion_comments collection"""
    collection = db["studyhub_discussion_comments"]

    logger.info("Creating indexes for studyhub_discussion_comments...")
    collection.create_index([("discussion_id", 1), ("created_at", 1)])
    collection.create_index([("parent_comment_id", 1)])
    collection.create_index([("author_id", 1)])
    logger.info("✅ Created 3 indexes for studyhub_discussion_comments")


def create_reviews_indexes(db):
    """Create indexes for studyhub_reviews collection"""
    collection = db["studyhub_reviews"]

    logger.info("Creating indexes for studyhub_reviews...")
    collection.create_index([("course_id", 1), ("created_at", -1)])
    collection.create_index([("course_id", 1), ("rating", -1)])
    collection.create_index([("user_id", 1), ("course_id", 1)], unique=True)
    collection.create_index([("helpful_count", -1)])
    logger.info("✅ Created 4 indexes for studyhub_reviews")


def create_wishlist_indexes(db):
    """Create indexes for studyhub_wishlist collection"""
    collection = db["studyhub_wishlist"]

    logger.info("Creating indexes for studyhub_wishlist...")
    collection.create_index([("user_id", 1), ("added_at", -1)])
    collection.create_index([("user_id", 1), ("course_id", 1)], unique=True)
    collection.create_index([("course_id", 1)])
    logger.info("✅ Created 3 indexes for studyhub_wishlist")


def create_all_indexes():
    """Create all indexes for StudyHub community collections"""
    try:
        db_manager = DBManager()
        db = db_manager.db

        logger.info("=" * 60)
        logger.info("Creating indexes for StudyHub community collections...")
        logger.info("=" * 60)

        create_discussions_indexes(db)
        create_discussion_comments_indexes(db)
        create_reviews_indexes(db)
        create_wishlist_indexes(db)

        logger.info("\n" + "=" * 60)
        logger.info("✅ All indexes created successfully!")
        logger.info("=" * 60)
        logger.info("Total collections: 4")
        logger.info("  - studyhub_discussions: 4 indexes")
        logger.info("  - studyhub_discussion_comments: 3 indexes")
        logger.info("  - studyhub_reviews: 4 indexes")
        logger.info("  - studyhub_wishlist: 3 indexes")
        logger.info("Total indexes: 14")

    except Exception as e:
        logger.error(f"❌ Error creating indexes: {e}")
        raise


if __name__ == "__main__":
    create_all_indexes()
