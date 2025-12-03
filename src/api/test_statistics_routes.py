"""
Online Test Statistics API Routes
Provides statistics and analytics for online tests and user activities.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from pymongo import MongoClient
from bson import ObjectId
import logging
import config.config as config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tests/statistics", tags=["Test Statistics"])

# MongoDB connection helper
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

    # Return object with .db attribute for compatibility
    class MongoService:
        def __init__(self, client, db_name):
            self.db = client[db_name]

    return MongoService(_mongo_client, db_name)


# ========== Response Models ==========


class PopularTestItem(BaseModel):
    """Popular test item with submission count"""

    test_id: str = Field(..., description="Test ID")
    test_title: str = Field(..., description="Test title")
    slug: Optional[str] = Field(None, description="SEO-friendly URL slug")
    submission_count: int = Field(
        ..., description="Number of times this test was taken"
    )
    test_category: Optional[str] = Field(
        None, description="Test category (academic/diagnostic)"
    )
    creator_id: Optional[str] = Field(None, description="Test creator user ID")

    class Config:
        json_schema_extra = {
            "example": {
                "test_id": "692c0ce9eabefddaa798357c",
                "test_title": "Kiểm tra IQ tổng quát cho mọi lứa tuổi",
                "slug": "kiem-tra-iq-tong-quat-cho-moi-lua-tuoi",
                "submission_count": 15,
                "test_category": "academic",
                "creator_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
            }
        }


class PopularTestsResponse(BaseModel):
    """Response for popular tests statistics"""

    success: bool = Field(True, description="Request success status")
    total_tests_with_submissions: int = Field(
        ..., description="Total number of tests that have submissions"
    )
    popular_tests: List[PopularTestItem] = Field(
        ..., description="List of popular tests ordered by submission count"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "total_tests_with_submissions": 25,
                "popular_tests": [
                    {
                        "test_id": "692c0ce9eabefddaa798357c",
                        "test_title": "Kiểm tra IQ tổng quát",
                        "submission_count": 15,
                        "test_category": "academic",
                        "creator_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
                    }
                ],
            }
        }


class ActiveUserItem(BaseModel):
    """Active user item with test submission count"""

    user_id: str = Field(..., description="User ID")
    user_name: Optional[str] = Field(None, description="User display name")
    submission_count: int = Field(
        ..., description="Number of tests submitted by this user"
    )
    average_score: Optional[float] = Field(
        None, description="Average score percentage across all submissions"
    )
    passed_count: int = Field(0, description="Number of tests passed")
    failed_count: int = Field(0, description="Number of tests failed")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
                "user_name": "Nguyen Van A",
                "submission_count": 10,
                "average_score": 85.5,
                "passed_count": 8,
                "failed_count": 2,
            }
        }


class ActiveUsersResponse(BaseModel):
    """Response for active users statistics"""

    success: bool = Field(True, description="Request success status")
    total_active_users: int = Field(
        ..., description="Total number of users who have submitted tests"
    )
    active_users: List[ActiveUserItem] = Field(
        ..., description="List of active users ordered by submission count"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "total_active_users": 50,
                "active_users": [
                    {
                        "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
                        "user_name": "Nguyen Van A",
                        "submission_count": 10,
                        "average_score": 85.5,
                        "passed_count": 8,
                        "failed_count": 2,
                    }
                ],
            }
        }


# ========== Endpoints ==========


@router.get("/popular", response_model=PopularTestsResponse)
async def get_popular_tests(
    limit: int = Query(
        10, ge=1, le=100, description="Maximum number of tests to return"
    ),
    test_category: Optional[str] = Query(
        None, description="Filter by test category (academic/diagnostic)"
    ),
    days: Optional[int] = Query(
        None, ge=1, le=365, description="Filter by submissions in last N days"
    ),
):
    """
    Get most popular tests ordered by submission count

    Returns a list of tests that have been taken the most, with submission counts.
    Can be filtered by test category and time range.

    **Query Parameters:**
    - **limit**: Maximum number of tests to return (1-100, default: 10)
    - **test_category**: Filter by category ('academic' or 'diagnostic')
    - **days**: Only count submissions from last N days (1-365)

    **Returns:**
    - List of popular tests with submission counts
    - Tests are ordered by submission_count descending
    - Includes test metadata (title, category, creator)
    """
    try:
        mongo_service = get_mongodb_service()
        submissions_collection = mongo_service.db["test_submissions"]
        tests_collection = mongo_service.db["online_tests"]

        # Build match filter
        match_filter = {}

        # Filter by time range if specified
        if days:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            match_filter["submitted_at"] = {"$gte": cutoff_date}

        # Filter by test category if specified
        if test_category:
            if test_category not in ["academic", "diagnostic"]:
                raise HTTPException(
                    status_code=400,
                    detail="test_category must be 'academic' or 'diagnostic'",
                )
            match_filter["test_category"] = test_category

        # Aggregate submissions to get popular tests
        pipeline = [
            {"$match": match_filter} if match_filter else {"$match": {}},
            {
                "$group": {
                    "_id": "$test_id",
                    "submission_count": {"$sum": 1},
                    "test_title": {"$first": "$test_title"},
                    "test_category": {"$first": "$test_category"},
                }
            },
            {"$sort": {"submission_count": -1}},
            {"$limit": limit},
        ]

        popular_tests = list(submissions_collection.aggregate(pipeline))

        # Enrich with test metadata
        result_tests = []
        for item in popular_tests:
            test_id = item["_id"]

            # Get additional test info from online_tests collection
            # Handle both string and ObjectId formats
            try:
                if isinstance(test_id, str):
                    test_doc = tests_collection.find_one({"_id": ObjectId(test_id)})
                else:
                    test_doc = tests_collection.find_one({"_id": test_id})
            except Exception:
                test_doc = None

            result_tests.append(
                PopularTestItem(
                    test_id=str(test_id),
                    test_title=item.get("test_title")
                    or (test_doc.get("title") if test_doc else "Unknown Test"),
                    slug=test_doc.get("slug") if test_doc else None,
                    submission_count=item["submission_count"],
                    test_category=item.get("test_category")
                    or (test_doc.get("test_category") if test_doc else None),
                    creator_id=test_doc.get("creator_id") if test_doc else None,
                )
            )

        # Get total count of tests with submissions
        total_pipeline = [
            {"$match": match_filter} if match_filter else {"$match": {}},
            {"$group": {"_id": "$test_id"}},
            {"$count": "total"},
        ]

        total_result = list(submissions_collection.aggregate(total_pipeline))
        total_tests = total_result[0]["total"] if total_result else 0

        logger.info(
            f"✅ Retrieved {len(result_tests)} popular tests (total: {total_tests})"
        )

        return PopularTestsResponse(
            success=True,
            total_tests_with_submissions=total_tests,
            popular_tests=result_tests,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get popular tests: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve statistics: {str(e)}"
        )


@router.get("/active-users", response_model=ActiveUsersResponse)
async def get_active_users(
    limit: int = Query(
        10, ge=1, le=100, description="Maximum number of users to return"
    ),
    days: Optional[int] = Query(
        None, ge=1, le=365, description="Filter by submissions in last N days"
    ),
    min_submissions: int = Query(
        1, ge=1, description="Minimum number of submissions required"
    ),
):
    """
    Get most active users ordered by submission count

    Returns a list of users who have submitted the most tests, with their statistics.
    Can be filtered by time range and minimum submission count.

    **Query Parameters:**
    - **limit**: Maximum number of users to return (1-100, default: 10)
    - **days**: Only count submissions from last N days (1-365)
    - **min_submissions**: Minimum number of submissions required (default: 1)

    **Returns:**
    - List of active users with submission counts and statistics
    - Users are ordered by submission_count descending
    - Includes average score, pass/fail counts
    """
    try:
        mongo_service = get_mongodb_service()
        submissions_collection = mongo_service.db["test_submissions"]

        # Build match filter
        match_filter = {}

        # Filter by time range if specified
        if days:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            match_filter["submitted_at"] = {"$gte": cutoff_date}

        # Aggregate submissions to get active users
        pipeline = [
            {"$match": match_filter} if match_filter else {"$match": {}},
            {
                "$group": {
                    "_id": "$user_id",
                    "submission_count": {"$sum": 1},
                    "user_name": {"$first": "$user_name"},
                    "average_score": {
                        "$avg": {
                            "$cond": [
                                {"$ne": ["$score_percentage", None]},
                                "$score_percentage",
                                None,
                            ]
                        }
                    },
                    "passed_count": {
                        "$sum": {"$cond": [{"$eq": ["$is_passed", True]}, 1, 0]}
                    },
                    "failed_count": {
                        "$sum": {"$cond": [{"$eq": ["$is_passed", False]}, 1, 0]}
                    },
                }
            },
            {"$match": {"submission_count": {"$gte": min_submissions}}},
            {"$sort": {"submission_count": -1}},
            {"$limit": limit},
        ]

        active_users = list(submissions_collection.aggregate(pipeline))

        # Format results
        result_users = []
        for item in active_users:
            result_users.append(
                ActiveUserItem(
                    user_id=item["_id"],
                    user_name=item.get("user_name"),
                    submission_count=item["submission_count"],
                    average_score=(
                        round(item["average_score"], 2)
                        if item.get("average_score")
                        else None
                    ),
                    passed_count=item.get("passed_count", 0),
                    failed_count=item.get("failed_count", 0),
                )
            )

        # Get total count of active users
        total_pipeline = [
            {"$match": match_filter} if match_filter else {"$match": {}},
            {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gte": min_submissions}}},
            {"$count": "total"},
        ]

        total_result = list(submissions_collection.aggregate(total_pipeline))
        total_users = total_result[0]["total"] if total_result else 0

        logger.info(
            f"✅ Retrieved {len(result_users)} active users (total: {total_users})"
        )

        return ActiveUsersResponse(
            success=True,
            total_active_users=total_users,
            active_users=result_users,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get active users: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve statistics: {str(e)}"
        )
