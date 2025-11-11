"""
Marketplace Transaction Routes - Phase 5
Handle purchases, ratings, and earnings transfers

Revenue Split: 80% creator, 20% platform
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId
import logging
import uuid

from ..middleware.auth import verify_firebase_token as require_auth
from pymongo import MongoClient
import config.config as config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/marketplace", tags=["Marketplace Transactions"])


# MongoDB connection helper
_mongo_client = None


def get_database():
    """Get MongoDB database instance"""
    global _mongo_client
    if _mongo_client is None:
        mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
            config, "MONGODB_URI", "mongodb://localhost:27017"
        )
        _mongo_client = MongoClient(mongo_uri)
    db_name = getattr(config, "MONGODB_NAME", "wordai_db")
    return _mongo_client[db_name]


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class PurchaseTestRequest(BaseModel):
    """Purchase a marketplace test"""

    pass  # test_id from path parameter


class RatingRequest(BaseModel):
    """Rate and comment on a test"""

    rating: int = Field(..., ge=1, le=5, description="Rating 1-5 stars")
    comment: Optional[str] = Field(
        None, max_length=1000, description="Optional comment"
    )


class TransferEarningsRequest(BaseModel):
    """Transfer earnings from test sales to user wallet"""

    amount_points: int = Field(..., gt=0, description="Points to transfer")


# ============================================================================
# PURCHASE ENDPOINT
# ============================================================================


@router.post("/tests/{test_id}/purchase")
async def purchase_test(test_id: str, user_info: dict = Depends(require_auth)):
    """
    Purchase a marketplace test

    Revenue Split:
    - 80% goes to creator's marketplace earnings
    - 20% goes to platform

    Transaction creates:
    - test_purchases record
    - 2x point_transactions (creator +80%, platform +20%)
    - Updates test stats
    """
    try:
        db = get_database()
        user_id = user_info["uid"]

        # 1. Get test
        test = db.online_tests.find_one(
            {"_id": ObjectId(test_id), "marketplace_config.is_public": True}
        )

        if not test:
            raise HTTPException(
                status_code=404, detail="Test not found or not published"
            )

        creator_id = test["creator_id"]
        price_points = test.get("marketplace_config", {}).get("price_points", 0)

        # 2. Check if user is creator
        if user_id == creator_id:
            raise HTTPException(status_code=400, detail="Cannot purchase your own test")

        # 3. Check if already purchased
        existing_purchase = db.test_purchases.find_one(
            {"test_id": test_id, "buyer_id": user_id}
        )

        if existing_purchase:
            raise HTTPException(
                status_code=400, detail="You already purchased this test"
            )

        # 4. Check user has enough points (if not free)
        if price_points > 0:
            user_points_doc = db.user_points.find_one({"user_id": user_id})
            current_balance = (
                user_points_doc.get("balance", 0) if user_points_doc else 0
            )

            if current_balance < price_points:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient points. Required: {price_points}, Available: {current_balance}",
                )

            # 5. Calculate revenue split
            creator_earnings = int(price_points * 0.8)  # 80% to creator
            platform_fee = price_points - creator_earnings  # 20% to platform

            # 6. Deduct points from buyer
            db.user_points.update_one(
                {"user_id": user_id},
                {
                    "$inc": {"balance": -price_points},
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                },
                upsert=True,
            )

            # 7. Add to creator's marketplace earnings (NOT wallet yet)
            db.online_tests.update_one(
                {"_id": ObjectId(test_id)},
                {
                    "$inc": {
                        "marketplace_config.total_revenue": creator_earnings,
                        "marketplace_config.total_purchases": 1,
                    },
                    "$set": {
                        "marketplace_config.updated_at": datetime.now(timezone.utc)
                    },
                },
            )

            # 8. Record point transactions
            now = datetime.now(timezone.utc)
            purchase_id = str(uuid.uuid4())

            # Buyer deduction
            db.point_transactions.insert_one(
                {
                    "transaction_id": f"purchase_{purchase_id}_buyer",
                    "user_id": user_id,
                    "amount": -price_points,
                    "transaction_type": "test_purchase",
                    "description": f"Purchased test: {test.get('title', 'Untitled')}",
                    "metadata": {"test_id": test_id, "purchase_id": purchase_id},
                    "created_at": now,
                }
            )

            # Creator earnings (marketplace balance, not wallet)
            db.point_transactions.insert_one(
                {
                    "transaction_id": f"purchase_{purchase_id}_creator",
                    "user_id": creator_id,
                    "amount": creator_earnings,
                    "transaction_type": "test_sale_earnings",
                    "description": f"Sale earnings (80%): {test.get('title', 'Untitled')}",
                    "metadata": {
                        "test_id": test_id,
                        "purchase_id": purchase_id,
                        "buyer_id": user_id,
                        "original_amount": price_points,
                        "revenue_share": "80%",
                    },
                    "created_at": now,
                }
            )

            # Platform fee
            db.point_transactions.insert_one(
                {
                    "transaction_id": f"purchase_{purchase_id}_platform",
                    "user_id": "PLATFORM",
                    "amount": platform_fee,
                    "transaction_type": "platform_fee",
                    "description": f"Platform fee (20%): {test.get('title', 'Untitled')}",
                    "metadata": {
                        "test_id": test_id,
                        "purchase_id": purchase_id,
                        "buyer_id": user_id,
                        "creator_id": creator_id,
                        "original_amount": price_points,
                        "revenue_share": "20%",
                    },
                    "created_at": now,
                }
            )

        else:
            # Free test - just increment purchase count
            db.online_tests.update_one(
                {"_id": ObjectId(test_id)},
                {
                    "$inc": {"marketplace_config.total_purchases": 1},
                    "$set": {
                        "marketplace_config.updated_at": datetime.now(timezone.utc)
                    },
                },
            )
            purchase_id = str(uuid.uuid4())

        # 9. Create purchase record
        purchase_doc = {
            "purchase_id": purchase_id,
            "test_id": test_id,
            "buyer_id": user_id,
            "creator_id": creator_id,
            "price_paid": price_points,
            "creator_earnings": int(price_points * 0.8) if price_points > 0 else 0,
            "platform_fee": (
                price_points - int(price_points * 0.8) if price_points > 0 else 0
            ),
            "version_purchased": test.get("marketplace_config", {}).get(
                "current_version", "v1"
            ),
            "purchased_at": datetime.now(timezone.utc),
        }

        db.test_purchases.insert_one(purchase_doc)

        logger.info(
            f"User {user_id} purchased test {test_id} for {price_points} points (80/20 split)"
        )

        return {
            "success": True,
            "message": "Test purchased successfully",
            "data": {
                "purchase_id": purchase_id,
                "test_id": test_id,
                "price_paid": price_points,
                "creator_earnings": purchase_doc["creator_earnings"],
                "platform_fee": purchase_doc["platform_fee"],
                "version": purchase_doc["version_purchased"],
                "purchased_at": purchase_doc["purchased_at"],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error purchasing test: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to purchase test: {str(e)}"
        )


# ============================================================================
# RATING ENDPOINTS
# ============================================================================


@router.post("/tests/{test_id}/ratings")
async def rate_test(
    test_id: str, request: RatingRequest, user_info: dict = Depends(require_auth)
):
    """
    Rate and comment on a test (must have purchased)
    Updates test's avg_rating and rating_count
    """
    try:
        db = get_database()
        user_id = user_info["uid"]

        # 1. Validate test exists and is published
        test = db.online_tests.find_one(
            {"_id": ObjectId(test_id), "marketplace_config.is_public": True}
        )

        if not test:
            raise HTTPException(
                status_code=404, detail="Test not found or not published"
            )

        # 2. Check if user purchased (or is creator - creators can't rate their own test)
        if user_id == test["creator_id"]:
            raise HTTPException(status_code=400, detail="Cannot rate your own test")

        purchase = db.test_purchases.find_one({"test_id": test_id, "buyer_id": user_id})

        if not purchase:
            raise HTTPException(
                status_code=400, detail="Must purchase test before rating"
            )

        # 3. Check if already rated
        existing_rating = db.test_ratings.find_one(
            {"test_id": test_id, "user_id": user_id}
        )

        now = datetime.now(timezone.utc)
        rating_id = str(uuid.uuid4())

        if existing_rating:
            # Update existing rating
            old_rating = existing_rating["rating"]

            db.test_ratings.update_one(
                {"_id": existing_rating["_id"]},
                {
                    "$set": {
                        "rating": request.rating,
                        "comment": request.comment,
                        "updated_at": now,
                    }
                },
            )

            # Recalculate average
            all_ratings = list(db.test_ratings.find({"test_id": test_id}))
            total_rating = sum(r["rating"] for r in all_ratings)
            avg_rating = total_rating / len(all_ratings)

            db.online_tests.update_one(
                {"_id": ObjectId(test_id)},
                {
                    "$set": {
                        "marketplace_config.avg_rating": round(avg_rating, 2),
                        "marketplace_config.updated_at": now,
                    }
                },
            )

            logger.info(f"Updated rating for test {test_id} by user {user_id}")

            return {
                "success": True,
                "message": "Rating updated successfully",
                "data": {
                    "rating_id": str(existing_rating["_id"]),
                    "test_id": test_id,
                    "rating": request.rating,
                    "old_rating": old_rating,
                    "new_avg_rating": round(avg_rating, 2),
                },
            }

        else:
            # Create new rating
            rating_doc = {
                "rating_id": rating_id,
                "test_id": test_id,
                "user_id": user_id,
                "rating": request.rating,
                "comment": request.comment,
                "created_at": now,
                "updated_at": now,
            }

            db.test_ratings.insert_one(rating_doc)

            # Recalculate average
            all_ratings = list(db.test_ratings.find({"test_id": test_id}))
            total_rating = sum(r["rating"] for r in all_ratings)
            avg_rating = total_rating / len(all_ratings)
            rating_count = len(all_ratings)

            db.online_tests.update_one(
                {"_id": ObjectId(test_id)},
                {
                    "$set": {
                        "marketplace_config.avg_rating": round(avg_rating, 2),
                        "marketplace_config.rating_count": rating_count,
                        "marketplace_config.updated_at": now,
                    }
                },
            )

            logger.info(f"Created rating for test {test_id} by user {user_id}")

            return {
                "success": True,
                "message": "Rating created successfully",
                "data": {
                    "rating_id": rating_id,
                    "test_id": test_id,
                    "rating": request.rating,
                    "new_avg_rating": round(avg_rating, 2),
                    "rating_count": rating_count,
                },
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rating test: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to rate test")


@router.get("/tests/{test_id}/ratings")
async def get_test_ratings(
    test_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("newest", regex="^(newest|oldest|highest|lowest)$"),
):
    """
    Get ratings for a test with pagination
    """
    try:
        db = get_database()

        # Validate test exists
        test = db.online_tests.find_one(
            {"_id": ObjectId(test_id), "marketplace_config.is_public": True}
        )

        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

        # Build sort
        sort_map = {
            "newest": [("created_at", -1)],
            "oldest": [("created_at", 1)],
            "highest": [("rating", -1), ("created_at", -1)],
            "lowest": [("rating", 1), ("created_at", -1)],
        }

        sort_order = sort_map.get(sort_by, sort_map["newest"])

        # Count total
        total = db.test_ratings.count_documents({"test_id": test_id})

        # Fetch ratings
        skip = (page - 1) * page_size
        ratings = list(
            db.test_ratings.find({"test_id": test_id})
            .sort(sort_order)
            .skip(skip)
            .limit(page_size)
        )

        # Format response with user info
        results = []
        for rating in ratings:
            user = db.users.find_one({"uid": rating["user_id"]})

            results.append(
                {
                    "rating_id": rating.get("rating_id", str(rating["_id"])),
                    "rating": rating["rating"],
                    "comment": rating.get("comment"),
                    "created_at": rating["created_at"],
                    "updated_at": rating.get("updated_at"),
                    "user": {
                        "uid": rating["user_id"],
                        "display_name": (
                            user.get("display_name", "Anonymous")
                            if user
                            else "Anonymous"
                        ),
                    },
                }
            )

        total_pages = (total + page_size - 1) // page_size

        return {
            "success": True,
            "data": {
                "ratings": results,
                "summary": {
                    "avg_rating": test.get("marketplace_config", {}).get(
                        "avg_rating", 0.0
                    ),
                    "total_ratings": total,
                },
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                },
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ratings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get ratings")


# ============================================================================
# EARNINGS MANAGEMENT
# ============================================================================


@router.get("/me/earnings")
async def get_my_earnings(user_info: dict = Depends(require_auth)):
    """
    Get current user's marketplace earnings from all tests
    Shows earnings still in marketplace (not yet transferred to wallet)
    """
    try:
        db = get_database()
        user_id = user_info["uid"]

        # Get all tests owned by user
        tests = list(db.online_tests.find({"creator_id": user_id}))

        total_earnings = 0
        test_breakdown = []

        for test in tests:
            mc = test.get("marketplace_config", {})
            if mc.get("is_public"):
                test_earnings = mc.get("total_revenue", 0)
                total_earnings += test_earnings

                test_breakdown.append(
                    {
                        "test_id": str(test["_id"]),
                        "title": test.get("title", "Untitled"),
                        "total_revenue": test_earnings,
                        "total_purchases": mc.get("total_purchases", 0),
                        "avg_rating": mc.get("avg_rating", 0.0),
                    }
                )

        return {
            "success": True,
            "data": {
                "total_earnings": total_earnings,
                "test_count": len(test_breakdown),
                "tests": test_breakdown,
            },
        }

    except Exception as e:
        logger.error(f"Error getting earnings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get earnings")


@router.post("/me/earnings/transfer")
async def transfer_earnings_to_wallet(
    request: TransferEarningsRequest, user_info: dict = Depends(require_auth)
):
    """
    Transfer earnings from marketplace to user's point wallet
    Allows withdrawing sales revenue to use or cash out
    """
    try:
        db = get_database()
        user_id = user_info["uid"]
        amount = request.amount_points

        # 1. Calculate total available earnings
        tests = list(db.online_tests.find({"creator_id": user_id}))
        total_earnings = sum(
            test.get("marketplace_config", {}).get("total_revenue", 0) for test in tests
        )

        if amount > total_earnings:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient earnings. Available: {total_earnings}, Requested: {amount}",
            )

        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")

        # 2. Deduct from tests proportionally (FIFO by revenue)
        remaining = amount
        now = datetime.now(timezone.utc)

        for test in sorted(
            tests,
            key=lambda t: t.get("marketplace_config", {}).get("total_revenue", 0),
            reverse=True,
        ):
            if remaining <= 0:
                break

            test_revenue = test.get("marketplace_config", {}).get("total_revenue", 0)
            if test_revenue > 0:
                deduct = min(remaining, test_revenue)

                db.online_tests.update_one(
                    {"_id": test["_id"]},
                    {
                        "$inc": {"marketplace_config.total_revenue": -deduct},
                        "$set": {"marketplace_config.updated_at": now},
                    },
                )

                remaining -= deduct

        # 3. Add to user wallet
        db.user_points.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": amount}, "$set": {"updated_at": now}},
            upsert=True,
        )

        # 4. Record transaction
        transaction_id = str(uuid.uuid4())
        db.point_transactions.insert_one(
            {
                "transaction_id": transaction_id,
                "user_id": user_id,
                "amount": amount,
                "transaction_type": "earnings_transfer",
                "description": f"Transferred marketplace earnings to wallet",
                "metadata": {"transfer_id": transaction_id},
                "created_at": now,
            }
        )

        # 5. Get updated balance
        updated_user_points = db.user_points.find_one({"user_id": user_id})
        new_balance = (
            updated_user_points.get("balance", 0) if updated_user_points else 0
        )

        logger.info(
            f"Transferred {amount} points from marketplace to wallet for user {user_id}"
        )

        return {
            "success": True,
            "message": "Earnings transferred to wallet successfully",
            "data": {
                "transferred_amount": amount,
                "new_wallet_balance": new_balance,
                "transaction_id": transaction_id,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error transferring earnings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to transfer earnings")


# ============================================================================
# MY PUBLIC TESTS & HISTORY ENDPOINTS
# ============================================================================


@router.get("/me/tests")
async def get_my_public_tests(
    user_info: dict = Depends(require_auth),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=50, description="Items per page"),
    status: Optional[str] = Query(
        None, description="Filter: published, unpublished, all"
    ),
):
    """
    Get my published marketplace tests with stats

    Shows all tests I've published to marketplace with:
    - Sales stats (purchases, revenue)
    - Rating stats
    - Version info
    """
    try:
        db = get_database()
        user_id = user_info["uid"]

        # Build filter
        match_filter = {"creator_id": user_id}

        if status == "published":
            match_filter["marketplace_config.is_public"] = True
        elif status == "unpublished":
            match_filter["marketplace_config.is_public"] = False
        # "all" or None = no additional filter

        # Only include tests that have marketplace_config
        match_filter["marketplace_config"] = {"$exists": True}

        # Count total
        total = db.online_tests.count_documents(match_filter)

        # Get paginated results
        skip = (page - 1) * page_size
        tests = list(
            db.online_tests.find(match_filter)
            .sort("marketplace_config.published_at", -1)
            .skip(skip)
            .limit(page_size)
        )

        results = []
        for test in tests:
            mc = test.get("marketplace_config", {})
            test_id = str(test["_id"])

            # Calculate completion stats
            total_purchases = mc.get("total_purchases", 0)
            total_completions = 0
            completion_rate = 0.0

            if total_purchases > 0:
                # Count unique users who completed this test
                completed_users = db.user_test_attempts.distinct(
                    "user_id", {"test_id": test_id, "status": "completed"}
                )
                total_completions = len(completed_users)
                completion_rate = round((total_completions / total_purchases) * 100, 1)

            results.append(
                {
                    "test_id": test_id,
                    "title": test.get("title", "Untitled"),
                    "description": mc.get("description", ""),
                    "category": mc.get("category"),
                    "tags": mc.get("tags", []),
                    "is_public": mc.get("is_public", False),
                    "price_points": mc.get("price_points", 0),
                    "cover_image_url": mc.get("cover_image_url"),
                    "thumbnail_url": mc.get("thumbnail_url"),
                    "current_version": mc.get("current_version", "v1"),
                    "stats": {
                        "total_purchases": total_purchases,
                        "total_completions": total_completions,
                        "completion_rate": completion_rate,
                        "total_revenue": mc.get("total_revenue", 0),
                        "avg_rating": mc.get("avg_rating", 0.0),
                        "rating_count": mc.get("rating_count", 0),
                    },
                    "published_at": mc.get("published_at"),
                    "updated_at": mc.get("updated_at"),
                    "question_count": len(test.get("questions", [])),
                }
            )

        return {
            "success": True,
            "data": {
                "tests": results,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size,
                },
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting my public tests: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get my public tests")


@router.get("/me/purchases")
async def get_my_purchase_history(
    user_info: dict = Depends(require_auth),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=50, description="Items per page"),
    status: Optional[str] = Query(
        None, description="Filter: not_started, in_progress, completed"
    ),
):
    """
    Get my marketplace purchase history with attempt stats

    Shows all tests I've purchased with:
    - Purchase info (date, price)
    - Attempt stats (times completed, best score, average score)
    - Test info (title, creator, category)
    """
    try:
        db = get_database()
        user_id = user_info["uid"]

        # Get all purchases
        purchases = list(
            db.test_purchases.find({"buyer_id": user_id}).sort("purchased_at", -1)
        )

        if not purchases:
            return {
                "success": True,
                "data": {
                    "purchases": [],
                    "pagination": {
                        "page": 1,
                        "page_size": page_size,
                        "total": 0,
                        "total_pages": 0,
                    },
                },
            }

        test_ids = [p["test_id"] for p in purchases]

        # Get all test info
        tests_dict = {}
        for test in db.online_tests.find(
            {"_id": {"$in": [ObjectId(tid) for tid in test_ids]}}
        ):
            tests_dict[str(test["_id"])] = test

        # Get attempt stats for each test
        results = []
        for purchase in purchases:
            test_id = purchase["test_id"]
            test = tests_dict.get(test_id)

            if not test:
                continue

            # Get attempt stats
            attempts = list(
                db.user_test_attempts.find({"user_id": user_id, "test_id": test_id})
            )

            completed_attempts = [a for a in attempts if a.get("status") == "completed"]

            # Calculate stats
            times_completed = len(completed_attempts)
            best_score = (
                max([a.get("score", 0) for a in completed_attempts])
                if completed_attempts
                else 0
            )
            avg_score = (
                sum([a.get("score", 0) for a in completed_attempts])
                / len(completed_attempts)
                if completed_attempts
                else 0
            )

            # Determine status
            attempt_status = "not_started"
            if times_completed > 0:
                attempt_status = "completed"
            elif len(attempts) > 0:
                attempt_status = "in_progress"

            # Apply status filter
            if status and status != attempt_status:
                continue

            # Get creator info
            creator = db.users.find_one({"uid": test["creator_id"]})
            mc = test.get("marketplace_config", {})

            results.append(
                {
                    "purchase_id": str(purchase["_id"]),
                    "test_id": test_id,
                    "test_info": {
                        "title": test.get("title", "Untitled"),
                        "description": mc.get("description", ""),
                        "category": mc.get("category"),
                        "tags": mc.get("tags", []),
                        "cover_image_url": mc.get("cover_image_url"),
                        "thumbnail_url": mc.get("thumbnail_url"),
                        "creator": {
                            "user_id": test["creator_id"],
                            "display_name": (
                                creator.get("display_name", "Unknown")
                                if creator
                                else "Unknown"
                            ),
                        },
                    },
                    "purchase_info": {
                        "purchased_at": purchase.get("purchased_at"),
                        "price_paid": purchase.get("price_paid", 0),
                    },
                    "attempt_stats": {
                        "status": attempt_status,
                        "times_completed": times_completed,
                        "best_score": round(best_score, 1),
                        "average_score": round(avg_score, 1),
                        "total_attempts": len(attempts),
                        "last_attempt_at": (
                            max([a.get("started_at") for a in attempts])
                            if attempts
                            else None
                        ),
                    },
                }
            )

        # Pagination
        total = len(results)
        skip = (page - 1) * page_size
        paginated_results = results[skip : skip + page_size]

        return {
            "success": True,
            "data": {
                "purchases": paginated_results,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size,
                },
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting purchase history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get purchase history")


@router.get("/me/purchases/summary")
async def get_purchase_history_summary(user_info: dict = Depends(require_auth)):
    """
    Get summary statistics for user's purchase history

    Provides:
    - Total purchased tests
    - Total completed tests
    - Pass rate (% tests with best_score >= 70)
    - Average score across all completed tests
    - Total time spent
    """
    try:
        db = get_database()
        user_id = user_info["uid"]

        # Get all purchases
        purchases = list(db.test_purchases.find({"buyer_id": user_id}))
        total_purchased = len(purchases)

        if total_purchased == 0:
            return {
                "success": True,
                "data": {
                    "total_purchased": 0,
                    "total_completed": 0,
                    "pass_rate": 0.0,
                    "average_score": 0.0,
                    "total_time_spent_minutes": 0,
                },
            }

        test_ids = [p["test_id"] for p in purchases]

        # Get all completed attempts for purchased tests
        completed_attempts = list(
            db.user_test_attempts.find(
                {
                    "user_id": user_id,
                    "test_id": {"$in": test_ids},
                    "status": "completed",
                }
            )
        )

        # Calculate stats per test
        test_best_scores = {}
        test_times = {}

        for attempt in completed_attempts:
            test_id = attempt["test_id"]
            score = attempt.get("score", 0)

            # Track best score per test
            if test_id not in test_best_scores or score > test_best_scores[test_id]:
                test_best_scores[test_id] = score

            # Track time
            if "started_at" in attempt and "completed_at" in attempt:
                time_minutes = (
                    attempt["completed_at"] - attempt["started_at"]
                ).total_seconds() / 60
                if test_id not in test_times:
                    test_times[test_id] = 0
                test_times[test_id] += time_minutes

        # Calculate summary
        total_completed = len(test_best_scores)
        passed_tests = sum(1 for score in test_best_scores.values() if score >= 70)
        pass_rate = (
            round((passed_tests / total_completed * 100), 1)
            if total_completed > 0
            else 0.0
        )
        average_score = (
            round(sum(test_best_scores.values()) / len(test_best_scores), 1)
            if test_best_scores
            else 0.0
        )
        total_time_spent = round(sum(test_times.values()), 0)

        return {
            "success": True,
            "data": {
                "total_purchased": total_purchased,
                "total_completed": total_completed,
                "pass_rate": pass_rate,
                "average_score": average_score,
                "total_time_spent_minutes": int(total_time_spent),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting purchase summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get purchase summary")


@router.get("/me/purchases/{test_id}/rank")
async def get_test_rank_percentile(
    test_id: str, user_info: dict = Depends(require_auth)
):
    """
    Get user's rank percentile for a specific test

    Compares user's best score with all other users who completed the test
    Returns percentile (e.g., 85.5 means user is in top 14.5%)
    """
    try:
        db = get_database()
        user_id = user_info["uid"]

        # Check if user purchased this test
        purchase = db.test_purchases.find_one({"buyer_id": user_id, "test_id": test_id})

        if not purchase:
            raise HTTPException(status_code=404, detail="Test not purchased")

        # Get user's best score
        user_attempts = list(
            db.user_test_attempts.find(
                {"user_id": user_id, "test_id": test_id, "status": "completed"}
            )
        )

        if not user_attempts:
            return {
                "success": True,
                "data": {
                    "test_id": test_id,
                    "user_best_score": 0.0,
                    "rank_percentile": 0.0,
                    "total_users": 0,
                    "users_below": 0,
                },
            }

        user_best_score = max([a.get("score", 0) for a in user_attempts])

        # Get all users' best scores for this test
        pipeline = [
            {"$match": {"test_id": test_id, "status": "completed"}},
            {"$group": {"_id": "$user_id", "best_score": {"$max": "$score"}}},
        ]

        all_scores = list(db.user_test_attempts.aggregate(pipeline))

        if len(all_scores) <= 1:
            return {
                "success": True,
                "data": {
                    "test_id": test_id,
                    "user_best_score": user_best_score,
                    "rank_percentile": 100.0,
                    "total_users": len(all_scores),
                    "users_below": 0,
                },
            }

        # Calculate percentile
        users_below = sum(1 for s in all_scores if s["best_score"] < user_best_score)
        total_users = len(all_scores)
        rank_percentile = round((users_below / total_users) * 100, 1)

        return {
            "success": True,
            "data": {
                "test_id": test_id,
                "user_best_score": round(user_best_score, 1),
                "rank_percentile": rank_percentile,
                "total_users": total_users,
                "users_below": users_below,
                "rank_position": total_users - users_below,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rank percentile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get rank percentile")
