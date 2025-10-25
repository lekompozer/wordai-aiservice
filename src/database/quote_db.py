"""
MongoDB connection and operations for quote generation
"""

import os
import motor.motor_asyncio
from typing import Optional
from src.utils.logger import setup_logger

logger = setup_logger()


class QuoteDatabase:
    """MongoDB database manager for quote generation"""

    def __init__(self):
        self.client = None
        self.db = None

    async def initialize(self) -> None:
        """Initialize database connection"""
        try:
            # Check environment
            environment = os.getenv("ENVIRONMENT", "development")

            # Use authenticated URI if available, fallback to basic URI
            mongo_uri = os.getenv("MONGODB_URI_AUTH")
            if not mongo_uri:
                # Build authenticated URI from components
                mongo_user = os.getenv("MONGODB_APP_USERNAME")
                mongo_pass = os.getenv("MONGODB_APP_PASSWORD")
                db_name = os.getenv("MONGODB_NAME", "ai_service_db")

                # FIXED: Use Docker network container name in production
                if environment == "production":
                    mongo_host = "mongodb:27017"  # Docker network container name
                    logger.info(f"🐳 [PROD] Using Docker network MongoDB")
                else:
                    mongo_host = "localhost:27017"
                    logger.info(f"🏠 [DEV] Using local MongoDB")

                if mongo_user and mongo_pass:
                    mongo_uri = f"mongodb://{mongo_user}:{mongo_pass}@{mongo_host}/{db_name}?authSource=admin"
                else:
                    mongo_uri = f"mongodb://{mongo_host}/"

            db_name = os.getenv("MONGODB_NAME", "ai_service_db")

            self.client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
            self.db = self.client[db_name]

            # Test connection
            await self.client.admin.command("ping")
            logger.info("✅ Quote Database connection successful")

            # Create indexes for better performance
            await self._create_indexes()

        except Exception as e:
            logger.error(f"❌ Database connection failed: {str(e)}")
            raise e

    async def _create_indexes(self):
        """Create database indexes for quote collections"""
        try:
            # Quote settings indexes
            await self.db.quote_settings.create_index("firebase_uid")
            await self.db.quote_settings.create_index("user_id")
            await self.db.quote_settings.create_index("created_at")
            await self.db.quote_settings.create_index(
                [("firebase_uid", 1), ("is_active", 1)]
            )

            # Quote records indexes
            await self.db.quote_records.create_index("firebase_uid")
            await self.db.quote_records.create_index("user_id")
            await self.db.quote_records.create_index("settings_id")
            await self.db.quote_records.create_index("created_at")
            await self.db.quote_records.create_index(
                [("firebase_uid", 1), ("status", 1)]
            )

            # Document templates indexes
            await self.db.user_upload_files.create_index("type")
            await self.db.user_upload_files.create_index("is_active")
            await self.db.user_upload_files.create_index(
                [("type", 1), ("is_active", 1)]
            )

            logger.info("✅ Database indexes created successfully")

        except Exception as e:
            logger.warning(f"⚠️ Could not create indexes: {str(e)}")

    async def close(self):
        """Close database connection"""
        if self.client:
            self.client.close()
            logger.info("Database connection closed")


# Global database instance
quote_db = QuoteDatabase()


async def get_database():
    """Get database instance"""
    if not quote_db.db:
        await quote_db.initialize()
    return quote_db.db


async def close_database():
    """Close database connection"""
    await quote_db.close()
