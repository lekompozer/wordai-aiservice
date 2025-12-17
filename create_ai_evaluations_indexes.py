"""
Create indexes for ai_evaluations collection
Run this script after deploying the evaluation history feature
"""

from pymongo import ASCENDING, DESCENDING
from config.config import get_mongodb
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_ai_evaluations_indexes():
    """Create indexes for ai_evaluations collection"""
    try:
        db = get_mongodb()
        collection = db["ai_evaluations"]

        # Index 1: submission_id (for retrieving all evaluations of a submission)
        collection.create_index(
            [("submission_id", ASCENDING)], name="submission_id_idx"
        )
        logger.info("✅ Created index: submission_id")

        # Index 2: user_id + created_at (for user's evaluation history, sorted by date)
        collection.create_index(
            [("user_id", ASCENDING), ("created_at", DESCENDING)],
            name="user_id_created_at_idx",
        )
        logger.info("✅ Created index: user_id + created_at")

        # Index 3: test_id + user_id (for filtering user evaluations by test)
        collection.create_index(
            [("test_id", ASCENDING), ("user_id", ASCENDING)], name="test_id_user_id_idx"
        )
        logger.info("✅ Created index: test_id + user_id")

        logger.info("✅ All ai_evaluations indexes created successfully")

    except Exception as e:
        logger.error(f"❌ Failed to create indexes: {e}")
        raise


if __name__ == "__main__":
    create_ai_evaluations_indexes()
