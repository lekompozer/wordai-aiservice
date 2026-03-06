"""
Create database indexes for Song Subscription system
Run this once to set up indexes
"""

from src.database.db_manager import DBManager
from src.utils.logger import setup_logger

logger = setup_logger()


def create_song_subscription_indexes():
    """Create MongoDB indexes for song subscription collections"""

    db_manager = DBManager()
    db = db_manager.db

    logger.info("🔧 Creating Song Subscription indexes...")

    # user_song_subscription collection
    subscription_col = db["user_song_subscription"]

    # Index: user_id (for quick user lookup)
    subscription_col.create_index("user_id")
    logger.info("✅ Created index: user_song_subscription.user_id")

    # Index: status + end_date (for finding active subscriptions)
    subscription_col.create_index([("status", 1), ("end_date", 1)])
    logger.info("✅ Created index: user_song_subscription.status + end_date")

    # Index: order_invoice_number (unique, for payment tracking)
    subscription_col.create_index("order_invoice_number", unique=True, sparse=True)
    logger.info(
        "✅ Created index: user_song_subscription.order_invoice_number (unique)"
    )

    logger.info("✅ All Song Subscription indexes created successfully")


if __name__ == "__main__":
    create_song_subscription_indexes()
    print("✅ Done! Song Subscription indexes are ready.")
