"""
Utility functions and helpers for Online Test System
Contains MongoDB service, R2 storage, access control, and background tasks
"""

import logging
import os
import boto3
from typing import Dict, Any, Optional
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient
from fastapi import HTTPException

import config.config as config
from src.services.test_sharing_service import get_test_sharing_service
from src.services.test_generator_service import get_test_generator_service

logger = logging.getLogger("chatbot")

# MongoDB connection helper
_mongo_client = None


def get_mongodb_service():
    """Get MongoDB database instance (helper for compatibility)"""
    global _mongo_client
    if _mongo_client is None:
        mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
            config, "MONGODB_URI", "mongodb://localhost:27017"
        )
        _mongo_client = MongoClient(mongo_uri)
    db_name = getattr(config, "MONGODB_NAME", "wordai_db")
    db = _mongo_client[db_name]

    # Return a simple object that mimics the service interface
    class MongoDBService:
        def __init__(self, database):
            self.db = database

    return MongoDBService(db)


# ========== R2 Configuration for Marketplace ==========

# R2 Configuration
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "wordai")
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "https://static.wordai.pro")

# Initialize R2 client
_s3_client = None


def get_s3_client():
    """Get or create S3 client for R2"""
    global _s3_client
    if _s3_client is None:
        if not all([R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL]):
            logger.error("❌ Missing R2 credentials")
            raise HTTPException(
                status_code=500, detail="R2 storage not configured properly"
            )

        _s3_client = boto3.client(
            "s3",
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            endpoint_url=R2_ENDPOINT_URL,
            region_name="auto",
        )
        logger.info("✅ R2 client initialized for marketplace")

    return _s3_client


