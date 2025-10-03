#!/usr/bin/env python3
"""
Initialize Document Editor Database
Tạo collection và indexes cho document management system
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from src.database.db_manager import DBManager
from src.services.document_manager import DocumentManager
from src.utils.logger import setup_logger

logger = setup_logger()


def initialize_document_database():
    """Initialize database for document editor"""
    try:
        logger.info("🚀 Initializing Document Editor Database...")

        # Connect to MongoDB
        db_manager = DBManager()
        logger.info("✅ Connected to MongoDB")

        # Create DocumentManager
        doc_manager = DocumentManager(db_manager.db)

        # Create indexes (synchronous)
        doc_manager.create_indexes()
        logger.info("✅ Document indexes created")

        # Test connection
        stats = doc_manager.get_storage_stats("test_user")
        logger.info(f"✅ Database test successful: {stats}")

        logger.info("🎉 Document Editor Database initialized successfully!")
        logger.info("")
        logger.info("📋 Created collection: documents")
        logger.info("📋 Created indexes:")
        logger.info("   - document_id (unique)")
        logger.info("   - user_id + last_opened_at")
        logger.info("   - file_id")
        logger.info("   - user_id + is_deleted")
        logger.info("")
        logger.info("✅ Ready to use!")

    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    initialize_document_database()
