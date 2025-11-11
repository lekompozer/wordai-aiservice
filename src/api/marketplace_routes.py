"""
Marketplace Routes - Phase 5
Endpoints for test marketplace where creators can sell tests

Features:
- Publish tests to marketplace with cover image
- Browse/search marketplace
- Purchase tests (80% creator, 20% platform split)
- Rate and comment on tests
- Transfer earnings to wallet
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Header
from fastapi.responses import JSONResponse
from typing import Optional, List
from pydantic import BaseModel, Field, conint
from datetime import datetime, timezone
from bson import ObjectId
import logging

from ..middleware.auth import verify_firebase_token as require_auth
from ..services.test_cover_image_service import TestCoverImageService
from ..services.test_version_service import TestVersionService
from pymongo import MongoClient
import config.config as config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


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

class MarketplaceConfig(BaseModel):
    """Marketplace configuration for a test"""
    is_public: bool = Field(default=False, description="Whether test is published")
    price_points: int = Field(ge=0, description="Points required (0 for free)")
    cover_image_url: Optional[str] = Field(None, description="Cover image URL")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail URL")
    description: Optional[str] = Field(None, max_length=2000, description="Marketplace description")
    category: Optional[str] = Field(None, description="Test category")
    tags: List[str] = Field(default_factory=list, description="Search tags")
    total_purchases: int = Field(default=0, description="Total purchase count")
    total_revenue: int = Field(default=0, description="Total points earned")
    avg_rating: float = Field(default=0.0, ge=0, le=5, description="Average rating")
    rating_count: int = Field(default=0, description="Total ratings")
    published_at: Optional[datetime] = Field(None, description="First publish time")
    updated_at: Optional[datetime] = Field(None, description="Last update time")


class PublishTestRequest(BaseModel):
    """Request to publish test to marketplace"""
    price_points: int = Field(ge=0, description="Points required (0 = free)")
    description: str = Field(..., min_length=10, max_length=2000, description="Marketplace description")
    category: Optional[str] = Field(None, description="Test category")
    tags: List[str] = Field(default_factory=list, max_items=10, description="Search tags")


class UpdateMarketplaceConfigRequest(BaseModel):
    """Update marketplace configuration"""
    price_points: Optional[int] = Field(None, ge=0, description="New price")
    description: Optional[str] = Field(None, min_length=10, max_length=2000)
    category: Optional[str] = None
    tags: Optional[List[str]] = Field(None, max_items=10)


class PurchaseTestRequest(BaseModel):
    """Purchase a marketplace test"""
    test_id: str = Field(..., description="Test ID to purchase")


class RatingRequest(BaseModel):
    """Rate and comment on a test"""
    test_id: str = Field(..., description="Test ID to rate")
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5 stars")
    comment: Optional[str] = Field(None, max_length=1000, description="Optional comment")


class TransferEarningsRequest(BaseModel):
    """Transfer earnings from test sales to user wallet"""
    amount_points: int = Field(..., gt=0, description="Points to transfer")


# ============================================================================
# MARKETPLACE ENDPOINTS
# ============================================================================

@router.post("/tests/{test_id}/publish")
async def publish_test_to_marketplace(
    test_id: str,
    price_points: int = Form(..., ge=0),
    description: str = Form(..., min_length=10, max_length=2000),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # Comma-separated
    cover_image: UploadFile = File(...),
    user_info: dict = Depends(require_auth)
):
    """
    Publish test to marketplace with cover image
    
    - Creates version snapshot (v1, v2, v3...)
    - Uploads cover image + thumbnail
    - Sets marketplace configuration
    - Validates test has questions
    
    Revenue: 80% creator, 20% platform on all purchases
    """
    try:
        db = get_database()
        cover_service = TestCoverImageService()
        version_service = TestVersionService()
        
        # 1. Validate test exists and user is owner
        test = db.online_tests.find_one({
            "_id": ObjectId(test_id),
            "creator_id": user_info["uid"]
        })
        
        if not test:
            raise HTTPException(status_code=404, detail="Test not found or unauthorized")
        
        # 2. Validate test has questions
        if not test.get("questions") or len(test["questions"]) == 0:
            raise HTTPException(status_code=400, detail="Cannot publish test with no questions")
        
        # 3. Upload cover image + thumbnail
        upload_result = await cover_service.upload_cover_image(
            file=cover_image,
            test_id=test_id
        )
        
        # 4. Create version snapshot
        version_number = await version_service.create_version_snapshot(
            test_id=test_id,
            test_data=test,
            published_by=user_info["uid"]
        )
        
        # 5. Parse tags
        tag_list = []
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            tag_list = tag_list[:10]  # Max 10 tags
        
        # 6. Update test with marketplace config
        now = datetime.now(timezone.utc)
        is_first_publish = not test.get("marketplace_config", {}).get("published_at")
        
        marketplace_config = {
            "is_public": True,
            "price_points": price_points,
            "cover_image_url": upload_result["cover_url"],
            "thumbnail_url": upload_result["thumbnail_url"],
            "description": description,
            "category": category,
            "tags": tag_list,
            "total_purchases": test.get("marketplace_config", {}).get("total_purchases", 0),
            "total_revenue": test.get("marketplace_config", {}).get("total_revenue", 0),
            "avg_rating": test.get("marketplace_config", {}).get("avg_rating", 0.0),
            "rating_count": test.get("marketplace_config", {}).get("rating_count", 0),
            "published_at": test.get("marketplace_config", {}).get("published_at", now),
            "updated_at": now,
            "current_version": version_number
        }
        
        db.online_tests.update_one(
            {"_id": ObjectId(test_id)},
            {
                "$set": {
                    "marketplace_config": marketplace_config,
                    "updated_at": now
                }
            }
        )
        
        logger.info(f"Published test {test_id} to marketplace at {price_points} points (version {version_number})")
        
        return {
            "success": True,
            "message": "Test published to marketplace successfully",
            "data": {
                "test_id": test_id,
                "version": version_number,
                "marketplace_config": marketplace_config,
                "is_first_publish": is_first_publish
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing test to marketplace: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to publish test: {str(e)}")


@router.patch("/tests/{test_id}/config")
async def update_marketplace_config(
    test_id: str,
    request: UpdateMarketplaceConfigRequest,
    user_info: dict = Depends(require_auth)
):
    """
    Update marketplace configuration (price, description, category, tags)
    Does NOT create new version - only updates metadata
    """
    try:
        db = get_database()
        
        # Validate test exists and user is owner
        test = db.online_tests.find_one({
            "_id": ObjectId(test_id),
            "creator_id": user_info["uid"],
            "marketplace_config.is_public": True
        })
        
        if not test:
            raise HTTPException(status_code=404, detail="Test not found or not published")
        
        # Build update dict
        update_fields = {}
        if request.price_points is not None:
            update_fields["marketplace_config.price_points"] = request.price_points
        if request.description is not None:
            update_fields["marketplace_config.description"] = request.description
        if request.category is not None:
            update_fields["marketplace_config.category"] = request.category
        if request.tags is not None:
            update_fields["marketplace_config.tags"] = request.tags[:10]  # Max 10
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_fields["marketplace_config.updated_at"] = datetime.now(timezone.utc)
        
        db.online_tests.update_one(
            {"_id": ObjectId(test_id)},
            {"$set": update_fields}
        )
        
        logger.info(f"Updated marketplace config for test {test_id}")
        
        return {
            "success": True,
            "message": "Marketplace configuration updated",
            "data": {
                "test_id": test_id,
                "updated_fields": list(update_fields.keys())
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating marketplace config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


@router.post("/tests/{test_id}/unpublish")
async def unpublish_test(
    test_id: str,
    user_info: dict = Depends(require_auth)
):
    """
    Unpublish test from marketplace (hide from browsing)
    Does NOT delete versions or purchase history
    """
    try:
        db = get_database()
        
        # Validate ownership
        result = db.online_tests.update_one(
            {
                "_id": ObjectId(test_id),
                "creator_id": user_info["uid"]
            },
            {
                "$set": {
                    "marketplace_config.is_public": False,
                    "marketplace_config.updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Test not found or unauthorized")
        
        logger.info(f"Unpublished test {test_id} from marketplace")
        
        return {
            "success": True,
            "message": "Test unpublished from marketplace",
            "data": {"test_id": test_id}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unpublishing test: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to unpublish test")


@router.get("/tests")
async def browse_marketplace(
    category: Optional[str] = Query(None, description="Filter by category"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    min_price: Optional[int] = Query(None, ge=0, description="Min price points"),
    max_price: Optional[int] = Query(None, ge=0, description="Max price points"),
    sort_by: str = Query("newest", regex="^(newest|oldest|popular|top_rated|price_low|price_high)$"),
    search: Optional[str] = Query(None, description="Search in title/description"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    authorization: Optional[str] = Header(None)
):
    """
    Browse marketplace tests with filters and sorting
    
    Sort options:
    - newest: Recently published
    - oldest: First published
    - popular: Most purchases
    - top_rated: Highest avg rating
    - price_low: Cheapest first
    - price_high: Most expensive first
    """
    try:
        db = get_database()
        
        # Build query
        query = {"marketplace_config.is_public": True}
        
        if category:
            query["marketplace_config.category"] = category
        
        if tag:
            query["marketplace_config.tags"] = tag
        
        if min_price is not None:
            query["marketplace_config.price_points"] = {"$gte": min_price}
        
        if max_price is not None:
            if "marketplace_config.price_points" in query:
                query["marketplace_config.price_points"]["$lte"] = max_price
            else:
                query["marketplace_config.price_points"] = {"$lte": max_price}
        
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"marketplace_config.description": {"$regex": search, "$options": "i"}}
            ]
        
        # Build sort
        sort_map = {
            "newest": [("marketplace_config.published_at", -1)],
            "oldest": [("marketplace_config.published_at", 1)],
            "popular": [("marketplace_config.total_purchases", -1)],
            "top_rated": [("marketplace_config.avg_rating", -1), ("marketplace_config.rating_count", -1)],
            "price_low": [("marketplace_config.price_points", 1)],
            "price_high": [("marketplace_config.price_points", -1)]
        }
        
        sort_order = sort_map.get(sort_by, sort_map["newest"])
        
        # Count total
        total = db.online_tests.count_documents(query)
        
        # Fetch tests
        skip = (page - 1) * page_size
        tests = list(db.online_tests.find(query).sort(sort_order).skip(skip).limit(page_size))
        
        # Format response
        results = []
        
        # Optionally verify token if provided
        user_id = None
        if authorization and authorization.startswith("Bearer "):
            try:
                from firebase_admin import auth as firebase_auth
                token = authorization.split("Bearer ")[1]
                decoded_token = firebase_auth.verify_id_token(token, check_revoked=False)
                user_id = decoded_token.get("uid")
            except:
                pass  # Ignore auth errors for optional auth
        
        for test in tests:
            test_id_str = str(test["_id"])
            creator = db.users.find_one({"uid": test["creator_id"]})
            
            # Check if user purchased
            has_purchased = False
            if user_id:
                purchase = db.test_purchases.find_one({
                    "test_id": test_id_str,
                    "buyer_id": user_id
                })
                has_purchased = purchase is not None
            
            mc = test.get("marketplace_config", {})
            
            results.append({
                "test_id": test_id_str,
                "title": test.get("title", "Untitled"),
                "description": mc.get("description", ""),
                "cover_image_url": mc.get("cover_image_url"),
                "thumbnail_url": mc.get("thumbnail_url"),
                "category": mc.get("category"),
                "tags": mc.get("tags", []),
                "price_points": mc.get("price_points", 0),
                "total_purchases": mc.get("total_purchases", 0),
                "avg_rating": mc.get("avg_rating", 0.0),
                "rating_count": mc.get("rating_count", 0),
                "published_at": mc.get("published_at"),
                "creator": {
                    "uid": test["creator_id"],
                    "display_name": creator.get("display_name", "Unknown") if creator else "Unknown"
                },
                "has_purchased": has_purchased
            })
        
        total_pages = (total + page_size - 1) // page_size
        
        return {
            "success": True,
            "data": {
                "tests": results,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error browsing marketplace: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to browse marketplace")


@router.get("/tests/{test_id}")
async def get_marketplace_test_detail(
    test_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get detailed view of marketplace test
    Includes sample questions (first 3) if not purchased
    """
    try:
        db = get_database()
        
        # Get test
        test = db.online_tests.find_one({
            "_id": ObjectId(test_id),
            "marketplace_config.is_public": True
        })
        
        if not test:
            raise HTTPException(status_code=404, detail="Test not found or not published")
        
        # Optionally verify token if provided
        user_id = None
        if authorization and authorization.startswith("Bearer "):
            try:
                from firebase_admin import auth as firebase_auth
                token = authorization.split("Bearer ")[1]
                decoded_token = firebase_auth.verify_id_token(token, check_revoked=False)
                user_id = decoded_token.get("uid")
            except:
                pass  # Ignore auth errors for optional auth
        
        # Check if user purchased
        has_purchased = False
        purchase_date = None
        if user_id:
            purchase = db.test_purchases.find_one({
                "test_id": test_id,
                "buyer_id": user_id
            })
            if purchase:
                has_purchased = True
                purchase_date = purchase.get("purchased_at")
        
        # Check if user is creator
        is_creator = user_id == test["creator_id"]
        
        # Get creator info
        creator = db.users.find_one({"uid": test["creator_id"]})
        
        mc = test.get("marketplace_config", {})
        
        # Build response
        response_data = {
            "test_id": str(test["_id"]),
            "title": test.get("title", "Untitled"),
            "description": mc.get("description", ""),
            "cover_image_url": mc.get("cover_image_url"),
            "category": mc.get("category"),
            "tags": mc.get("tags", []),
            "price_points": mc.get("price_points", 0),
            "total_purchases": mc.get("total_purchases", 0),
            "avg_rating": mc.get("avg_rating", 0.0),
            "rating_count": mc.get("rating_count", 0),
            "published_at": mc.get("published_at"),
            "updated_at": mc.get("updated_at"),
            "current_version": mc.get("current_version", "v1"),
            "creator": {
                "uid": test["creator_id"],
                "display_name": creator.get("display_name", "Unknown") if creator else "Unknown"
            },
            "question_count": len(test.get("questions", [])),
            "time_limit": test.get("time_limit"),
            "has_purchased": has_purchased,
            "is_creator": is_creator,
            "purchase_date": purchase_date
        }
        
        # Add sample questions if not purchased/creator
        if not has_purchased and not is_creator:
            questions = test.get("questions", [])
            sample_questions = questions[:3] if len(questions) >= 3 else questions
            
            # Remove correct answers from samples
            sanitized_samples = []
            for q in sample_questions:
                sanitized = {
                    "question_text": q.get("question_text", ""),
                    "question_type": q.get("question_type", "multiple_choice"),
                    "options": q.get("options", [])
                }
                sanitized_samples.append(sanitized)
            
            response_data["sample_questions"] = sanitized_samples
        
        return {
            "success": True,
            "data": response_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting marketplace test detail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get test detail")


# Note: Purchase, rating, and earnings endpoints will be added in next file
