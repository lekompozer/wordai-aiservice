"""
Create indexes for saved_books collection
Run this to set up database indexes after deploying the new endpoints
"""

from src.database.db_manager import DBManager
import logging

logger = logging.getLogger(__name__)

# Initialize DB
db_manager = DBManager()
db = db_manager.db


def create_saved_books_indexes():
    """Create indexes for saved_books collection"""

    try:
        # Index for user's saved books list
        db.saved_books.create_index(
            [("user_id", 1), ("saved_at", -1)],
            name="idx_user_saved_at",
        )

        # Index for checking if book is saved
        db.saved_books.create_index(
            [("user_id", 1), ("book_id", 1), ("deleted_at", 1)],
            name="idx_user_book_deleted",
            unique=True,
        )

        # Index for book's total saves count
        db.saved_books.create_index(
            [("book_id", 1), ("deleted_at", 1)],
            name="idx_book_deleted",
        )

        logger.info("✅ Created saved_books indexes")

        # List all indexes
        indexes = list(db.saved_books.list_indexes())
        logger.info(f"📊 saved_books indexes: {[idx['name'] for idx in indexes]}")

        return True

    except Exception as e:
        logger.error(f"❌ Failed to create saved_books indexes: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_saved_books_indexes()
