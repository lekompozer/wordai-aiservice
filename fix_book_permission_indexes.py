import os
import logging
from pymongo import MongoClient
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_indexes")

# Load environment variables
load_dotenv("development.env")


def fix_indexes():
    mongo_uri = os.getenv("MONGODB_URL")
    if not mongo_uri:
        logger.error("MONGODB_URL not found in environment")
        return

    try:
        client = MongoClient(mongo_uri)
        db = client.get_database()
        collection = db["book_permissions"]

        logger.info("Connected to database. Checking indexes...")

        # List existing indexes
        indexes = list(collection.list_indexes())
        logger.info(f"Found {len(indexes)} indexes")
        for idx in indexes:
            logger.info(f" - {idx['name']}: {idx['key']}")

        # Drop the problematic index
        if "guide_user_unique" in [idx["name"] for idx in indexes]:
            logger.info("Dropping incorrect 'guide_user_unique' index...")
            collection.drop_index("guide_user_unique")
            logger.info("Dropped 'guide_user_unique'")

        # Create correct indexes

        # 1. Unique permission per user (only for accepted permissions where user_id is set)
        logger.info("Creating partial unique index for (book_id, user_id)...")
        collection.create_index(
            [("book_id", 1), ("user_id", 1)],
            unique=True,
            name="book_user_unique",
            partialFilterExpression={"user_id": {"$ne": ""}},
        )

        # 2. Unique invitation per email (only for pending invitations)
        logger.info("Creating unique index for (book_id, invited_email)...")
        collection.create_index(
            [("book_id", 1), ("invited_email", 1)],
            unique=True,
            name="book_email_invite_unique",
            partialFilterExpression={"user_id": ""},
        )

        logger.info("✅ Indexes fixed successfully!")

        # Verify
        indexes = list(collection.list_indexes())
        logger.info("Current indexes:")
        for idx in indexes:
            logger.info(f" - {idx['name']}: {idx['key']}")

    except Exception as e:
        logger.error(f"Error fixing indexes: {e}")


if __name__ == "__main__":
    fix_indexes()
