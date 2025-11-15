"""
Initialize User Guide Database Collections and Indexes
Phase 1: Setup script
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.database.db_manager import DBManager
from src.services.user_guide_manager import UserGuideManager
from src.services.guide_chapter_manager import GuideChapterManager
from src.services.guide_permission_manager import GuidePermissionManager
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("chatbot")


def initialize_user_guide_collections():
    """Initialize all User Guide collections and indexes"""

    logger.info("=" * 60)
    logger.info("🚀 Initializing User Guide System - Phase 1")
    logger.info("=" * 60)

    try:
        # Get database connection
        db_manager = DBManager()
        db = db_manager.db
        logger.info(f"✅ Connected to database: {db.name}")

        # Initialize managers
        guide_manager = UserGuideManager(db)
        chapter_manager = GuideChapterManager(db)
        permission_manager = GuidePermissionManager(db)

        # Create indexes for user_guides collection
        logger.info("\n📘 Creating indexes for user_guides collection...")
        guide_manager.create_indexes()

        # Create indexes for guide_chapters collection
        logger.info("\n📄 Creating indexes for guide_chapters collection...")
        chapter_manager.create_indexes()

        # Create indexes for guide_permissions collection
        logger.info("\n🔐 Creating indexes for guide_permissions collection...")
        permission_manager.create_indexes()

        # Verify collections exist
        logger.info("\n✅ Verifying collections...")
        collections = db.list_collection_names()

        required_collections = ["user_guides", "guide_chapters", "guide_permissions"]
        for collection_name in required_collections:
            if collection_name in collections:
                logger.info(f"   ✅ {collection_name}")
            else:
                logger.warning(f"   ⚠️ {collection_name} (not found)")

        # Count indexes
        logger.info("\n📊 Index Summary:")
        guide_indexes = list(guide_manager.guides_collection.list_indexes())
        chapter_indexes = list(chapter_manager.chapters_collection.list_indexes())
        permission_indexes = list(
            permission_manager.permissions_collection.list_indexes()
        )

        logger.info(f"   user_guides: {len(guide_indexes)} indexes")
        logger.info(f"   guide_chapters: {len(chapter_indexes)} indexes")
        logger.info(f"   guide_permissions: {len(permission_indexes)} indexes")

        logger.info("\n" + "=" * 60)
        logger.info("✅ Phase 1 Initialization Complete!")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"\n❌ Error during initialization: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = initialize_user_guide_collections()
    sys.exit(0 if success else 1)
