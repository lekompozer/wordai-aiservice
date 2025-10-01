"""
Script to fix MongoDB index conflicts
Drop old indexes and recreate with correct configuration
"""

from src.database.db_manager import DBManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fix_indexes():
    """Fix MongoDB index conflicts"""
    try:
        db_manager = DBManager()

        if not db_manager.client:
            logger.error("MongoDB not connected")
            return

        db = db_manager.db

        # Fix users collection
        logger.info("Fixing 'users' collection indexes...")
        users = db["users"]

        # List existing indexes
        logger.info("Current indexes:")
        for idx in users.list_indexes():
            logger.info(f"  - {idx['name']}: {idx.get('key')}")

        # Drop problematic index
        try:
            users.drop_index("firebase_uid_1")
            logger.info("✅ Dropped old firebase_uid_1 index")
        except Exception as e:
            logger.warning(f"Could not drop firebase_uid_1: {e}")

        # Recreate with correct configuration
        users.create_index(
            "firebase_uid", unique=True, sparse=True, name="firebase_uid_1_sparse"
        )
        logger.info("✅ Created new firebase_uid index with sparse=True")

        users.create_index("email", name="email_1")
        logger.info("✅ Created email index")

        # Fix conversations collection
        logger.info("\nFixing 'conversations' collection indexes...")
        conversations = db["conversations"]

        try:
            conversations.drop_index("conversation_id_1")
            logger.info("✅ Dropped old conversation_id_1 index")
        except Exception as e:
            logger.warning(f"Could not drop conversation_id_1: {e}")

        conversations.create_index(
            "conversation_id", unique=True, sparse=True, name="conversation_id_1_sparse"
        )
        logger.info("✅ Created new conversation_id index with sparse=True")

        conversations.create_index("user_id", name="user_id_1")
        logger.info("✅ Created user_id index")

        conversations.create_index(
            [("user_id", 1), ("updated_at", -1)], name="user_id_1_updated_at_-1"
        )
        logger.info("✅ Created compound index (user_id, updated_at)")

        # Fix user_files collection
        logger.info("\nFixing 'user_files' collection indexes...")
        user_files = db["user_files"]

        try:
            user_files.drop_index("file_id_1")
            logger.info("✅ Dropped old file_id_1 index")
        except Exception as e:
            logger.warning(f"Could not drop file_id_1: {e}")

        user_files.create_index(
            "file_id", unique=True, sparse=True, name="file_id_1_sparse"
        )
        logger.info("✅ Created new file_id index with sparse=True")

        # Check if user_id index already exists before creating
        existing_indexes = [idx["name"] for idx in user_files.list_indexes()]
        if "user_id_1" not in existing_indexes:
            user_files.create_index("user_id", name="user_files_user_id_1")
            logger.info("✅ Created user_id index")
        else:
            logger.info("ℹ️  user_id index already exists")

        if (
            "user_files_user_id_1_uploaded_at_-1" not in existing_indexes
            and "user_id_1_uploaded_at_-1" not in existing_indexes
        ):
            user_files.create_index(
                [("user_id", 1), ("uploaded_at", -1)],
                name="user_files_user_id_1_uploaded_at_-1",
            )
            logger.info("✅ Created compound index (user_id, uploaded_at)")
        else:
            logger.info("ℹ️  Compound index already exists")

        logger.info("\n" + "=" * 60)
        logger.info("✅ All indexes fixed successfully!")
        logger.info("=" * 60)

        # Show final indexes
        logger.info("\nFinal indexes in 'users' collection:")
        for idx in users.list_indexes():
            logger.info(
                f"  - {idx['name']}: {idx.get('key')}, unique={idx.get('unique', False)}, sparse={idx.get('sparse', False)}"
            )

        logger.info("\nFinal indexes in 'conversations' collection:")
        for idx in conversations.list_indexes():
            logger.info(
                f"  - {idx['name']}: {idx.get('key')}, unique={idx.get('unique', False)}, sparse={idx.get('sparse', False)}"
            )

    except Exception as e:
        logger.error(f"❌ Error fixing indexes: {e}")


if __name__ == "__main__":
    fix_indexes()
