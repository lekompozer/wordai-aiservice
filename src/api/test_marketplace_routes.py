"""
Online Test Marketplace Routes
Endpoints for publishing, unpublishing, marketplace config, and earnings
"""

import logging
import os
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    UploadFile,
    File,
    Form,
    Query,
)

from src.middleware.auth import verify_firebase_token as require_auth
from src.models.online_test_models import *
from src.models.payment_models import PaymentInfoRequest, WithdrawEarningsRequest
from src.services.online_test_utils import *
from src.services.creator_name_validator import validate_creator_name
from src.utils.slug_generator import generate_unique_slug, generate_meta_description

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/tests", tags=["Test Marketplace"])


@router.post(
    "/{test_id}/marketplace/publish",
    response_model=dict,
    tags=["Phase 5 - Marketplace"],
)
async def publish_test_to_marketplace(
    test_id: str,
    cover_image: Optional[UploadFile] = File(None),
    title: str = Form(...),
    description: str = Form(...),
    short_description: Optional[str] = Form(None),
    price_points: int = Form(...),
    category: str = Form(...),
    tags: str = Form(...),
    difficulty_level: str = Form(...),
    evaluation_criteria: Optional[str] = Form(None),
    creator_name: Optional[str] = Form(None),
    user_info: dict = Depends(require_auth),
):
    """
    Publish test to marketplace with cover image and full metadata

    Requirements:
    - Test must have at least 5 questions
    - Description must be at least 50 characters
    - Title must be at least 10 characters
    - Cover image: (Optional) JPG/PNG, max 5MB, min 800x600
    - Short description: (Optional) Brief summary for listing cards
    - Price: 0 (FREE) or any positive integer
    - Evaluation criteria: (Optional) Criteria for AI evaluation, max 5000 chars

    Returns:
    - marketplace_url: Public marketplace URL
    - marketplace_config: Full marketplace configuration
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        logger.info(f"📢 Publishing test {test_id} to marketplace")
        logger.info(f"   User: {user_id}")
        logger.info(f"   Title: {title}")
        logger.info(f"   Price: {price_points} points")
        logger.info(f"   Category: {category}")

        # ========== Step 1: Validate test exists and user is creator ==========
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc.get("creator_id") != user_id:
            raise HTTPException(
                status_code=403, detail="Only test creator can publish to marketplace"
            )

        # ========== Step 2: Check if already published ==========
        if test_doc.get("marketplace_config", {}).get("is_public"):
            raise HTTPException(
                status_code=409,
                detail="Test already published. Use PATCH /marketplace/config to update.",
            )

        # ========== Step 3: Validate test requirements ==========
        if not test_doc.get("is_active", False):
            logger.warning(f"❌ Publish failed: Test {test_id} is not active")
            raise HTTPException(
                status_code=400, detail="Test must be active before publishing"
            )

        questions = test_doc.get("questions", [])

        # Check minimum questions based on question types
        min_questions = 5  # Default for MCQ/mixed tests
        has_essay_only = all(q.get("question_type") == "essay" for q in questions)

        if has_essay_only:
            min_questions = 1  # Essay tests only need 1 question

        if len(questions) < min_questions:
            logger.warning(
                f"❌ Publish failed: Test {test_id} has {len(questions)} questions (min {min_questions})"
            )
            raise HTTPException(
                status_code=400,
                detail=f"Test must have at least {min_questions} questions (current: {len(questions)})",
            )

        # ========== Step 4: Validate form inputs ==========
        if len(title) < 10:
            logger.warning(f"❌ Publish failed: Title too short ({len(title)} chars)")
            raise HTTPException(
                status_code=400, detail="Title must be at least 10 characters"
            )

        if len(description) < 50:
            logger.warning(
                f"❌ Publish failed: Description too short ({len(description)} chars)"
            )
            raise HTTPException(
                status_code=400, detail="Description must be at least 50 characters"
            )

        if price_points < 0:
            logger.warning(f"❌ Publish failed: Invalid price {price_points}")
            raise HTTPException(status_code=400, detail="Price must be >= 0")

        # Validate evaluation_criteria length if provided
        if evaluation_criteria and len(evaluation_criteria) > 5000:
            logger.warning(f"❌ Publish failed: Evaluation criteria too long")
            raise HTTPException(
                status_code=400,
                detail="Evaluation criteria must not exceed 5000 characters",
            )

        # Validate category
        valid_categories = [
            "programming",
            "language",
            "math",
            "science",
            "business",
            "technology",
            "design",
            "exam_prep",
            "certification",
            "other",
        ]
        if category not in valid_categories:
            logger.warning(f"❌ Publish failed: Invalid category '{category}'")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Valid: {', '.join(valid_categories)}",
            )

        # Validate difficulty
        valid_difficulty = ["beginner", "intermediate", "advanced", "expert"]
        if difficulty_level not in valid_difficulty:
            logger.warning(
                f"❌ Publish failed: Invalid difficulty '{difficulty_level}'"
            )
            raise HTTPException(
                status_code=400,
                detail=f"Invalid difficulty. Valid: {', '.join(valid_difficulty)}",
            )

        # Parse tags
        tags_list = [tag.strip().lower() for tag in tags.split(",") if tag.strip()]
        if len(tags_list) < 1:
            logger.warning(f"❌ Publish failed: No tags provided")
            raise HTTPException(status_code=400, detail="At least 1 tag is required")
        if len(tags_list) > 10:
            logger.warning(f"❌ Publish failed: Too many tags ({len(tags_list)})")
            raise HTTPException(status_code=400, detail="Maximum 10 tags allowed")

        # Validate creator_name if provided
        if creator_name is not None:
            if len(creator_name) < 2 or len(creator_name) > 100:
                logger.warning(
                    f"❌ Publish failed: Invalid creator_name length ({len(creator_name)} chars)"
                )
                raise HTTPException(
                    status_code=400,
                    detail="Creator name must be between 2 and 100 characters",
                )

            # Validate creator_name (uniqueness and reserved names)
            validate_creator_name(
                creator_name,
                user_info.get("email", ""),
                user_info["uid"],
                test_id,  # Allow same test to keep its name
            )
            logger.info(f"   Creator name: {creator_name}")

        # ========== Step 5.5: Generate slug and meta description ==========
        # Helper function to check if slug exists
        def check_slug_exists(slug, exclude_id):
            query = {"slug": slug}
            if exclude_id:
                query["_id"] = {"$ne": ObjectId(exclude_id)}
            return mongo_service.db["online_tests"].count_documents(query) > 0

        # Generate unique slug from title
        slug = generate_unique_slug(
            title, 
            check_slug_exists,
            max_length=100,
            exclude_id=test_id
        )
        logger.info(f"   Generated slug: {slug}")

        # Generate meta description for SEO
        meta_description = generate_meta_description(description, max_length=160)
        logger.info(f"   Meta description: {meta_description[:50]}...")

        # ========== Step 5: Validate cover image (optional) ==========
        cover_url = None
        if cover_image:
            if not cover_image.content_type in ["image/jpeg", "image/png", "image/jpg"]:
                logger.warning(
                    f"❌ Publish failed: Invalid image type {cover_image.content_type}"
                )
                raise HTTPException(
                    status_code=400,
                    detail="Cover image must be JPG or PNG",
                )

            # Read file content
            cover_content = await cover_image.read()
            cover_size_mb = len(cover_content) / (1024 * 1024)

            if cover_size_mb > 5:
                logger.warning(
                    f"❌ Publish failed: Image too large ({cover_size_mb:.2f}MB)"
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Cover image too large: {cover_size_mb:.2f}MB (max 5MB)",
                )

            logger.info(f"   Cover image size: {cover_size_mb:.2f}MB")
        else:
            logger.info(f"   No cover image provided (optional)")

        # ========== Step 6: Determine version ==========
        current_version = test_doc.get("marketplace_config", {}).get("version", 0)

        # Handle both string "v1" and int 0 formats
        if isinstance(current_version, str):
            # Extract number from "v1" -> 1
            current_version_num = int(current_version.lstrip("v"))
        else:
            current_version_num = current_version

        new_version = f"v{current_version_num + 1}"

        logger.info(f"   Creating marketplace version: {new_version}")

        # ========== Step 7: Upload cover image to R2 (if provided) ==========
        if cover_image:
            cover_url = await upload_cover_to_r2(
                cover_content, test_id, new_version, cover_image.content_type
            )
        else:
            cover_url = None

        # ========== Step 8: Create marketplace_config ==========
        marketplace_config = {
            "is_public": True,
            "version": new_version,
            "title": title,
            "description": description,
            "short_description": (
                short_description or description[:100] + "..."
                if len(description) > 100
                else description
            ),  # Auto-generate from description if not provided
            "cover_image_url": cover_url,  # None if not provided
            "price_points": price_points,
            "category": category,
            "tags": tags_list,
            "difficulty_level": difficulty_level,
            "evaluation_criteria": evaluation_criteria,  # Optional criteria for AI evaluation
            "slug": slug,  # ✅ NEW: SEO-friendly URL slug
            "meta_description": meta_description,  # ✅ NEW: SEO meta description
            "published_at": datetime.utcnow(),
            "total_participants": 0,
            "total_earnings": 0,
            "average_rating": 0.0,
            "rating_count": 0,
            "average_participant_score": 0.0,
        }

        # ========== Step 9: Update test document ==========
        update_data = {
            "marketplace_config": marketplace_config,
            "slug": slug,  # ✅ Store slug at root level for easy querying
            "meta_description": meta_description,  # ✅ Store meta at root level
            "updated_at": datetime.utcnow(),
        }

        # Add creator_name to test document if provided
        if creator_name is not None:
            update_data["creator_name"] = creator_name
            logger.info(f"   Saving creator_name: {creator_name}")

        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)},
            {"$set": update_data},
        )

        if result.modified_count == 0:
            logger.error(f"❌ Failed to update test {test_id}")
            raise HTTPException(status_code=500, detail="Failed to update test")

        # ========== Step 10: Return success response ==========
        marketplace_url = f"online-test?view=public&testId={test_id}"

        logger.info(f"✅ Test {test_id} published successfully!")
        logger.info(f"   Version: {new_version}")
        logger.info(f"   Cover: {cover_url}")
        logger.info(f"   URL: {marketplace_url}")

        return {
            "success": True,
            "test_id": test_id,
            "version": new_version,
            "marketplace_url": marketplace_url,
            "published_at": marketplace_config["published_at"].isoformat(),
            "marketplace_config": marketplace_config,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to publish test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{test_id}/marketplace/unpublish",
    response_model=dict,
    tags=["Phase 5 - Marketplace"],
)
async def unpublish_test_from_marketplace(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Unpublish test from marketplace
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        logger.info(f"🚫 Unpublishing test {test_id} from marketplace")
        logger.info(f"   User: {user_id}")

        # Check test exists
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Check ownership
        if test_doc.get("creator_id") != user_id:
            raise HTTPException(
                status_code=403,
                detail="Only test creator can unpublish from marketplace",
            )

        # Check if currently published
        marketplace_config = test_doc.get("marketplace_config", {})
        if not marketplace_config.get("is_public"):
            raise HTTPException(
                status_code=400, detail="Test is not currently published"
            )

        # Update
        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)},
            {
                "$set": {
                    "marketplace_config.is_public": False,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to unpublish test")

        logger.info(f"✅ Test {test_id} unpublished successfully")

        return {
            "success": True,
            "test_id": test_id,
            "message": "Test unpublished from marketplace",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to unpublish test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/{test_id}/marketplace/config",
    response_model=dict,
    tags=["Phase 5 - Marketplace"],
)
async def update_marketplace_config(
    test_id: str,
    cover_image: Optional[UploadFile] = File(None),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    short_description: Optional[str] = Form(None),
    creator_name: Optional[str] = Form(None),
    price_points: Optional[int] = Form(None),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    difficulty_level: Optional[str] = Form(None),
    evaluation_criteria: Optional[str] = Form(None),
    is_public: Optional[bool] = Form(None),
    user_info: dict = Depends(require_auth),
):
    """
    Update marketplace configuration for an already published test

    **Can update:**
    - cover_image: Upload new cover image (JPG/PNG, max 5MB)
    - title: Marketplace title (min 10 chars)
    - description: Full description (min 50 chars)
    - short_description: Brief summary for listing cards
    - creator_name: Display name for test creator (2-100 chars)
    - price_points: Price in points (>= 0)
    - category: Test category
    - tags: Comma-separated tags
    - difficulty_level: Difficulty (beginner/intermediate/advanced/expert)
    - evaluation_criteria: Criteria for AI evaluation (max 5000 chars)
    - is_public: Set to False to unpublish test

    **Access:**
    - Only test creator can update
    - Test must already be published (marketplace_config.is_public = true)

    **Note:**
    - All fields are optional, only update what you provide
    - Cover image: If provided, uploads new version and replaces old URL
    - Version number increments automatically on update
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        logger.info(f"🔄 Updating marketplace config for test {test_id}")
        logger.info(f"   User: {user_id}")

        # ========== Step 1: Validate test exists and user is creator ==========
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_doc.get("creator_id") != user_id:
            raise HTTPException(
                status_code=403,
                detail="Only test creator can update marketplace config",
            )

        # ========== Step 2: Check if test is published ==========
        marketplace_config = test_doc.get("marketplace_config", {})
        if not marketplace_config.get("is_public", False):
            raise HTTPException(
                status_code=400,
                detail="Test is not published. Use POST /marketplace/publish first.",
            )

        # ========== Step 3: Build update data ==========
        update_data = {}
        regenerate_slug = False
        new_title = None
        new_description = None

        # Validate and update title
        if title is not None:
            if len(title) < 10:
                raise HTTPException(
                    status_code=400, detail="Title must be at least 10 characters"
                )
            update_data["marketplace_config.title"] = title
            new_title = title
            regenerate_slug = True  # Regenerate slug when title changes
            logger.info(f"   Update title: {title}")

        # Validate and update description
        if description is not None:
            if len(description) < 50:
                raise HTTPException(
                    status_code=400, detail="Description must be at least 50 characters"
                )
            update_data["marketplace_config.description"] = description
            new_description = description
            logger.info(f"   Update description (length: {len(description)})")

        # Regenerate slug and meta if title or description changed
        if regenerate_slug or new_description:
            # Use new title or existing title
            slug_source = new_title or marketplace_config.get("title", test_doc.get("title", ""))
            
            # Helper function to check if slug exists
            def check_slug_exists(slug, exclude_id):
                query = {"slug": slug}
                if exclude_id:
                    query["_id"] = {"$ne": ObjectId(exclude_id)}
                return mongo_service.db["online_tests"].count_documents(query) > 0
            
            # Generate new unique slug
            new_slug = generate_unique_slug(
                slug_source,
                check_slug_exists,
                max_length=100,
                exclude_id=test_id
            )
            update_data["slug"] = new_slug
            update_data["marketplace_config.slug"] = new_slug
            logger.info(f"   Regenerated slug: {new_slug}")
            
            # Regenerate meta description if description changed
            if new_description:
                new_meta = generate_meta_description(new_description, max_length=160)
                update_data["meta_description"] = new_meta
                update_data["marketplace_config.meta_description"] = new_meta
                logger.info(f"   Regenerated meta: {new_meta[:50]}...")


        # Update short description
        if short_description is not None:
            update_data["marketplace_config.short_description"] = short_description
            logger.info(f"   Update short_description")

        # Update creator name
        if creator_name is not None:
            if len(creator_name) < 2 or len(creator_name) > 100:
                raise HTTPException(
                    status_code=400,
                    detail="Creator name must be between 2 and 100 characters",
                )

            # Validate creator_name (uniqueness and reserved names)
            validate_creator_name(
                creator_name,
                user_info.get("email", ""),
                user_id,
                test_id,  # Pass test_id to allow same name for same test
            )

            update_data["creator_name"] = creator_name
            logger.info(f"   Update creator_name: {creator_name}")

        # Validate and update price
        if price_points is not None:
            if price_points < 0:
                raise HTTPException(status_code=400, detail="Price must be >= 0")
            update_data["marketplace_config.price_points"] = price_points
            logger.info(f"   Update price: {price_points} points")

        # Validate and update category
        if category is not None:
            valid_categories = [
                "programming",
                "language",
                "math",
                "science",
                "business",
                "technology",
                "design",
                "exam_prep",
                "certification",
                "other",
            ]
            if category not in valid_categories:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category. Valid: {', '.join(valid_categories)}",
                )
            update_data["marketplace_config.category"] = category
            logger.info(f"   Update category: {category}")

        # Validate and update tags
        if tags is not None:
            tags_list = [tag.strip().lower() for tag in tags.split(",") if tag.strip()]
            if len(tags_list) < 1:
                raise HTTPException(
                    status_code=400, detail="At least 1 tag is required"
                )
            if len(tags_list) > 10:
                raise HTTPException(status_code=400, detail="Maximum 10 tags allowed")
            update_data["marketplace_config.tags"] = tags_list
            logger.info(f"   Update tags: {tags_list}")

        # Validate and update difficulty
        if difficulty_level is not None:
            valid_difficulty = ["beginner", "intermediate", "advanced", "expert"]
            if difficulty_level not in valid_difficulty:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid difficulty. Valid: {', '.join(valid_difficulty)}",
                )
            update_data["marketplace_config.difficulty_level"] = difficulty_level
            logger.info(f"   Update difficulty: {difficulty_level}")

        # Validate and update evaluation criteria
        if evaluation_criteria is not None:
            if len(evaluation_criteria) > 5000:
                raise HTTPException(
                    status_code=400,
                    detail="Evaluation criteria must not exceed 5000 characters",
                )
            update_data["marketplace_config.evaluation_criteria"] = evaluation_criteria
            logger.info(
                f"   Update evaluation_criteria (length: {len(evaluation_criteria)})"
            )

        # Update public status (unpublish if False)
        if is_public is not None:
            update_data["marketplace_config.is_public"] = is_public
            logger.info(f"   Update is_public: {is_public}")

        # ========== Step 4: Handle cover image upload (if provided) ==========
        if cover_image:
            logger.info(f"   New cover image provided: {cover_image.filename}")

            # Validate image
            if not cover_image.content_type in ["image/jpeg", "image/png", "image/jpg"]:
                raise HTTPException(
                    status_code=400,
                    detail="Cover image must be JPG or PNG",
                )

            # Read file content
            cover_content = await cover_image.read()
            cover_size_mb = len(cover_content) / (1024 * 1024)

            if cover_size_mb > 5:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cover image too large: {cover_size_mb:.2f}MB (max 5MB)",
                )

            logger.info(f"   Cover image size: {cover_size_mb:.2f}MB")

            # Increment version for new upload
            current_version_str = marketplace_config.get("version", "v1")
            current_version_num = int(current_version_str.replace("v", ""))
            new_version = f"v{current_version_num + 1}"

            # Upload to R2
            cover_url = await upload_cover_to_r2(
                cover_content, test_id, new_version, cover_image.content_type
            )

            update_data["marketplace_config.cover_image_url"] = cover_url
            update_data["marketplace_config.version"] = new_version
            logger.info(f"   Uploaded new cover: {cover_url}")
            logger.info(f"   New version: {new_version}")

        # ========== Step 5: Ensure at least one field to update ==========
        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No fields to update. Provide at least one field to update.",
            )

        # Add updated_at timestamp
        update_data["updated_at"] = datetime.utcnow()

        # ========== Step 6: Update in database ==========
        result = mongo_service.db["online_tests"].update_one(
            {"_id": ObjectId(test_id)}, {"$set": update_data}
        )

        if result.modified_count == 0:
            logger.warning(f"⚠️ No changes made to test {test_id} (data might be same)")

        # ========== Step 7: Get updated config ==========
        updated_test = mongo_service.db["online_tests"].find_one(
            {"_id": ObjectId(test_id)}
        )
        updated_marketplace_config = updated_test.get("marketplace_config", {})

        logger.info(f"✅ Marketplace config updated for test {test_id}")

        return {
            "success": True,
            "test_id": test_id,
            "updated_fields": list(update_data.keys()),
            "marketplace_config": updated_marketplace_config,
            "updated_at": update_data["updated_at"].isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update marketplace config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{test_id}/marketplace/details",
    response_model=dict,
    tags=["Phase 5 - Marketplace"],
)
async def get_public_test_details(
    test_id: str,
    user_info: Optional[dict] = Depends(lambda: None),
):
    """
    Get full public test details for marketplace view (before starting test)

    Returns comprehensive information including:
    - Marketplace config (title, description, cover_image, price, difficulty)
    - Test statistics (num_questions, time_limit, passing_score)
    - Community stats (total_participants, average_participant_score, average_rating)
    - User-specific data (if authenticated): already_participated, attempts_used, user_best_score

    **Access:**
    - Must be a public test (marketplace_config.is_public = true)
    - NO AUTHENTICATION REQUIRED - Anyone can view public marketplace tests
    - If authenticated, returns additional user-specific stats

    **Note:**
    - This is for VIEWING details only (before starting)
    - To start the test, use POST /{test_id}/start (authentication required, points deducted)
    """
    try:
        mongo_service = get_mongodb_service()
        user_id = user_info.get("uid") if user_info else None

        logger.info(
            f"📋 Get public test details: {test_id} (user: {user_id or 'anonymous'})"
        )

        # ========== Step 1: Get test document ==========
        test_doc = mongo_service.db["online_tests"].find_one({"_id": ObjectId(test_id)})

        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # ========== Step 2: Check if test is public ==========
        marketplace_config = test_doc.get("marketplace_config", {})
        if not marketplace_config.get("is_public", False):
            raise HTTPException(
                status_code=403,
                detail="This test is not public. Only published marketplace tests can be viewed.",
            )

        # ========== Step 3: Get user-specific data if authenticated ==========
        is_creator = False
        already_participated = None
        attempts_used = None
        user_best_score = None

        if user_id:
            # Check if user is creator
            is_creator = test_doc.get("creator_id") == user_id

            # Get user's participation history
            submissions_collection = mongo_service.db["test_submissions"]
            user_submissions = list(
                submissions_collection.find(
                    {"test_id": test_id, "user_id": user_id}
                ).sort("submitted_at", -1)
            )

            already_participated = len(user_submissions) > 0
            attempts_used = len(user_submissions)
            user_best_score = (
                max([s.get("score_percentage", 0) for s in user_submissions])
                if user_submissions
                else None
            )

        # ========== Step 4: Build response ==========
        response = {
            "success": True,
            "test_id": test_id,
            # Basic test info
            "title": marketplace_config.get("title", test_doc.get("title")),
            "description": marketplace_config.get(
                "description", test_doc.get("description")
            ),
            "short_description": marketplace_config.get("short_description"),
            "cover_image_url": marketplace_config.get("cover_image_url"),
            # Test configuration
            "num_questions": test_doc.get(
                "num_questions", len(test_doc.get("questions", []))
            ),
            "time_limit_minutes": test_doc.get("time_limit_minutes", 30),
            "passing_score": test_doc.get("passing_score", 70),
            "max_retries": test_doc.get("max_retries", 3),
            # Marketplace metadata
            "price_points": marketplace_config.get("price_points", 0),
            "category": marketplace_config.get("category"),
            "tags": marketplace_config.get("tags", []),
            "difficulty_level": marketplace_config.get("difficulty_level"),
            "version": marketplace_config.get("version"),
            # Community statistics
            "total_participants": marketplace_config.get("total_participants", 0),
            "average_participant_score": marketplace_config.get(
                "average_participant_score", 0.0
            ),
            "average_rating": marketplace_config.get("average_rating", 0.0),
            "rating_count": marketplace_config.get("rating_count", 0),
            # Publication info
            "published_at": (
                marketplace_config.get("published_at").isoformat()
                if marketplace_config.get("published_at")
                else None
            ),
            "creator_id": test_doc.get("creator_id"),
            # AI Evaluation
            "evaluation_criteria": marketplace_config.get("evaluation_criteria"),
            # Additional metadata
            "creation_type": test_doc.get("creation_type"),
            "test_language": test_doc.get(
                "test_language", test_doc.get("language", "vi")
            ),
        }

        # Add user-specific fields only if authenticated
        if user_id:
            response.update(
                {
                    "is_creator": is_creator,
                    "already_participated": already_participated,
                    "attempts_used": attempts_used,
                    "user_best_score": user_best_score,
                }
            )

        logger.info(f"✅ Public test details retrieved: {test_id}")
        logger.info(f"   Price: {response['price_points']} points")
        if user_id:
            logger.info(
                f"   User {user_id}: participated={already_participated}, attempts={attempts_used}"
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get public test details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/me/payment-info",
    response_model=dict,
    tags=["Phase 5 - Marketplace"],
)
async def set_payment_info(
    request: PaymentInfoRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Set up or update payment information for earnings withdrawal

    **Purpose:**
    - User must set up payment info before requesting withdrawal
    - This information will be used for bank transfers
    - Admin will use this info to transfer earnings

    **Required Fields:**
    - account_holder_name: Tên chủ tài khoản (exact match required for bank transfer)
    - account_number: Số tài khoản ngân hàng
    - bank_name: Tên ngân hàng (e.g., "Vietcombank", "Techcombank", "BIDV")
    - bank_branch: Chi nhánh (optional)

    **Security:**
    - Payment info is stored securely in user profile
    - Only the account owner can view/update their payment info
    - Admin can only view payment info when processing withdrawals
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        logger.info(f"💳 Setting payment info for user: {user_id}")
        logger.info(f"   Bank: {request.bank_name}")
        logger.info(f"   Account: {request.account_number}")

        # Get user document
        users_collection = mongo_service.db["users"]
        user_doc = users_collection.find_one({"firebase_uid": user_id})

        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")

        # Prepare payment info
        payment_info = {
            "account_holder_name": request.account_holder_name,
            "account_number": request.account_number,
            "bank_name": request.bank_name,
            "bank_branch": request.bank_branch,
            "updated_at": datetime.utcnow(),
        }

        # Update user document
        users_collection.update_one(
            {"firebase_uid": user_id},
            {"$set": {"payment_info": payment_info}},
        )

        logger.info(f"✅ Payment info updated for user {user_id}")

        return {
            "success": True,
            "message": "Thông tin thanh toán đã được cập nhật thành công",
            "payment_info": {
                "account_holder_name": payment_info["account_holder_name"],
                "account_number": payment_info["account_number"],
                "bank_name": payment_info["bank_name"],
                "bank_branch": payment_info.get("bank_branch"),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to set payment info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/me/payment-info",
    response_model=dict,
    tags=["Phase 5 - Marketplace"],
)
async def get_payment_info(
    user_info: dict = Depends(require_auth),
):
    """
    Get current payment information

    Returns user's saved payment info for earnings withdrawal.
    If no payment info is set up, returns null.
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        # Get user document
        users_collection = mongo_service.db["users"]
        user_doc = users_collection.find_one({"firebase_uid": user_id})

        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")

        payment_info = user_doc.get("payment_info")

        if not payment_info:
            return {
                "success": True,
                "has_payment_info": False,
                "payment_info": None,
                "message": "Chưa thiết lập thông tin thanh toán",
            }

        return {
            "success": True,
            "has_payment_info": True,
            "payment_info": {
                "account_holder_name": payment_info.get("account_holder_name"),
                "account_number": payment_info.get("account_number"),
                "bank_name": payment_info.get("bank_name"),
                "bank_branch": payment_info.get("bank_branch"),
                "updated_at": (
                    payment_info.get("updated_at").isoformat()
                    if payment_info.get("updated_at")
                    else None
                ),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get payment info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/me/earnings",
    response_model=dict,
    tags=["Phase 5 - Marketplace"],
)
async def get_my_earnings(
    user_info: dict = Depends(require_auth),
):
    """
    Get user's earnings from public tests

    Returns:
    - earnings_points: Total earnings available (can be withdrawn to cash)
    - total_earned: Lifetime earnings
    - earnings_transactions: Recent earnings history
    - pending_withdrawal: Any pending withdrawal requests

    **Note:**
    - earnings_points is separate from regular points
    - earnings_points can be withdrawn to real money
    - Regular points are for app usage only
    """
    try:
        user_id = user_info["uid"]
        mongo_service = get_mongodb_service()

        logger.info(f"💰 Get earnings for user: {user_id}")

        # Get user document (use firebase_uid)
        users_collection = mongo_service.db["users"]
        user_doc = users_collection.find_one({"firebase_uid": user_id})

        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")

        earnings_points = user_doc.get("earnings_points", 0)
        earnings_transactions = user_doc.get("earnings_transactions", [])

        # Calculate total lifetime earnings
        total_earned = sum(
            t.get("amount", 0) for t in earnings_transactions if t.get("type") == "earn"
        )

        # Get recent transactions (last 50)
        recent_transactions = sorted(
            earnings_transactions,
            key=lambda x: x.get("timestamp", datetime.min),
            reverse=True,
        )[:50]

        # Format transactions for response
        formatted_transactions = []
        for t in recent_transactions:
            formatted_transactions.append(
                {
                    "type": t.get("type"),
                    "amount": t.get("amount"),
                    "original_amount": t.get("original_amount"),
                    "percentage": t.get("percentage"),
                    "reason": t.get("reason"),
                    "test_id": t.get("test_id"),
                    "timestamp": (
                        t.get("timestamp").isoformat() if t.get("timestamp") else None
                    ),
                }
            )

        response = {
            "success": True,
            "earnings_points": earnings_points,
            "total_earned": total_earned,
            "total_withdrawn": total_earned - earnings_points,
            "recent_transactions": formatted_transactions,
        }

        logger.info(f"✅ Earnings retrieved: {earnings_points} points available")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get earnings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/me/earnings/withdraw",
    response_model=dict,
    tags=["Phase 5 - Marketplace"],
)
async def withdraw_earnings(
    request: WithdrawEarningsRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Request to withdraw earnings to real money

    **Requirements:**
    - Minimum withdrawal: 100,000 points (100,000 VND)
    - earnings_points must be sufficient
    - Payment info must be set up first (use POST /me/payment-info)
    - Withdrawal will be processed manually by admin

    **Process:**
    1. User sets up payment info (bank account details)
    2. User requests withdrawal
    3. Points are deducted and marked as "pending"
    4. Admin receives email notification
    5. Admin transfers money and marks as "completed"

    **Note:**
    - This only works with earnings_points (not regular points)
    - Withdrawals are processed within 24-48 hours
    - User will receive money via bank transfer
    """
    try:
        user_id = user_info["uid"]
        amount = request.amount
        mongo_service = get_mongodb_service()

        logger.info(f"💸 Withdrawal request: {amount} points from user {user_id}")

        # Get user document (use firebase_uid)
        users_collection = mongo_service.db["users"]
        user_doc = users_collection.find_one({"firebase_uid": user_id})

        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if payment info is set up
        payment_info = user_doc.get("payment_info")
        if not payment_info:
            raise HTTPException(
                status_code=400,
                detail="Vui lòng cài đặt thông tin thanh toán trước khi rút tiền. Sử dụng endpoint POST /api/v1/tests/me/payment-info",
            )

        earnings_points = user_doc.get("earnings_points", 0)

        # Check sufficient balance
        if earnings_points < amount:
            raise HTTPException(
                status_code=402,
                detail=f"Không đủ điểm thưởng. Bạn có {earnings_points:,} điểm nhưng yêu cầu rút {amount:,} điểm.",
            )

        # Deduct from earnings_points
        new_earnings = earnings_points - amount
        users_collection.update_one(
            {"firebase_uid": user_id},
            {
                "$set": {"earnings_points": new_earnings},
                "$push": {
                    "earnings_transactions": {
                        "type": "withdraw",
                        "amount": amount,
                        "reason": "Rút tiền về tài khoản ngân hàng",
                        "status": "pending",
                        "timestamp": datetime.utcnow(),
                        "balance_after": new_earnings,
                    }
                },
            },
        )

        # Create withdrawal request for admin review
        withdrawals_collection = mongo_service.db["withdrawal_requests"]
        withdrawal_doc = {
            "user_id": user_id,
            "amount": amount,
            "amount_vnd": amount,  # 1 point = 1 VND
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "user_email": user_info.get("email"),
            "user_name": user_info.get("name"),
            # Payment info from user profile
            "payment_info": {
                "account_holder_name": payment_info.get("account_holder_name"),
                "account_number": payment_info.get("account_number"),
                "bank_name": payment_info.get("bank_name"),
                "bank_branch": payment_info.get("bank_branch"),
            },
        }

        result = withdrawals_collection.insert_one(withdrawal_doc)
        withdrawal_id = str(result.inserted_id)

        logger.info(f"✅ Withdrawal request created: {withdrawal_id}")
        logger.info(f"   Amount: {amount:,} points ({amount:,} VND)")
        logger.info(f"   User balance: {earnings_points:,} → {new_earnings:,}")
        logger.info(
            f"   Bank: {payment_info.get('bank_name')} - {payment_info.get('account_number')}"
        )

        # Send email notification to admin
        try:
            from src.services.brevo_email_service import get_brevo_service

            brevo_service = get_brevo_service()
            admin_email = "tienhoi.lh@gmail.com"

            email_body = f"""
            <h2>🔔 Yêu cầu rút tiền mới từ WordAI</h2>

            <h3>Thông tin người yêu cầu:</h3>
            <ul>
                <li><strong>Tên:</strong> {user_info.get('name', 'N/A')}</li>
                <li><strong>Email:</strong> {user_info.get('email', 'N/A')}</li>
                <li><strong>User ID:</strong> {user_id}</li>
            </ul>

            <h3>Thông tin giao dịch:</h3>
            <ul>
                <li><strong>Số tiền:</strong> {amount:,} điểm ({amount:,} VNĐ)</li>
                <li><strong>Trạng thái:</strong> Chờ thanh toán</li>
                <li><strong>Mã giao dịch:</strong> {withdrawal_id}</li>
                <li><strong>Thời gian:</strong> {datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')} UTC</li>
            </ul>

            <h3>Thông tin chuyển khoản:</h3>
            <ul>
                <li><strong>Tên chủ TK:</strong> {payment_info.get('account_holder_name')}</li>
                <li><strong>Số tài khoản:</strong> {payment_info.get('account_number')}</li>
                <li><strong>Ngân hàng:</strong> {payment_info.get('bank_name')}</li>
                <li><strong>Chi nhánh:</strong> {payment_info.get('bank_branch', 'Không có')}</li>
            </ul>

            <p><strong>⚠️ Vui lòng xử lý yêu cầu này trong vòng 24-48 giờ.</strong></p>

            <p>Để xác nhận đã chuyển tiền, truy cập:</p>
            <p><a href="https://ai.wordai.pro/admin/withdrawals/{withdrawal_id}">https://ai.wordai.pro/admin/withdrawals/{withdrawal_id}</a></p>
            """

            brevo_service.send_email(
                to_email=admin_email,
                subject=f"🔔 Yêu cầu rút {amount:,} VNĐ từ {user_info.get('name', 'User')}",
                html_body=email_body,
            )

            logger.info(f"📧 Email notification sent to admin: {admin_email}")

        except Exception as email_error:
            logger.error(f"⚠️ Failed to send admin email notification: {email_error}")
            # Don't fail the withdrawal request if email fails

        return {
            "success": True,
            "withdrawal_id": withdrawal_id,
            "amount": amount,
            "amount_vnd": amount,
            "status": "pending",
            "message": "Yêu cầu rút tiền đã được gửi. Bạn sẽ nhận được tiền trong vòng 24-48 giờ.",
            "new_balance": new_earnings,
            "payment_info": {
                "account_holder_name": payment_info.get("account_holder_name"),
                "account_number": payment_info.get("account_number"),
                "bank_name": payment_info.get("bank_name"),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to process withdrawal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check-slug/{slug}", tags=["Test Marketplace - Slug"])
async def check_slug_availability(
    slug: str,
    exclude_test_id: Optional[str] = Query(None, description="Test ID to exclude from check (for updates)"),
):
    """
    ✅ NEW: Check if a slug is available for use
    
    Returns:
    - available: True if slug is not in use
    - suggestions: Alternative slugs if taken
    - test_id: ID of test using this slug (if taken)
    - title: Title of test using this slug (if taken)
    """
    try:
        mongo_service = get_mongodb_service()
        
        # Build query
        query = {"slug": slug, "marketplace_config.is_public": True}
        if exclude_test_id:
            try:
                query["_id"] = {"$ne": ObjectId(exclude_test_id)}
            except:
                pass  # Invalid ObjectId, ignore
        
        # Check if slug exists
        existing_test = mongo_service.db["online_tests"].find_one(
            query,
            {"_id": 1, "title": 1}
        )
        
        if existing_test:
            # Slug is taken, generate suggestions
            from src.utils.slug_generator import generate_slug
            
            suggestions = []
            for i in range(2, 6):  # Generate 4 alternatives
                alt_slug = f"{slug}-{i}"
                if not mongo_service.db["online_tests"].find_one({"slug": alt_slug, "marketplace_config.is_public": True}):
                    suggestions.append(alt_slug)
            
            return {
                "available": False,
                "slug": slug,
                "test_id": str(existing_test["_id"]),
                "title": existing_test.get("title", "Unknown"),
                "suggestions": suggestions[:3],  # Return top 3
                "message": f"Slug '{slug}' đã được sử dụng"
            }
        else:
            # Slug is available
            return {
                "available": True,
                "slug": slug,
                "message": f"Slug '{slug}' có thể sử dụng"
            }
            
    except Exception as e:
        logger.error(f"❌ Failed to check slug availability: {e}")
        raise HTTPException(status_code=500, detail=str(e))

