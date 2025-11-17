"""
MongoDB Migration Script: Add access_config and stats to existing books

Adds access_config (None by default) and stats (0 revenue) to all existing books
that don't have these fields.

Usage:
    python migrate_add_point_system_fields.py
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_add_point_system_fields():
    """Add access_config and stats to all existing books"""
    
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
    needs_access_config = books_collection.count_documents(
        {"access_config": {"$exists": False}}
    )
    needs_stats = books_collection.count_documents(
        {"stats": {"$exists": False}}
    )
    
    logger.info(f"📊 Total books: {total_books}")
    logger.info(f"📊 Books needing access_config: {needs_access_config}")
    logger.info(f"📊 Books needing stats: {needs_stats}")
    
    if needs_access_config == 0 and needs_stats == 0:
        logger.info("✅ No books need migration. All books already have point system fields.")
        return
    
    # Add access_config to books without it
    if needs_access_config > 0:
        logger.info(f"🔄 Adding access_config to {needs_access_config} books...")
        
        result = books_collection.update_many(
            {"access_config": {"$exists": False}},
            {
                "$set": {
                    "access_config": None  # Default: no point-based access
                }
            }
        )
        
        logger.info(f"✅ Successfully added access_config to {result.modified_count} books")
    
    # Add stats to books without it
    if needs_stats > 0:
        logger.info(f"🔄 Adding stats to {needs_stats} books...")
        
        result = books_collection.update_many(
            {"stats": {"$exists": False}},
            {
                "$set": {
                    "stats": {
                        "total_revenue_points": 0,
                        "owner_reward_points": 0,
                        "system_fee_points": 0
                    }
                }
            }
        )
        
        logger.info(f"✅ Successfully added stats to {result.modified_count} books")
    
    # Verify migration
    remaining_access_config = books_collection.count_documents(
        {"access_config": {"$exists": False}}
    )
    remaining_stats = books_collection.count_documents(
        {"stats": {"$exists": False}}
    )
    
    if remaining_access_config == 0 and remaining_stats == 0:
        logger.info("✅ Migration completed successfully!")
    else:
        logger.warning(f"⚠️ Warning: {remaining_access_config} books still need access_config")
        logger.warning(f"⚠️ Warning: {remaining_stats} books still need stats")
    
    # Show sample data
    sample = books_collection.find_one({}, {
        "_id": 0,
        "book_id": 1,
        "title": 1,
        "access_config": 1,
        "stats": 1
    })
    
    if sample:
        logger.info(f"📄 Sample book after migration:")
        logger.info(f"   - book_id: {sample.get('book_id')}")
        logger.info(f"   - title: {sample.get('title')}")
        logger.info(f"   - access_config: {sample.get('access_config')}")
        logger.info(f"   - stats: {sample.get('stats')}")
    
    client.close()
    logger.info("🔌 MongoDB connection closed")


if __name__ == "__main__":
    try:
        migrate_add_point_system_fields()
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        sys.exit(1)
