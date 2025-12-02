"""
Creator Name Validation Service
Validates creator_name for uniqueness and reserved names
"""

import logging
from typing import Optional
from bson import ObjectId
from fastapi import HTTPException
from pymongo import MongoClient
import config.config as config

logger = logging.getLogger("chatbot")

# Admin configuration
ADMIN_EMAIL = "tienhoi.lh@gmail.com"
RESERVED_NAMES = ["admin", "administrator", "michael le"]

# MongoDB connection
_mongo_client = None


def get_mongodb_service():
    """Get MongoDB database instance"""
    global _mongo_client
    if _mongo_client is None:
        mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
            config, "MONGODB_URI", "mongodb://localhost:27017"
        )
        _mongo_client = MongoClient(mongo_uri)
    db_name = getattr(config, "MONGODB_NAME", "wordai_db")
    db = _mongo_client[db_name]

    class MongoDBService:
        def __init__(self, database):
            self.db = database

    return MongoDBService(db)


def validate_creator_name(
    creator_name: Optional[str],
    user_email: str,
    user_id: str,
    test_id: Optional[str] = None,
) -> None:
    """
    Validate creator_name for uniqueness and reserved names

    Args:
        creator_name: The name to validate
        user_email: Current user's email
        user_id: Current user's ID
        test_id: Test ID (optional, for updates to allow same name for same test)

    Raises:
        HTTPException: If validation fails
    """
    if not creator_name:
        return  # Optional field

    creator_name_lower = creator_name.strip().lower()

    # Check reserved names (only admin can use these)
    if creator_name_lower in RESERVED_NAMES:
        if user_email != ADMIN_EMAIL:
            raise HTTPException(
                status_code=403,
                detail=f"The name '{creator_name}' is reserved for system administrators only.",
            )

    # Check uniqueness across all tests
    mongo_service = get_mongodb_service()
    collection = mongo_service.db["online_tests"]

    # Build query: find tests with same creator_name (case-insensitive)
    query = {
        "creator_name": {"$regex": f"^{creator_name}$", "$options": "i"},
        "is_active": {"$ne": False},  # Only check active tests
    }

    # If updating existing test, exclude it from uniqueness check
    if test_id:
        query["_id"] = {"$ne": ObjectId(test_id)}

    # Check if another user already uses this name
    existing = collection.find_one(query)

    if existing and existing.get("creator_id") != user_id:
        raise HTTPException(
            status_code=400,
            detail=f"The creator name '{creator_name}' is already in use. Please choose a different name.",
        )

    logger.info(f"✅ Creator name '{creator_name}' validated for user {user_id}")