async def upload_cover_to_r2(
    file_content: bytes, test_id: str, version: str, content_type: str
) -> str:
    """
    Upload test cover image to R2 and return public URL

    Cover images are stored in public 'test-covers/' directory for direct access.
    The R2 bucket has a public access policy configured for this directory.
    """
    try:
        # Generate R2 key
        key = f"test-covers/test_{test_id}_{version}.jpg"

        logger.info(f"   [R2] Uploading cover image...")
        logger.info(f"   [R2] Key: {key}")
        logger.info(f"   [R2] Size: {len(file_content)} bytes")

        s3_client = get_s3_client()

        # Upload to R2 (public read via bucket policy)
        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=file_content,
            ContentType=content_type,
        )

        # Return public URL (accessible via bucket policy)
        public_url = f"{R2_PUBLIC_URL}/{key}"
        logger.info(f"   [R2] ✅ Cover uploaded: {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"   [R2] ❌ Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cover upload failed: {str(e)}")


# ========== Phase 4: Access Control Helper ==========


def check_test_access(
    test_id: str, user_id: str, test_doc: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Check if user has access to test (owner, shared, or public)

    Args:
        test_id: Test ID
        user_id: Firebase UID
        test_doc: Optional test document (to avoid extra query)

    Returns:
        Dict with access_type ("owner", "shared", or "public") and test document

    Raises:
        HTTPException: If no access
    """
    try:
        # Get test if not provided
        if not test_doc:
            mongo_service = get_mongodb_service()
            test_doc = mongo_service.db["online_tests"].find_one(
                {"_id": ObjectId(test_id)}
            )

            if not test_doc:
                raise HTTPException(status_code=404, detail="Test not found")

        # Check if user is owner
        if test_doc.get("creator_id") == user_id:
            return {
                "access_type": "owner",
                "test": test_doc,
                "is_owner": True,
            }

        # Check if test is public on marketplace
        marketplace_config = test_doc.get("marketplace_config", {})
        if marketplace_config.get("is_public", False):
            return {
                "access_type": "public",
                "test": test_doc,
                "is_owner": False,
                "is_public": True,
            }

        # Check if test is shared with user
        sharing_service = get_test_sharing_service()
        share = sharing_service.db.test_shares.find_one(
            {
                "test_id": str(test_doc["_id"]),
                "sharee_id": user_id,
                "status": "accepted",
            }
        )

        if not share:
            raise HTTPException(
                status_code=403,
                detail="Access denied: You don't own this test and it hasn't been shared with you",
            )

        # Check deadline (priority: test's global deadline, then share-specific override)
        deadline = test_doc.get("deadline") or share.get("deadline")
        if deadline:
            if deadline.tzinfo is None:
                from datetime import timezone

                deadline = deadline.replace(tzinfo=timezone.utc)

            if deadline < datetime.now(deadline.tzinfo):
                # Auto-expire
                sharing_service.db.test_shares.update_one(
                    {"share_id": share["share_id"]}, {"$set": {"status": "expired"}}
                )
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: Deadline has passed for this shared test",
                )

        return {
            "access_type": "shared",
            "test": test_doc,
            "is_owner": False,
            "share": share,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error checking test access: {e}")
        raise HTTPException(status_code=500, detail="Failed to check test access")


# ========== Background Job for AI Generation ==========


async def generate_test_background(
    test_id: str,
    content: str,
    title: str,
    user_query: str,
    language: str,
    difficulty: Optional[str],
    num_questions: int,
    creator_id: str,
    source_type: str,
    source_id: str,
    time_limit_minutes: int,
    gemini_pdf_bytes: Optional[bytes],
    num_options: int = 4,
    num_correct_answers: int = 1,
    test_category: str = "academic",
):
    """
    Background job to generate test questions with AI
    Updates status: pending → generating → ready/failed
    """
    from pymongo import MongoClient
    import config.config as config

    mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
        config, "MONGODB_URI", "mongodb://localhost:27017"
    )
    client = MongoClient(mongo_uri)
    db_name = getattr(config, "MONGODB_NAME", "wordai_db")
    db = client[db_name]
    collection = db["online_tests"]

    try:
        # Update status to generating
        collection.update_one(
            {"_id": ObjectId(test_id)},
            {
                "$set": {
                    "status": "generating",
                    "progress_percent": 10,
                    "updated_at": datetime.now(),
                }
            },
        )
        logger.info(f"🔄 Test {test_id}: Status updated to 'generating'")

        # Generate test with AI
        test_generator = get_test_generator_service()

        logger.info(f"🤖 Calling AI to generate {num_questions} questions...")
        result = await test_generator._generate_questions_with_ai(
            content=content,
            user_query=user_query,
            language=language,
            difficulty=difficulty,
            num_questions=num_questions,
            gemini_pdf_bytes=gemini_pdf_bytes,
            num_options=num_options,
            num_correct_answers=num_correct_answers,
            test_category=test_category,
        )

        questions = result["questions"]
        diagnostic_criteria = result.get("diagnostic_criteria")

        # Update progress
        collection.update_one(
            {"_id": ObjectId(test_id)},
            {"$set": {"progress_percent": 80, "updated_at": datetime.now()}},
        )

        # Save questions
        update_fields = {
            "questions": questions,
            "status": "ready",
            "progress_percent": 100,
            "generated_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        # Add evaluation_criteria for diagnostic tests
        if test_category == "diagnostic" and diagnostic_criteria:
            import json

            update_fields["evaluation_criteria"] = json.dumps(
                diagnostic_criteria, ensure_ascii=False
            )
            logger.info(f"✅ Saved diagnostic criteria for test {test_id}")

        collection.update_one(
            {"_id": ObjectId(test_id)},
            {"$set": update_fields},
        )

        logger.info(f"✅ Test {test_id}: Generation completed successfully")

    except Exception as e:
        logger.error(f"❌ Test {test_id}: Generation failed: {e}")
        collection.update_one(
            {"_id": ObjectId(test_id)},
            {
                "$set": {
                    "status": "failed",
                    "error_message": str(e),
                    "updated_at": datetime.now(),
                }
            },
        )
        raise
