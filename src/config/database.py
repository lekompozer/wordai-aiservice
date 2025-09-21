"""
Database configuration for document generation service
"""

import os
import motor.motor_asyncio
from src.database.db_manager import DBManager

# Global database instance
_db_manager = None
_async_client = None
_async_db = None


def get_database():
    """Get database instance (synchronous)"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DBManager()
    return _db_manager.db


def get_db_manager():
    """Get database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DBManager()
    return _db_manager


async def get_async_database():
    """Get async database instance for motor"""
    global _async_client, _async_db

    if _async_db is None:
        # Use authenticated URI if available, fallback to basic URI
        mongo_uri = os.getenv("MONGODB_URI_AUTH")
        if not mongo_uri:
            # Fallback: build authenticated URI from components
            mongo_user = os.getenv("MONGODB_APP_USERNAME")
            mongo_pass = os.getenv("MONGODB_APP_PASSWORD")
            mongo_host = (
                os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
                .replace("mongodb://", "")
                .rstrip("/")
            )
            db_name = os.getenv("MONGODB_NAME", "ai_service_db")

            if mongo_user and mongo_pass:
                mongo_uri = f"mongodb://{mongo_user}:{mongo_pass}@{mongo_host}/{db_name}?authSource=admin"
            else:
                mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")

        db_name = os.getenv("MONGODB_NAME", "ai_service_db")

        _async_client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
        _async_db = _async_client[db_name]

        # Test connection
        await _async_client.admin.command("ping")

    return _async_db
