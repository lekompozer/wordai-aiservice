"""
Online Test Taking Routes
Endpoints for accessing tests, starting, submitting, auto-save, and history
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId
import redis as _redis_sync

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
from src.services.online_test_utils import *
from src.services.ielts_scoring import score_question
from src.database.db_manager import DBManager

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/tests", tags=["Test Taking"])

# Initialize database
db_manager = DBManager()
db = db_manager.db


@router.post("/submissions/answer-media/presigned-url", tags=["Essay Answers"])
async def get_answer_media_presigned_url(
    request: PresignedURLRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Generate presigned URL for uploading media attachments with essay answers

    **Purpose**: Allow students to attach images, audio, or documents to their essay answers

    **Supported Media Types:**
    - Images: JPG, PNG, GIF (for diagrams, photos, visual explanations)
    - Audio: MP3, WAV, M4A (for voice recordings, language practice)
    - Documents: PDF, DOCX (for supplementary materials)

    **Storage Rules:**
    - Attachments count toward student's storage quota
    - Max file size: 20MB per attachment
    - Files stored in R2 at: answer-media/{user_id}/{submission_id}/{filename}

    **Flow:**
    1. Student writes essay answer and wants to attach media
    2. Frontend calls this endpoint with filename + file_size_mb
    3. Backend checks storage quota and generates presigned URL
    4. Frontend uploads file directly to R2 (PUT request)
    5. Frontend includes file_url in submission's answer object

    **Returns:**
    - presigned_url: URL for uploading file (PUT request)
    - file_url: Public URL to access file after upload
    - expires_in: Expiration time in seconds (5 minutes)
    """
    try:
        from src.services.r2_storage_service import get_r2_service
        from src.services.subscription_service import get_subscription_service

        user_id = user_info["uid"]
        logger.info(
            f"🔗 Generating presigned URL for essay answer media: user={user_id}, file={request.filename} ({request.file_size_mb}MB)"
        )

        # Validate file size (max 20MB for answer attachments)
        if request.file_size_mb > 20:
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {request.file_size_mb:.2f}MB (max 20MB for answer attachments)",
            )

        # Check storage limit
        subscription_service = get_subscription_service()
        if not await subscription_service.check_storage_limit(
            user_id, request.file_size_mb
        ):
            subscription = await subscription_service.get_subscription(user_id)
            remaining_mb = subscription.storage_limit_mb - subscription.storage_used_mb

            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Không đủ dung lượng lưu trữ",
                    "message": f"Cần: {request.file_size_mb:.2f}MB, Còn lại: {remaining_mb:.2f}MB",
                    "file_size_mb": request.file_size_mb,
                    "storage_used_mb": round(subscription.storage_used_mb, 2),
                    "storage_limit_mb": subscription.storage_limit_mb,
                    "upgrade_url": "https://ai.wordai.pro/pricing",
                },
            )

        # Get R2 service
        r2_service = get_r2_service()

        # Generate presigned URL with answer-media prefix
        result = r2_service.generate_presigned_upload_url(
            filename=f"answer-media/{user_id}/{request.filename}",
            content_type=request.content_type,
        )

        # Generate signed download URL (7 days expiration) for security
        signed_download_url = r2_service.generate_presigned_download_url(
            key=result["key"], expiration=604800  # 7 days
        )

        # Return presigned upload URL + signed download URL
        return {
            "success": True,
            "presigned_url": result["presigned_url"],
            "file_url": signed_download_url,  # ✅ Now returns signed URL instead of public
            "file_size_mb": request.file_size_mb,  # Return for frontend tracking
            "expires_in": result["expires_in"],
        }

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"❌ R2 configuration error: {e}")
        raise HTTPException(
            status_code=500, detail="File upload service not configured properly"
        )
    except Exception as e:
        logger.error(f"❌ Failed to generate presigned URL: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate upload URL: {str(e)}"
        )


# ========== NEW: Manual Test Creation Endpoint ==========


@router.get("/{test_id}")
async def get_test(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get test details - response varies by access type

    **UPDATED**: Now returns different data based on user's relationship to test

    **Owner View:**
    - Full test configuration (all settings)
    - All questions with correct answers
    - Marketplace config (if published)
    - Statistics (participants, earnings, ratings)
    - Complete edit dashboard data

    **Public View (Marketplace):**
    - Marketplace info only (cover, price, description, difficulty)
    - No questions revealed
    - Community stats (participants, average score)
    - User's participation history

    **Shared View:**
    - Questions for taking (without correct answers)
    - Basic test info

    **Access Control:**
    - Owner: Full access to all data
    - Public: Marketplace data only
    - Shared: Questions for taking
    """
    try:
        logger.info(f"📖 Get test request: {test_id} from user {user_info['uid']}")

        # Get test
        # db already initialized
        test = db["online_tests"].find_one({"_id": ObjectId(test_id)})

        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

        # ========== Check access (owner, shared, or public) ==========
        access_info = check_test_access(test_id, user_info["uid"], test)
        logger.info(f"   ✅ Access granted: type={access_info['access_type']}")

        # ========== OWNER VIEW: Return full edit dashboard data ==========
        if access_info["is_owner"]:
            logger.info(f"   🔑 Owner view: returning full data")

            # Get statistics
            submissions_collection = db["test_submissions"]
            total_submissions = submissions_collection.count_documents(
                {"test_id": test_id}
            )

            marketplace_config = test.get("marketplace_config", {})
            is_published = marketplace_config.get("is_public", False)

            # For tests with audio (listening or merged tests), include full audio sections with transcripts
            test_type = test.get("test_type", "mcq")
            # Check if test actually has audio_sections (not just test_type)
            has_audio = (
                test.get("audio_sections") and len(test.get("audio_sections", [])) > 0
            )
            audio_sections = test.get("audio_sections", []) if has_audio else None

            return {
                "success": True,
                "test_id": test_id,
                "view_type": "owner",
                "is_owner": True,
                "access_type": "owner",
                # Basic info
                "title": test.get("title"),
                "description": test.get("description"),
                "test_type": test_type,
                "test_category": test.get("test_category", "academic"),
                "is_active": test.get("is_active", True),
                "status": test.get("status", "ready"),
                # Test settings
                "max_retries": test.get("max_retries"),
                "time_limit_minutes": test.get("time_limit_minutes"),
                "passing_score": test.get("passing_score", 50),
                "deadline": (
                    test.get("deadline").isoformat() if test.get("deadline") else None
                ),
                "show_answers_timing": test.get("show_answers_timing"),
                # Questions (with correct answers for owner)
                "num_questions": len(test.get("questions", [])),
                "questions": test.get("questions", []),
                # Audio sections (for listening or merged tests with audio)
                "audio_sections": audio_sections,
                "num_audio_sections": (len(audio_sections) if audio_sections else None),
                # Creation info
                "creation_type": test.get("creation_type"),
                "test_language": test.get("test_language", test.get("language", "vi")),
                # Diagnostic/Evaluation (from root level, not marketplace_config)
                "evaluation_criteria": test.get("evaluation_criteria"),
                # Statistics
                "total_submissions": total_submissions,
                # Marketplace (if published)
                "is_published": is_published,
                "marketplace_config": marketplace_config if is_published else None,
                # Timestamps
                "created_at": test.get("created_at").isoformat(),
                "updated_at": (
                    test.get("updated_at").isoformat()
                    if test.get("updated_at")
                    else None
                ),
            }

        # ========== PUBLIC VIEW: Return marketplace data only ==========
        elif access_info["access_type"] == "public":
            logger.info(f"   🌍 Public view: returning marketplace data only")

            marketplace_config = test.get("marketplace_config", {})

            # Get user's participation history
            submissions_collection = db["test_submissions"]
            user_submissions = list(
                submissions_collection.find(
                    {"test_id": test_id, "user_id": user_info["uid"]}
                ).sort("submitted_at", -1)
            )

            already_participated = len(user_submissions) > 0
            attempts_used = len(user_submissions)
            user_best_score = (
                max([s.get("score_percentage", 0) for s in user_submissions])
                if user_submissions
                else None
            )

            return {
                "success": True,
                "test_id": test_id,
                "view_type": "public",
                "is_owner": False,
                "access_type": "public",
                # Marketplace info
                "title": marketplace_config.get("title", test.get("title")),
                "description": marketplace_config.get(
                    "description", test.get("description")
                ),
                "short_description": marketplace_config.get("short_description"),
                "cover_image_url": marketplace_config.get("cover_image_url"),
                # Test configuration (basic)
                "num_questions": len(test.get("questions", [])),
                "time_limit_minutes": test.get("time_limit_minutes"),
                "passing_score": test.get("passing_score", 50),
                "max_retries": test.get("max_retries"),
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
                "creator_id": test.get("creator_id"),
                # AI Evaluation
                "evaluation_criteria": marketplace_config.get("evaluation_criteria"),
                # User-specific info
                "already_participated": already_participated,
                "attempts_used": attempts_used,
                "user_best_score": user_best_score,
                # Additional metadata
                "creation_type": test.get("creation_type"),
                "test_language": test.get("test_language", test.get("language", "vi")),
            }

        # ========== SHARED VIEW: Return questions for taking (no answers) ==========
        else:
            logger.info(f"   👥 Shared view: returning questions for taking")

            # Check is_active for shared access
            if not test.get("is_active", False):
                raise HTTPException(status_code=403, detail="Test is not active")

            # Check if test is ready
            status = test.get("status", "ready")
            if status != "ready":
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "TEST_NOT_READY",
                        "message": f"Test is not ready yet. Current status: {status}",
                        "current_status": status,
                        "progress_percent": test.get("progress_percent", 0),
                        "tip": f"Poll GET /api/v1/tests/{test_id}/status to check when ready",
                    },
                )

            # Get questions without correct answers
            test_generator = get_test_generator_service()
            test_data = await test_generator.get_test_for_taking(
                test_id, user_info["uid"]
            )

            # Add metadata
            test_data["status"] = "ready"
            test_data["description"] = test.get("description")
            test_data["access_type"] = access_info["access_type"]
            test_data["is_owner"] = False
            test_data["view_type"] = "shared"

            return test_data

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{test_id}/start")
async def start_test(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Start a new test session

    **UPDATED Phase 4**: Now supports shared access (owner OR shared users)

    Creates a session record and returns test questions.
    Phase 2 WebSocket support for real-time progress.

    **Access Control:**
    - Owner: Unlimited attempts
    - Shared: Subject to max_retries limit
    """
    try:
        logger.info(f"🚀 Start test: {test_id} for user {user_info['uid']}")

        # Check if user has already exceeded max attempts
        # db already initialized
        test_collection = db["online_tests"]
        submissions_collection = db["test_submissions"]

        test_doc = test_collection.find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # ========== Phase 4: Check access (owner or shared) ==========
        access_info = check_test_access(test_id, user_info["uid"], test_doc)
        is_creator = access_info["is_owner"]
        is_public = access_info.get("access_type") == "public"

        logger.info(f"   ✅ Access granted: type={access_info['access_type']}")

        if is_creator:
            logger.info(f"   👤 User is test creator - unlimited attempts allowed")

        # ========== Phase 5: Deduct points for public marketplace tests ==========
        marketplace_config = test_doc.get("marketplace_config", {})
        price_points = marketplace_config.get("price_points", 0)

        # Deduct points on EVERY attempt if:
        # 1. Test is public (marketplace)
        # 2. User is NOT the creator
        # 3. Test has a price
        should_deduct_points = is_public and not is_creator and price_points > 0

        # Conversation Learning premium subscribers: free access to conversation-linked tests
        if should_deduct_points:
            try:
                _now = datetime.utcnow()
                _conv_link = db["conversation_library"].find_one(
                    {"online_test_id": ObjectId(test_id)}, {"_id": 1}
                )
                if _conv_link:
                    _conv_sub = db["user_conversation_subscription"].find_one(
                        {
                            "user_id": user_info["uid"],
                            "is_active": True,
                            "end_date": {"$gte": _now},
                        }
                    )
                    if _conv_sub:
                        should_deduct_points = False
                        logger.info(
                            f"   ✅ Conversation premium user - skipping point deduction for test {test_id}"
                        )
            except Exception as _e:
                logger.warning(f"   ⚠️ Could not check conversation premium: {_e}")

        if should_deduct_points:
            # Get user's current points
            users_collection = db["users"]
            # Query by firebase_uid (unified schema)
            user_doc = users_collection.find_one({"firebase_uid": user_info["uid"]})

            logger.info(f"   🔍 Debug user document:")
            logger.info(f"      User ID: {user_info['uid']}")
            logger.info(f"      Email: {user_info.get('email', 'N/A')}")
            logger.info(f"      User doc found: {user_doc is not None}")
            if user_doc:
                logger.info(f"      Points in doc: {user_doc.get('points', 'MISSING')}")
                logger.info(
                    f"      Earnings in doc: {user_doc.get('earnings_points', 'MISSING')}"
                )
                logger.info(
                    f"      Firebase UID: {user_doc.get('firebase_uid', 'MISSING')}"
                )

            # Auto-create or sync user profile if not exists
            if not user_doc:
                logger.info(
                    f"   📝 Creating unified user profile for {user_info['uid']}"
                )
                user_doc = {
                    "firebase_uid": user_info["uid"],  # Primary key (unified)
                    "uid": user_info["uid"],  # Alias for backward compatibility
                    "email": user_info.get("email", ""),
                    "display_name": user_info.get("name", ""),
                    "photo_url": user_info.get("picture", ""),
                    "email_verified": user_info.get("email_verified", False),
                    "provider": user_info.get("firebase", {}).get(
                        "sign_in_provider", "unknown"
                    ),
                    # Online test fields
                    "points": 0,
                    "earnings_points": 0,
                    "point_transactions": [],
                    "earnings_transactions": [],
                    # Auth system fields
                    "subscription_plan": "free",
                    "total_conversations": 0,
                    "total_files": 0,
                    "preferences": {
                        "default_ai_provider": "openai",
                        "theme": "light",
                        "language": "vi",
                    },
                    # Timestamps
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "last_login": datetime.utcnow(),
                }
                users_collection.insert_one(user_doc)
                logger.info(f"   ✅ Unified user profile created with 0 points")

            current_points = user_doc.get("points", 0)

            # Check if user has enough points
            if current_points < price_points:
                raise HTTPException(
                    status_code=402,  # Payment Required
                    detail=f"Insufficient points. You need {price_points} points but only have {current_points} points.",
                )

            # Count how many times user has started this test (for logging)
            progress_collection = db["test_progress"]
            previous_attempts = progress_collection.count_documents(
                {"test_id": test_id, "user_id": user_info["uid"]}
            )
            current_attempt_number = previous_attempts + 1

            # Deduct points from user (on EVERY attempt)
            new_points = current_points - price_points
            users_collection.update_one(
                {"firebase_uid": user_info["uid"]},  # Use firebase_uid
                {
                    "$set": {"points": new_points, "updated_at": datetime.utcnow()},
                    "$push": {
                        "point_transactions": {
                            "type": "deduct",
                            "amount": price_points,
                            "reason": f"Started test: {test_doc.get('title')} (Attempt #{current_attempt_number})",
                            "test_id": test_id,
                            "attempt_number": current_attempt_number,
                            "timestamp": datetime.utcnow(),
                            "balance_after": new_points,
                        }
                    },
                },
            )

            # ✅ BIDIRECTIONAL SYNC: Also update subscription.points_remaining
            subscriptions_collection = db["user_subscriptions"]
            subscription_doc = subscriptions_collection.find_one(
                {"user_id": user_info["uid"]}
            )
            if subscription_doc:
                points_used = subscription_doc.get("points_used", 0) + price_points
                subscriptions_collection.update_one(
                    {"user_id": user_info["uid"]},
                    {
                        "$set": {
                            "points_remaining": new_points,
                            "points_used": points_used,
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
                logger.info(
                    f"   ✅ Subscription synced: points_remaining updated to {new_points}"
                )

            # Update test's total earnings (increment on EVERY attempt)
            # This will be distributed to creator's earnings_points (80% of total)
            test_collection.update_one(
                {"_id": ObjectId(test_id)},
                {"$inc": {"marketplace_config.total_earnings": price_points}},
            )

            # Calculate creator's earnings (80% of price, rounded up)
            import math

            creator_earnings = math.ceil(price_points * 0.8)

            # Add to creator's earnings_points (separate from regular points)
            creator_id = test_doc.get("creator_id")
            users_collection.update_one(
                {"firebase_uid": creator_id},  # Use firebase_uid
                {
                    "$inc": {"earnings_points": creator_earnings},
                    "$push": {
                        "earnings_transactions": {
                            "type": "earn",
                            "amount": creator_earnings,
                            "original_amount": price_points,
                            "percentage": 80,
                            "reason": f"User started your test: {test_doc.get('title')} (Attempt #{current_attempt_number})",
                            "test_id": test_id,
                            "participant_id": user_info["uid"],
                            "attempt_number": current_attempt_number,
                            "timestamp": datetime.utcnow(),
                        }
                    },
                },
            )

            # Only increment participants count on FIRST attempt
            if current_attempt_number == 1:
                test_collection.update_one(
                    {"_id": ObjectId(test_id)},
                    {"$inc": {"marketplace_config.total_participants": 1}},
                )

            logger.info(
                f"   💰 Points deducted: {price_points} from user {user_info['uid']} (Attempt #{current_attempt_number})"
            )
            logger.info(f"   💰 Test earnings: +{price_points} (total accumulated)")
            logger.info(
                f"   💵 Creator earnings: +{creator_earnings} points ({price_points} × 80% = {creator_earnings})"
            )
            logger.info(f"   📊 User balance: {current_points} → {new_points}")

        # Get test data
        test_generator = get_test_generator_service()
        test_data = await test_generator.get_test_for_taking(test_id, user_info["uid"])

        max_retries = test_doc.get("max_retries", 1)

        # Count user's attempts from BOTH submissions AND active sessions
        # This prevents users from starting multiple sessions to bypass retry limit
        progress_collection = db["test_progress"]

        # Count completed submissions
        completed_submissions = submissions_collection.count_documents(
            {
                "test_id": test_id,
                "user_id": user_info["uid"],
            }
        )

        # Count existing sessions (completed or not)
        existing_sessions = progress_collection.count_documents(
            {
                "test_id": test_id,
                "user_id": user_info["uid"],
            }
        )

        # Total attempts = max of submissions or sessions
        # (in case of orphaned sessions without submissions)
        attempts_used = max(completed_submissions, existing_sessions)

        # Current attempt number (this new session)
        current_attempt = attempts_used + 1

        # Check if exceeds limit BEFORE creating new session
        # BUT skip check if user is the creator (owner has unlimited attempts)
        if (
            not is_creator
            and max_retries != "unlimited"
            and current_attempt > max_retries
        ):
            raise HTTPException(
                status_code=429,
                detail=f"Maximum attempts ({max_retries}) exceeded. You have used {attempts_used} attempts.",
            )

        # Create session in test_progress (Phase 2 feature, but prepare now)
        import uuid

        session_id = str(uuid.uuid4())

        progress_collection.insert_one(
            {
                "session_id": session_id,
                "test_id": test_id,
                "user_id": user_info["uid"],
                "current_answers": {},  # ✅ Dict/object, not array
                "started_at": datetime.now(),
                "last_saved_at": datetime.now(),
                "time_remaining_seconds": test_data["time_limit_minutes"] * 60,
                "is_completed": False,
                "attempt_number": current_attempt,  # Track which attempt this is
            }
        )

        logger.info(
            f"   ✅ Session created: {session_id} (Attempt {current_attempt}/{max_retries if not is_creator else 'unlimited'})"
        )

        # Calculate time values for frontend
        time_limit_seconds = test_data["time_limit_minutes"] * 60
        time_remaining_seconds = time_limit_seconds  # Full time at start

        return {
            "success": True,
            "session_id": session_id,
            "test": test_data,
            # Attempt tracking
            "current_attempt": current_attempt,  # Lần thử hiện tại (1, 2, 3...)
            "max_attempts": (
                "unlimited" if is_creator else max_retries
            ),  # Creator = unlimited
            "attempts_remaining": (
                "unlimited"
                if is_creator
                else (
                    max_retries - current_attempt
                    if max_retries != "unlimited"
                    else "unlimited"
                )
            ),
            "is_creator": is_creator,  # NEW: Frontend biết user có phải creator
            # Time tracking
            "time_limit_seconds": time_limit_seconds,
            "time_remaining_seconds": time_remaining_seconds,
            "is_completed": False,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to start test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{test_id}/submit")
async def submit_test(
    test_id: str,
    request: SubmitTestRequest,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(require_auth),
):
    """
    Submit test answers and get results

    **UPDATED Phase 3 (Essay Support)**: Now supports MCQ, Essay, and Mixed-format tests

    **Scoring Logic:**
    - MCQ questions: Auto-graded immediately
    - Essay questions: Require manual grading (score = None until graded)
    - Mixed tests: Partial score shown for MCQ, pending for Essay

    **Grading Status:**
    - auto_graded: All MCQ, scores available immediately
    - pending_grading: Has essay questions, no grading done yet
    - partially_graded: Some essays graded (not implemented yet)
    - fully_graded: All essays graded, final score available

    **Phase 4 Features:**
    - Marks shared test as "completed" status
    - Sends email notification to test owner when shared user completes
    - Creates grading queue entry for tests with essay questions
    """
    try:
        logger.info(f"📤 Submit test: {test_id} from user {user_info['uid']}")
        logger.info(f"   Answers: {len(request.user_answers)} questions")

        # ========== DEBUG: Log full payload for troubleshooting ==========
        logger.info(f"   📋 User answers payload:")
        for idx, ans in enumerate(request.user_answers, 1):
            q_id = ans.get("question_id", "N/A")
            q_type = ans.get("question_type", "mcq")

            if q_type == "mcq":
                selected = ans.get("selected_answer_keys", []) or [
                    ans.get("selected_answer_key")
                ]
                logger.info(f"      {idx}. Q{q_id} (MCQ): {selected}")
            elif q_type == "essay":
                essay_len = len(ans.get("essay_answer", ""))
                logger.info(f"      {idx}. Q{q_id} (Essay): {essay_len} chars")
            else:
                logger.info(f"      {idx}. Q{q_id} ({q_type})")

        # Get test with correct answers
        # db already initialized
        test_collection = db["online_tests"]

        test_doc = test_collection.find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # ========== Phase 5: Check access first (owner, shared, or public) ==========
        access_info = check_test_access(test_id, user_info["uid"], test_doc)
        is_owner = access_info["is_owner"]

        logger.info(f"   ✅ Access granted: type={access_info['access_type']}")

        # Check is_active ONLY for non-public tests
        if access_info["access_type"] != "public" and not test_doc.get(
            "is_active", False
        ):
            raise HTTPException(status_code=410, detail="Test is no longer active")

        # ========== NEW: Separate MCQ and Essay questions ==========
        questions = test_doc["questions"]
        total_questions = len(questions)
        test_category = test_doc.get("test_category", "academic")
        is_diagnostic = test_category == "diagnostic"

        # Count questions by type
        essay_questions = [
            q for q in questions if q.get("question_type", "mcq") == "essay"
        ]
        # All non-essay questions are auto-gradable (MCQ, true_false_multiple, matching, completion, etc.)
        auto_gradable_questions = [
            q for q in questions if q.get("question_type", "mcq") != "essay"
        ]

        has_essay = len(essay_questions) > 0
        has_mcq = len(auto_gradable_questions) > 0

        logger.info(
            f"   📊 Test format: {len(auto_gradable_questions)} auto-gradable, {len(essay_questions)} Essay"
        )
        logger.info(f"   📊 Test category: {test_category}")

        # Create answer maps for all question types
        user_answers_map = {}
        for ans in request.user_answers:
            q_id = ans.get("question_id")
            ans_type = ans.get("question_type", "mcq")

            if ans_type == "mcq":
                # Support both new (selected_answer_keys) and legacy (selected_answer_key)
                selected_answers = ans.get("selected_answer_keys", [])
                if not selected_answers and "selected_answer_key" in ans:
                    selected_answers = [ans.get("selected_answer_key")]

                user_answers_map[q_id] = {
                    "type": "mcq",
                    "selected_answer_keys": selected_answers,
                }

            elif ans_type == "matching":
                user_answers_map[q_id] = {
                    "type": "matching",
                    "matches": ans.get("matches", {}),
                }

            elif ans_type == "map_labeling":
                user_answers_map[q_id] = {
                    "type": "map_labeling",
                    "labels": ans.get("labels", {}),
                }

            elif ans_type in ["completion", "sentence_completion", "short_answer"]:
                user_answers_map[q_id] = {
                    "type": ans_type,
                    "answers": ans.get("answers", {}),
                }

            elif ans_type == "essay":
                user_answers_map[q_id] = {
                    "type": "essay",
                    "essay_answer": ans.get("essay_answer", ""),
                    "media_attachments": ans.get(
                        "media_attachments", []
                    ),  # Store media attachments (images, audio, documents)
                }

            elif ans_type == "true_false_multiple":
                user_answers_map[q_id] = {
                    "type": "true_false_multiple",
                    "user_answer": ans.get("user_answer", {}),
                }

        # ========== Auto-grade ALL auto-gradable questions (MCQ + IELTS types) ==========
        mcq_correct_count = 0
        mcq_score = 0
        results = []

        # Get all auto-gradable questions (MCQ + IELTS types)
        auto_gradable_questions = [
            q for q in questions if q.get("question_type", "mcq") != "essay"
        ]

        # For diagnostic tests, skip correct/incorrect scoring
        if is_diagnostic:
            # Diagnostic test - no scoring, just save answers
            for q in auto_gradable_questions:
                question_id = q["question_id"]
                question_type = q.get("question_type", "mcq")
                user_answer_data = user_answers_map.get(question_id, {})

                results.append(
                    {
                        "question_id": question_id,
                        "question_text": q["question_text"],
                        "question_type": question_type,
                        "user_answer": user_answer_data,
                        "is_correct": None,
                        "explanation": q.get("explanation"),
                        "max_points": q.get("max_points", 1),
                        "points_awarded": 0,  # No points for diagnostic
                    }
                )
        else:
            # Academic test - score using IELTS scoring logic
            for q in auto_gradable_questions:
                question_id = q["question_id"]
                question_type = q.get("question_type", "mcq")
                user_answer_data = user_answers_map.get(question_id, {})

                # Use new IELTS scoring system
                is_correct, points_earned, feedback = score_question(
                    q, user_answer_data
                )

                if is_correct:
                    mcq_correct_count += 1

                mcq_score += points_earned

                # Build result based on question type
                result = {
                    "question_id": question_id,
                    "question_text": q["question_text"],
                    "question_type": question_type,
                    "is_correct": is_correct,
                    "explanation": q.get("explanation"),
                    "max_points": q.get("max_points", 1),
                    "points_awarded": points_earned,
                    "feedback": feedback,
                }

                # Add type-specific fields for result
                if question_type == "mcq":
                    result["selected_answer_keys"] = user_answer_data.get(
                        "selected_answer_keys", []
                    )
                    # Use correct_answers as primary, fallback to correct_answer_keys
                    result["correct_answer_keys"] = q.get("correct_answers") or q.get(
                        "correct_answer_keys", []
                    )
                elif question_type == "matching":
                    result["user_matches"] = user_answer_data.get("matches", {})
                    # Use correct_answers as primary, fallback to correct_matches
                    result["correct_matches"] = q.get("correct_answers") or q.get(
                        "correct_matches", {}
                    )
                elif question_type == "map_labeling":
                    result["user_labels"] = user_answer_data.get("labels", {})
                    # Use correct_answers as primary, fallback to correct_labels
                    result["correct_labels"] = q.get("correct_answers") or q.get(
                        "correct_labels", {}
                    )
                elif question_type in [
                    "completion",
                    "sentence_completion",
                    "short_answer",
                ]:
                    result["user_answers"] = user_answer_data.get("answers", {})
                    # Don't expose all correct answers immediately (show after deadline if configured)
                    # Frontend will show feedback only

                elif question_type == "true_false_multiple":
                    # Add statement-by-statement breakdown
                    # Support both NEW format (options + correct_answers) and LEGACY format (statements)
                    statements = q.get("statements", [])
                    options = q.get("options", [])
                    correct_answers = q.get("correct_answers", [])

                    # Convert NEW format to unified format if needed
                    if options and correct_answers and not statements:
                        statements = [
                            {
                                "key": opt.get("option_key"),
                                "text": opt.get("option_text"),
                                "correct_value": opt.get("option_key")
                                in correct_answers,
                            }
                            for opt in options
                        ]

                    user_answers = user_answer_data.get("user_answer", {})
                    breakdown = {}

                    for stmt in statements:
                        key = stmt.get("key")
                        correct_value = stmt.get("correct_value")
                        user_value = user_answers.get(key)

                        breakdown[key] = {
                            "user": user_value,
                            "correct": correct_value,
                            "is_correct": user_value == correct_value,
                        }

                    result["statements"] = (
                        statements  # Include all statements with correct_value
                    )
                    result["user_answer"] = user_answers  # User's choices
                    result["breakdown"] = breakdown  # Statement-by-statement comparison
                    result["scoring_mode"] = q.get("scoring_mode", "partial")

                results.append(result)

        # ========== Add essay questions to results (not graded yet) ==========
        for q in essay_questions:
            question_id = q["question_id"]
            user_answer_data = user_answers_map.get(question_id, {})
            essay_answer = user_answer_data.get("essay_answer", "")
            media_attachments = user_answer_data.get("media_attachments", [])

            results.append(
                {
                    "question_id": question_id,
                    "question_text": q["question_text"],
                    "question_type": "essay",
                    "your_answer": essay_answer,
                    "media_attachments": media_attachments,  # Include student's media attachments
                    "max_points": q.get("max_points", 1),
                    "grading_status": "pending",
                    "points_awarded": None,  # Not graded yet
                }
            )

        # ========== Determine grading status ==========
        if has_essay:
            grading_status = "pending_grading"
            # Final score is None until all essays are graded
            final_score = None
            score_percentage = None
        else:
            grading_status = "auto_graded"
            # Calculate final score for all auto-gradable questions (MCQ + IELTS types)
            total_max_points = sum(
                q.get("max_points", 1) for q in auto_gradable_questions
            )
            final_score = (
                round(mcq_score / total_max_points * 10, 2)
                if total_max_points > 0
                else 0
            )
            score_percentage = (
                round(mcq_score / total_max_points * 100, 2)
                if total_max_points > 0
                else 0
            )

        # Check if passed based on test's passing_score setting
        passing_score_threshold = test_doc.get("passing_score", 70)  # Default 70%
        is_passed = (
            score_percentage >= passing_score_threshold
            if score_percentage is not None
            else False
        )

        # ========== NEW: Handle diagnostic test - deduct 1 point for AI evaluation ==========
        has_sufficient_points_for_ai = True
        if is_diagnostic and not is_owner:
            users_collection = db["users"]
            user_doc = users_collection.find_one({"firebase_uid": user_info["uid"]})

            if not user_doc:
                # Create user profile if doesn't exist
                user_doc = {
                    "firebase_uid": user_info["uid"],
                    "uid": user_info["uid"],
                    "email": user_info.get("email", ""),
                    "display_name": user_info.get("name", ""),
                    "points": 0,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
                users_collection.insert_one(user_doc)
                logger.info(f"   ✅ Created user profile with 0 points")

            current_points = user_doc.get("points", 0)
            ai_evaluation_cost = 1  # 1 point for AI evaluation

            if current_points < ai_evaluation_cost:
                has_sufficient_points_for_ai = False
                logger.warning(
                    f"   ⚠️ User has {current_points} points, need {ai_evaluation_cost} for AI evaluation"
                )
                logger.info(
                    f"   💾 Saving submission WITHOUT AI evaluation due to insufficient points"
                )
            else:
                # Deduct point for AI evaluation
                new_points = current_points - ai_evaluation_cost
                users_collection.update_one(
                    {"firebase_uid": user_info["uid"]},
                    {
                        "$set": {"points": new_points, "updated_at": datetime.utcnow()},
                        "$push": {
                            "point_transactions": {
                                "type": "deduct",
                                "amount": ai_evaluation_cost,
                                "reason": f"AI evaluation for diagnostic test: {test_doc.get('title')}",
                                "test_id": test_id,
                                "timestamp": datetime.utcnow(),
                                "balance_after": new_points,
                            }
                        },
                    },
                )
                logger.info(
                    f"   💸 Deducted {ai_evaluation_cost} point for AI evaluation (balance: {new_points})"
                )

        # ========== Validate time limit ==========
        # Get session to check started_at time
        progress_collection = db["test_progress"]
        session = progress_collection.find_one(
            {"test_id": test_id, "user_id": user_info["uid"], "is_completed": False},
            sort=[("started_at", -1)],  # Get most recent session
        )

        time_taken_seconds = 0
        if session and session.get("started_at"):
            started_at = session.get("started_at")
            submitted_at = datetime.now()
            time_taken_seconds = int((submitted_at - started_at).total_seconds())

            # Check if exceeded time limit
            time_limit_seconds = test_doc.get("time_limit_minutes", 30) * 60

            if time_taken_seconds > time_limit_seconds:
                # Time exceeded - reject submission and return latest result
                logger.warning(
                    f"⏰ Time limit exceeded: {time_taken_seconds}s > {time_limit_seconds}s"
                )

                # Get latest submission if exists
                submissions_collection = db["test_submissions"]
                latest_submission = submissions_collection.find_one(
                    {
                        "test_id": test_id,
                        "user_id": user_info["uid"],
                    },
                    sort=[("submitted_at", -1)],
                )

                if latest_submission:
                    # Return latest submission result
                    return {
                        "success": False,
                        "error": "time_limit_exceeded",
                        "message": f"Thời gian làm bài đã hết ({time_limit_seconds // 60} phút). Kết quả được lấy từ lần nộp gần nhất.",
                        "time_taken_seconds": time_taken_seconds,
                        "time_limit_seconds": time_limit_seconds,
                        "latest_submission": {
                            "submission_id": str(latest_submission["_id"]),
                            "score": latest_submission.get("score"),
                            "score_percentage": latest_submission.get(
                                "score_percentage"
                            ),
                            "grading_status": latest_submission.get(
                                "grading_status", "auto_graded"
                            ),
                            "is_passed": latest_submission.get("is_passed", False),
                            "submitted_at": latest_submission.get(
                                "submitted_at"
                            ).isoformat(),
                        },
                    }
                else:
                    # No previous submission - fail with 0 score
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "error": "time_limit_exceeded",
                            "message": f"Thời gian làm bài đã hết ({time_limit_seconds // 60} phút) và không có lần nộp bài nào trước đó.",
                            "time_taken_seconds": time_taken_seconds,
                            "time_limit_seconds": time_limit_seconds,
                        },
                    )

        logger.info(f"   ⏱️ Time taken: {time_taken_seconds}s")

        # Count attempt number
        submissions_collection = db["test_submissions"]
        attempt_number = (
            submissions_collection.count_documents(
                {
                    "test_id": test_id,
                    "user_id": user_info["uid"],
                }
            )
            + 1
        )

        # Get user info for statistics
        users_collection = db["users"]
        user_doc = users_collection.find_one({"firebase_uid": user_info["uid"]})
        user_name = None
        if user_doc:
            user_name = (
                user_doc.get("display_name")
                or user_doc.get("name")
                or user_doc.get("email")
            )

        # Build enriched user_answers with scoring data
        enriched_user_answers = []
        for user_ans in request.user_answers:
            q_id = user_ans.get("question_id")
            # Find corresponding result with scoring
            result = next((r for r in results if r["question_id"] == q_id), None)

            # Start with original user answer
            enriched_ans = dict(user_ans)

            # Add scoring data if available
            if result:
                enriched_ans["max_points"] = result.get("max_points", 1)
                enriched_ans["points_earned"] = result.get("points_awarded")
                if "is_correct" in result:
                    enriched_ans["is_correct"] = result["is_correct"]

            enriched_user_answers.append(enriched_ans)

        # Save submission
        submission_doc = {
            "test_id": test_id,
            "test_title": test_doc.get("title"),  # For statistics
            "test_category": test_category,  # NEW: Store test category
            "user_id": user_info["uid"],
            "user_name": user_name,  # For statistics
            "user_answers": enriched_user_answers,  # Use enriched answers with scoring
            "grading_status": grading_status,  # NEW: auto_graded or pending_grading
            "score": final_score,  # None if has essay, score/10 if MCQ only
            "score_percentage": score_percentage,  # None if has essay
            "mcq_score": mcq_score if has_mcq else None,  # NEW: Separate MCQ score
            "mcq_correct_count": mcq_correct_count if has_mcq else None,  # NEW
            "total_questions": total_questions,
            "correct_answers": (
                mcq_correct_count if not has_essay else None
            ),  # Only MCQ for now
            "time_taken_seconds": time_taken_seconds,
            "attempt_number": attempt_number,
            "is_passed": is_passed,
            "essay_grades": [],  # Will be populated later by grading endpoint
            "submitted_at": datetime.now(),
            # NEW: Diagnostic test fields
            "is_diagnostic_test": is_diagnostic,
            "has_ai_evaluation": is_diagnostic and has_sufficient_points_for_ai,
            "evaluation_criteria": (
                test_doc.get("evaluation_criteria") if is_diagnostic else None
            ),
        }

        result = submissions_collection.insert_one(submission_doc)
        submission_id = str(result.inserted_id)

        # ========== Phase 1: Push learning event if test is linked to conversation ==========
        # learning_events_worker handles XP, streak, achievements, dual-part completion asynchronously
        try:
            conv_library = db["conversation_library"]
            linked_conv = conv_library.find_one(
                {"online_test_id": ObjectId(test_id)},
                projection={"conversation_id": 1, "_id": 0},
            )
            if linked_conv and score_percentage is not None:
                _redis = _redis_sync.Redis(
                    host="redis-server", port=6379, db=0, decode_responses=True
                )
                _redis.lpush(
                    "queue:learning_events",
                    json.dumps(
                        {
                            "event_id": str(uuid.uuid4()),
                            "event_type": "test_submitted",
                            "user_id": user_info["uid"],
                            "conversation_id": linked_conv["conversation_id"],
                            "test_id": test_id,
                            "score": score_percentage,  # 0-100
                            "correct": mcq_correct_count if has_mcq else 0,
                            "total": len(auto_gradable_questions),
                            "time_spent": time_taken_seconds,
                            "is_first_attempt": attempt_number == 1,
                            "grading_status": grading_status,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    ),
                )
                logger.info(
                    f"📤 learning_events: test_submitted conv={linked_conv['conversation_id']} "
                    f"user={user_info['uid']} score={score_percentage}"
                )
        except Exception as _le:
            logger.warning(f"learning_events push failed (test_submit): {_le}")

        # ========== NEW: Add to grading queue if has essay questions ==========
        if has_essay:
            grading_queue = db["grading_queue"]

            # Get student name
            user_doc = db.users.find_one({"firebase_uid": user_info["uid"]})
            student_name = (
                user_doc.get("name") or user_doc.get("display_name")
                if user_doc
                else None
            )

            queue_entry = {
                "submission_id": submission_id,
                "test_id": test_id,
                "test_title": test_doc.get("title", "Untitled Test"),
                "student_id": user_info["uid"],
                "student_name": student_name,
                "submitted_at": datetime.now().isoformat(),
                "essay_question_count": len(essay_questions),
                "graded_count": 0,
                "assigned_to": None,
                "priority": 0,
                "status": "pending",
            }

            grading_queue.insert_one(queue_entry)
            logger.info(
                f"   📋 Added to grading queue: {len(essay_questions)} essays to grade"
            )

            # ========== Phase 5: Send notification to owner about new submission ==========
            async def send_new_submission_notification():
                try:
                    from src.services.brevo_email_service import get_brevo_service

                    # Get owner info
                    owner_id = test_doc.get("creator_id")
                    owner = db.users.find_one({"firebase_uid": owner_id})

                    if owner and owner.get("email"):
                        brevo = get_brevo_service()
                        await asyncio.to_thread(
                            brevo.send_new_submission_notification,
                            to_email=owner["email"],
                            owner_name=owner.get("name")
                            or owner.get("display_name")
                            or "Teacher",
                            student_name=student_name or "Unknown Student",
                            test_title=test_doc["title"],
                            essay_count=len(essay_questions),
                        )
                        logger.info(
                            f"   📧 Sent new submission notification to owner {owner['email']}"
                        )
                except Exception as e:
                    logger.error(
                        f"   ⚠️ Failed to send new submission notification: {e}"
                    )

            background_tasks.add_task(send_new_submission_notification)

        # Mark session as completed (if exists)
        progress_collection.update_many(
            {"test_id": test_id, "user_id": user_info["uid"], "is_completed": False},
            {"$set": {"is_completed": True, "last_saved_at": datetime.now()}},
        )

        # ========== Phase 4: Mark shared test as completed ==========
        if not is_owner:
            sharing_service = get_test_sharing_service()
            sharing_service.mark_test_completed(test_id, user_info["uid"])
            logger.info(f"   ✅ Marked shared test as completed")

            # Send completion notification to owner (background task)
            async def send_completion_notification():
                try:
                    from src.services.brevo_email_service import get_brevo_service

                    # Get owner info
                    owner_id = test_doc.get("creator_id")
                    owner = db.users.find_one({"firebase_uid": owner_id})

                    # Get user info
                    user = db.users.find_one({"firebase_uid": user_info["uid"]})

                    if owner and user:
                        owner_email = owner.get("email")
                        owner_name = (
                            owner.get("name") or owner.get("display_name") or "Owner"
                        )
                        user_name = (
                            user.get("name")
                            or user.get("display_name")
                            or user.get("email", "Someone")
                        )

                        # Calculate time taken (placeholder for now)
                        time_taken_minutes = (
                            submission_doc.get("time_taken_seconds", 0) // 60
                        )

                        brevo = get_brevo_service()
                        await asyncio.to_thread(
                            brevo.send_test_completion_notification,
                            to_email=owner_email,
                            owner_name=owner_name,
                            user_name=user_name,
                            test_title=test_doc["title"],
                            score=final_score if final_score is not None else 0,
                            is_passed=submission_doc["is_passed"],
                            time_taken_minutes=max(1, time_taken_minutes),
                        )
                        logger.info(
                            f"   📧 Sent completion email to owner {owner_email}"
                        )
                except Exception as e:
                    logger.error(f"   ⚠️ Failed to send completion notification: {e}")

            background_tasks.add_task(send_completion_notification)

        logger.info(
            f"✅ Test submitted: grading_status={grading_status}, "
            f"score={final_score if final_score is not None else 'pending'}, "
            f"attempt={attempt_number}"
        )

        # ========== NEW: Check show_answers_timing setting ==========
        show_answers_timing = test_doc.get("show_answers_timing", "immediate")
        deadline = test_doc.get("deadline")
        should_hide_answers = False

        if show_answers_timing == "after_deadline" and deadline:
            # Make deadline timezone-aware if needed
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)

            current_time = datetime.now(timezone.utc)

            # Hide answers if deadline not passed yet
            if current_time < deadline:
                should_hide_answers = True
                logger.info(
                    f"   🔒 Hiding answers until deadline: {deadline.isoformat()}"
                )

        # Build response based on show_answers_timing and grading_status
        if not should_hide_answers:
            # Full response - show everything
            response = {
                "success": True,
                "submission_id": submission_id,
                "grading_status": grading_status,  # NEW
                "score": final_score,  # None if pending grading
                "score_percentage": score_percentage,  # None if pending grading
                "total_questions": total_questions,
                "correct_answers": (
                    mcq_correct_count if has_mcq else 0
                ),  # Only MCQ count
                "attempt_number": attempt_number,
                "is_passed": is_passed,
                "results": results,
                "essay_grades": None if has_essay else [],  # Null until graded
                # NEW: Diagnostic test fields
                "is_diagnostic_test": is_diagnostic,
                "has_ai_evaluation": is_diagnostic and has_sufficient_points_for_ai,
            }

            # Add message if pending grading
            if grading_status == "pending_grading":
                response["message"] = (
                    "Bài thi chứa câu hỏi tự luận và đang chờ được chấm điểm."
                )
            elif is_diagnostic and not has_sufficient_points_for_ai:
                response["message"] = (
                    "Không đủ điểm để đánh giá AI. Câu trả lời đã được lưu nhưng bạn cần nạp thêm điểm để nhận kết quả phân tích từ AI."
                )
            elif is_diagnostic:
                response["message"] = (
                    "Đã lưu câu trả lời. AI đang phân tích kết quả của bạn. Vui lòng đợi trong giây lát để xem kết quả chi tiết."
                )
        else:
            # Limited response - hide detailed results until deadline
            response = {
                "success": True,
                "submission_id": submission_id,
                "grading_status": grading_status,
                "score": final_score,
                "score_percentage": score_percentage,
                "total_questions": total_questions,
                "correct_answers": mcq_correct_count if has_mcq else 0,
                "is_passed": is_passed,
                "results_hidden_until_deadline": deadline.isoformat(),
                "message": "Detailed answers will be revealed after the deadline",
            }

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{test_id}/sync-answers")
async def sync_answers(
    test_id: str,
    request: dict,
    user_info: dict = Depends(require_auth),
):
    """
    Sync answers to session (HTTP endpoint for reconnection)

    **Use case**: Frontend reconnect sau khi mất kết nối WebSocket

    Frontend gửi FULL answers để sync với backend. Backend sẽ overwrite
    toàn bộ current_answers của session.

    **UPDATED**: Hỗ trợ MCQ và Essay với media attachments

    **Request Body:**
    ```json
    {
        "session_id": "uuid-string",
        "answers": {
            "q1": {"question_type": "mcq", "selected_answer_key": "A"},
            "q2": {
                "question_type": "essay",
                "essay_answer": "text...",
                "media_attachments": [
                    {"media_type": "image", "media_url": "...", "filename": "..."}
                ]
            }
        }
    }
    ```

    Legacy format (vẫn hỗ trợ): answers: {"q1": "A", "q2": "B"}

    **Response:**
    ```json
    {
        "success": true,
        "session_id": "uuid-string",
        "answers_count": 5,
        "saved_at": "2025-11-15T10:30:00Z"
    }
    ```
    """
    try:
        session_id = request.get("session_id")
        answers = request.get("answers", {})

        if not session_id:
            raise HTTPException(
                status_code=400, detail="Missing required field: session_id"
            )

        logger.info(
            f"🔄 Sync answers for session {session_id[:8]}... "
            f"from user {user_info['uid']}: {len(answers)} answers"
        )

        # Get session and verify ownership
        # db already initialized
        progress_collection = db["test_progress"]

        session = progress_collection.find_one({"session_id": session_id})

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Verify session belongs to user
        if session.get("user_id") != user_info["uid"]:
            raise HTTPException(
                status_code=403, detail="Session does not belong to user"
            )

        # Check if session is already completed
        if session.get("is_completed"):
            raise HTTPException(status_code=410, detail="Session already completed")

        # Check if time has expired
        test_collection = db["online_tests"]
        test = test_collection.find_one({"_id": ObjectId(test_id)})

        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

        time_limit_seconds = test.get("time_limit_minutes", 30) * 60
        started_at = session.get("started_at")

        if started_at:
            elapsed_seconds = (datetime.now() - started_at).total_seconds()
            if elapsed_seconds > time_limit_seconds:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "time_expired",
                        "message": "Thời gian làm bài đã hết. Không thể sync answers.",
                        "elapsed_seconds": int(elapsed_seconds),
                        "time_limit_seconds": time_limit_seconds,
                    },
                )

        # Normalize answers (support both object and legacy string format)
        normalized_answers = {}
        for question_id, answer_data in answers.items():
            if isinstance(answer_data, str):
                # Legacy: simple string = MCQ answer key
                normalized_answers[question_id] = {
                    "question_type": "mcq",
                    "selected_answer_key": answer_data,
                }
            elif isinstance(answer_data, dict):
                # New: full answer object (MCQ or Essay)
                normalized_answers[question_id] = answer_data
            else:
                logger.warning(
                    f"Invalid answer format for {question_id}: {type(answer_data)}"
                )
                continue

        # Update answers in database (overwrite)
        result = progress_collection.update_one(
            {"session_id": session_id, "is_completed": False},
            {
                "$set": {
                    "current_answers": normalized_answers,
                    "last_saved_at": datetime.now(),
                }
            },
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to sync answers. Session may be inactive.",
            )

        saved_at = datetime.now()
        logger.info(f"✅ Synced {len(answers)} answers for session {session_id[:8]}...")

        return {
            "success": True,
            "session_id": session_id,
            "answers_count": len(answers),
            "saved_at": saved_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to sync answers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me/submissions")
async def get_my_submissions(
    user_info: dict = Depends(require_auth),
):
    """
    Get list of test submissions by the current user

    **Updated for test-history page:**
    - Groups submissions by test_id
    - Shows test details with submission count and scores
    - Supports both owned tests and community/shared tests
    """
    try:
        logger.info(f"📊 Get my submissions for user {user_info['uid']}")

        # db already initialized
        submissions_collection = db["test_submissions"]
        test_collection = db["online_tests"]

        # Get user's submissions
        submissions = list(
            submissions_collection.find(
                {"user_id": user_info["uid"]}, sort=[("submitted_at", -1)]
            )
        )

        # Group submissions by test_id
        test_submissions_map = {}
        for sub in submissions:
            test_id = sub["test_id"]
            if test_id not in test_submissions_map:
                test_submissions_map[test_id] = []
            test_submissions_map[test_id].append(sub)

        # Build response with test details
        result = []
        for test_id, test_subs in test_submissions_map.items():
            test_doc = test_collection.find_one({"_id": ObjectId(test_id)})

            if test_doc:
                # Get best score and latest submission
                sorted_subs = sorted(
                    test_subs, key=lambda x: x.get("score") or 0, reverse=True
                )
                best_submission = sorted_subs[0]
                latest_submission = sorted(
                    test_subs, key=lambda x: x["submitted_at"], reverse=True
                )[0]

                # Build submission history
                submission_history = []
                for sub in sorted(
                    test_subs, key=lambda x: x["submitted_at"], reverse=True
                ):
                    submission_history.append(
                        {
                            "submission_id": str(sub["_id"]),
                            "attempt_number": sub.get("attempt_number", 1),
                            "score": sub.get("score"),
                            "score_percentage": sub.get("score_percentage"),
                            "is_passed": sub.get("is_passed", False),
                            "is_diagnostic_test": sub.get("is_diagnostic_test", False),
                            "has_ai_evaluation": sub.get("has_ai_evaluation", True),
                            "grading_status": sub.get("grading_status", "auto_graded"),
                            "submitted_at": sub["submitted_at"].isoformat(),
                        }
                    )

                result.append(
                    {
                        "test_id": test_id,
                        "test_title": test_doc["title"],
                        "test_description": test_doc.get("description"),
                        "test_category": test_doc.get("test_category", "academic"),
                        "test_creator_id": test_doc.get("creator_id"),
                        "is_owner": test_doc.get("creator_id") == user_info["uid"],
                        "total_attempts": len(test_subs),
                        "best_score": best_submission.get("score"),
                        "best_score_percentage": best_submission.get(
                            "score_percentage"
                        ),
                        "latest_attempt_at": latest_submission[
                            "submitted_at"
                        ].isoformat(),
                        "submission_history": submission_history,
                    }
                )

        # Sort by latest attempt
        result.sort(key=lambda x: x["latest_attempt_at"], reverse=True)

        return {"tests": result}

    except Exception as e:
        logger.error(f"❌ Failed to get submissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me/submissions/{submission_id}")
async def get_submission_detail(
    submission_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get detailed results of a specific submission

    **UPDATED Phase 3**: Now supports Essay and Mixed-format tests

    **Response includes:**
    - grading_status: auto_graded, pending_grading, partially_graded, fully_graded
    - MCQ results with auto-grading
    - Essay results with grading status and feedback (if graded)
    - Conditional score (None if pending grading)
    """
    try:
        logger.info(f"🔍 Get submission detail: {submission_id}")

        # db already initialized
        submissions_collection = db["test_submissions"]

        submission = submissions_collection.find_one({"_id": ObjectId(submission_id)})

        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        if submission["user_id"] != user_info["uid"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Get test for question details
        test_collection = db["online_tests"]
        test_doc = test_collection.find_one({"_id": ObjectId(submission["test_id"])})

        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # ========== Build results (MCQ and Essay) ==========
        results = []

        # Create maps for quick lookup (ALL question types)
        user_answers_map = {}
        for ans in submission["user_answers"]:
            q_id = ans.get("question_id")
            ans_type = ans.get("question_type", "mcq")

            if ans_type == "mcq":
                # Support both new (selected_answer_keys) and legacy (selected_answer_key)
                selected_answers = ans.get("selected_answer_keys", [])
                if not selected_answers and "selected_answer_key" in ans:
                    selected_answers = [ans.get("selected_answer_key")]

                user_answers_map[q_id] = {
                    "type": "mcq",
                    "selected_answer_keys": selected_answers,
                }
            elif ans_type == "matching":
                user_answers_map[q_id] = {
                    "type": "matching",
                    "matches": ans.get("matches", {}),
                }
            elif ans_type == "completion":
                user_answers_map[q_id] = {
                    "type": "completion",
                    "answers": ans.get("answers", {}),
                }
            elif ans_type == "sentence_completion":
                user_answers_map[q_id] = {
                    "type": "sentence_completion",
                    "answers": ans.get("answers", {}),
                }
            elif ans_type == "short_answer":
                user_answers_map[q_id] = {
                    "type": "short_answer",
                    "answers": ans.get("answers", {}),
                }
            elif ans_type == "essay":
                user_answers_map[q_id] = {
                    "type": "essay",
                    "essay_answer": ans.get("essay_answer", ""),
                    "media_attachments": ans.get("media_attachments", []),
                }
            elif ans_type == "true_false_multiple":
                user_answers_map[q_id] = {
                    "type": "true_false_multiple",
                    "user_answer": ans.get("user_answer", {}),
                }

        # Get essay grades if available
        essay_grades_map = {}
        if submission.get("essay_grades"):
            for grade in submission["essay_grades"]:
                essay_grades_map[grade["question_id"]] = grade

        for q in test_doc["questions"]:
            question_id = q["question_id"]
            q_type = q.get("question_type", "mcq")
            user_answer_data = user_answers_map.get(question_id, {})

            if q_type == "mcq":
                # MCQ result
                user_answers = user_answer_data.get("selected_answer_keys", [])

                # Get correct answers - use correct_answers as primary field
                correct_answers = (
                    q.get("correct_answers")
                    or q.get("correct_answer_keys")
                    or (
                        [q.get("correct_answer_key")]
                        if "correct_answer_key" in q
                        else []
                    )
                )

                # Compare as sets (all answers must match)
                is_correct = (
                    set(user_answers) == set(correct_answers)
                    if (correct_answers and user_answers)
                    else None
                )

                result_data = {
                    "question_id": question_id,
                    "question_text": q["question_text"],
                    "question_type": "mcq",
                    "options": q.get("options", []),
                    "selected_answer_keys": user_answers,
                    "explanation": q.get("explanation"),
                    "max_points": q.get("max_points", 1),
                }

                # Only include correct_answer and is_correct for academic tests
                if correct_answers:
                    result_data["correct_answer_keys"] = correct_answers
                    result_data["is_correct"] = is_correct
                    result_data["points_awarded"] = (
                        q.get("max_points", 1) if is_correct else 0
                    )
                else:
                    # Diagnostic test - no correct/incorrect concept
                    result_data["correct_answer_keys"] = None
                    result_data["is_correct"] = None
                    result_data["points_awarded"] = 0

                results.append(result_data)

            elif q_type in [
                "matching",
                "completion",
                "sentence_completion",
                "short_answer",
            ]:
                # IELTS question types - Use ielts_scoring module
                user_answer_data = user_answers_map.get(question_id, {})

                # Score using IELTS scoring logic
                is_correct, points_earned, feedback = score_question(
                    q, user_answer_data
                )

                result = {
                    "question_id": question_id,
                    "question_text": q["question_text"],
                    "question_type": q_type,
                    "is_correct": is_correct,
                    "max_points": q.get("max_points", 1),
                    "points_awarded": points_earned,
                    "feedback": feedback,
                    "explanation": q.get("explanation"),
                }

                # Add type-specific fields
                if q_type == "matching":
                    result["left_items"] = q.get("left_items", [])
                    result["right_options"] = q.get("right_options", [])
                    result["user_matches"] = user_answer_data.get("matches", {})
                    # Use correct_answers as primary, fallback to correct_matches
                    result["correct_matches"] = q.get("correct_answers") or q.get(
                        "correct_matches", {}
                    )

                elif q_type == "completion":
                    result["template"] = q.get("template", "")
                    result["blanks"] = q.get("blanks", [])
                    result["user_answers"] = user_answer_data.get("answers", {})

                    # Completion has 2 formats:
                    # 1. Standard: correct_answers at root (array of {blank_key, answers})
                    # 2. Listening: questions array (each with key, text, correct_answers)
                    if q.get("questions"):
                        # Listening format - questions array contains correct answers
                        result["questions"] = q.get("questions", [])
                    else:
                        # Standard format - correct_answers at root
                        result["correct_answers"] = q.get("correct_answers", [])

                elif q_type == "sentence_completion":
                    result["sentences"] = q.get("sentences", [])
                    result["user_answers"] = user_answer_data.get("answers", {})
                    result["correct_answers"] = q.get("correct_answers", {})

                elif q_type == "short_answer":
                    result["user_answers"] = user_answer_data.get("answers", {})
                    # Short answer can have either:
                    # - questions array (IELTS format with multiple sub-questions)
                    # - correct_answers dict (legacy format)
                    if "questions" in q:
                        result["questions"] = q.get("questions", [])
                    else:
                        result["correct_answers"] = q.get("correct_answers", {})

                results.append(result)

            elif q_type == "true_false_multiple":
                # True/False Multiple - Use ielts_scoring module
                user_answer_data = user_answers_map.get(question_id, {})

                # Score using IELTS scoring logic
                is_correct, points_earned, feedback = score_question(
                    q, user_answer_data
                )

                # Calculate statement-by-statement breakdown
                statements = q.get("statements", [])
                user_answers = user_answer_data.get("user_answer", {})
                breakdown = {}

                for stmt in statements:
                    key = stmt.get("key")
                    correct_value = stmt.get("correct_value")
                    user_value = user_answers.get(key)

                    breakdown[key] = {
                        "user": user_value,
                        "correct": correct_value,
                        "is_correct": user_value == correct_value,
                    }

                result = {
                    "question_id": question_id,
                    "question_text": q["question_text"],
                    "question_type": "true_false_multiple",
                    "is_correct": is_correct,
                    "max_points": q.get("max_points", 1),
                    "points_awarded": points_earned,
                    "feedback": feedback,
                    "explanation": q.get("explanation"),
                    "statements": statements,  # Include all statements with correct_value
                    "user_answer": user_answers,  # User's choices
                    "breakdown": breakdown,  # Statement-by-statement comparison
                    "scoring_mode": q.get("scoring_mode", "partial"),
                }

                results.append(result)

            elif q_type == "essay":
                # Essay result
                essay_answer = user_answer_data.get("essay_answer", "")
                media_attachments = user_answer_data.get("media_attachments", [])
                essay_grade = essay_grades_map.get(question_id)

                result = {
                    "question_id": question_id,
                    "question_text": q["question_text"],
                    "question_type": "essay",
                    "your_answer": essay_answer,
                    "media_attachments": media_attachments,  # Include media files
                    "max_points": q.get("max_points", 1),
                    "grading_rubric": q.get("grading_rubric"),
                }

                if essay_grade:
                    # Graded
                    result.update(
                        {
                            "grading_status": "graded",
                            "points_awarded": essay_grade.get("points_awarded"),
                            "feedback": essay_grade.get("feedback"),
                            "graded_by": essay_grade.get("graded_by"),
                            "graded_at": essay_grade.get("graded_at"),
                        }
                    )
                else:
                    # Not graded yet
                    result.update(
                        {
                            "grading_status": "pending",
                            "points_awarded": None,
                            "feedback": None,
                        }
                    )

                results.append(result)

        # ========== NEW: Check show_answers_timing setting ==========
        show_answers_timing = test_doc.get("show_answers_timing", "immediate")
        deadline = test_doc.get("deadline")
        should_hide_answers = False

        if show_answers_timing == "after_deadline" and deadline:
            # Make deadline timezone-aware if needed
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)

            current_time = datetime.now(timezone.utc)

            # Hide answers if deadline not passed yet
            if current_time < deadline:
                should_hide_answers = True
                logger.info(
                    f"   🔒 Hiding detailed answers until deadline: {deadline.isoformat()}"
                )

        # Get grading status
        grading_status = submission.get("grading_status", "auto_graded")

        # Get audio sections for listening tests (for result replay)
        audio_sections = test_doc.get("audio_sections", [])
        formatted_audio_sections = []
        if audio_sections:
            for section in audio_sections:
                formatted_audio_sections.append(
                    {
                        "section_number": section.get("section_number"),
                        "section_title": section.get("section_title"),
                        "audio_url": section.get("audio_url"),
                        "duration_seconds": section.get("duration_seconds"),
                        # Include transcript in results so user can review
                        "transcript": section.get("transcript"),
                    }
                )

        # ========== Re-compute scores from results (handles old submissions with wrong stored scores) ==========
        is_diagnostic_test = submission.get("is_diagnostic_test", False)
        if grading_status == "auto_graded" and not is_diagnostic_test:
            recomputed_mcq_correct = sum(
                1
                for r in results
                if r.get("question_type") == "mcq" and r.get("is_correct") is True
            )
            recomputed_mcq_score = sum(
                r.get("points_awarded", 0)
                for r in results
                if r.get("question_type") not in ("essay",)
                and r.get("is_correct") is not None
            )
            # Only override if stored value looks wrong (0 but re-computed says > 0)
            stored_correct = submission.get("correct_answers", 0) or 0
            if stored_correct == 0 and recomputed_mcq_correct > 0:
                submission["correct_answers"] = recomputed_mcq_correct
                submission["mcq_correct_count"] = recomputed_mcq_correct
                submission["mcq_score"] = recomputed_mcq_score
                total_max = sum(
                    q.get("max_points", 1)
                    for q in test_doc["questions"]
                    if q.get("question_type") != "essay"
                )
                if total_max > 0:
                    submission["score_percentage"] = round(
                        recomputed_mcq_score / total_max * 100, 1
                    )
                    submission["score"] = round(
                        recomputed_mcq_score / total_max * 10, 1
                    )

        # Build response based on show_answers_timing
        if not should_hide_answers:
            # Full response - show everything
            response = {
                "submission_id": submission_id,
                "test_title": test_doc["title"],
                "test_category": test_doc.get("test_category", "academic"),
                "is_diagnostic_test": submission.get("is_diagnostic_test", False),
                "has_ai_evaluation": submission.get("has_ai_evaluation", True),
                "grading_status": grading_status,  # NEW
                "score": submission.get("score"),  # None if pending grading
                "score_percentage": submission.get(
                    "score_percentage"
                ),  # None if pending
                "mcq_score": submission.get("mcq_score"),  # NEW: Separate MCQ score
                "mcq_correct_count": submission.get("mcq_correct_count"),  # NEW
                "essay_score": submission.get(
                    "essay_score"
                ),  # NEW: Separate essay score
                "total_questions": submission["total_questions"],
                "correct_answers": submission.get("correct_answers"),  # MCQ only
                "time_taken_seconds": submission.get("time_taken_seconds", 0),
                "attempt_number": submission.get("attempt_number", 1),
                "is_passed": submission.get("is_passed", False),
                "submitted_at": submission["submitted_at"].isoformat(),
                "results": results,
                "audio_sections": formatted_audio_sections,  # Include audio for replay
            }

            # Add message if pending grading
            if grading_status == "pending_grading":
                response["message"] = (
                    "Bài thi chứa câu hỏi tự luận và đang chờ được chấm điểm."
                )

            # Add message if diagnostic test without AI evaluation
            if submission.get("is_diagnostic_test") and not submission.get(
                "has_ai_evaluation"
            ):
                response["message"] = (
                    "Câu trả lời của bạn đã được lưu nhưng chưa có đánh giá AI do không đủ điểm."
                )
        else:
            # Limited response - only basic info, NO detailed results
            response = {
                "submission_id": submission_id,
                "test_title": test_doc["title"],
                "grading_status": grading_status,
                "score": submission.get("score"),
                "score_percentage": submission.get("score_percentage"),
                "mcq_score": submission.get("mcq_score"),  # NEW
                "essay_score": submission.get("essay_score"),  # NEW
                "total_questions": submission["total_questions"],
                "correct_answers": submission.get(
                    "correct_answers"
                ),  # Still show count
                "is_passed": submission.get("is_passed", False),
                "submitted_at": submission["submitted_at"].isoformat(),
                "results_hidden_until_deadline": deadline.isoformat(),
                "message": "Detailed answers and explanations will be revealed after the deadline",
            }

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get submission detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Phase 2: HTTP Fallback Endpoints for Real-time Progress ==========


class SaveProgressRequest(BaseModel):
    """Request model for saving progress (HTTP fallback)"""

    session_id: str = Field(..., description="Session ID from /start endpoint")
    answers: dict = Field(
        ..., description="Current answers dict (question_id -> answer_key)"
    )
    time_remaining_seconds: Optional[int] = Field(
        None, description="Time remaining in seconds"
    )


class ProgressResponse(BaseModel):
    """Response model for progress retrieval"""

    session_id: str
    current_answers: dict
    time_remaining_seconds: Optional[int]
    started_at: str
    last_saved_at: str
    is_completed: bool


@router.post(
    "/{test_id}/progress/save", response_model=dict, tags=["Phase 2 - Auto-save"]
)
async def save_test_progress(
    test_id: str,
    request: SaveProgressRequest,
    user_info: dict = Depends(require_auth),
):
    """
    HTTP fallback for saving test progress (for clients without WebSocket)
    Saves current answers and time remaining to database
    """
    try:
        user_id = user_info["uid"]
        # db already initialized

        # Verify test exists
        test_doc = db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Verify session exists and belongs to user
        session = db["test_progress"].find_one({"session_id": request.session_id})

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session["user_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Session does not belong to user"
            )

        if str(session["test_id"]) != test_id:
            raise HTTPException(
                status_code=400, detail="Session does not belong to this test"
            )

        if session.get("is_completed"):
            raise HTTPException(status_code=409, detail="Session already completed")

        # Update progress in database
        update_data = {
            "current_answers": request.answers,
            "last_saved_at": datetime.utcnow(),
        }

        if request.time_remaining_seconds is not None:
            update_data["time_remaining_seconds"] = request.time_remaining_seconds

        result = db["test_progress"].update_one(
            {"session_id": request.session_id}, {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to save progress")

        logger.info(
            f"💾 Saved progress for session {request.session_id}: "
            f"{len(request.answers)} answers"
        )

        return {
            "success": True,
            "session_id": request.session_id,
            "saved_at": datetime.utcnow().isoformat(),
            "answers_count": len(request.answers),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to save progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{test_id}/progress", response_model=ProgressResponse, tags=["Phase 2 - Auto-save"]
)
async def get_test_progress(
    test_id: str,
    session_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Get current test progress (HTTP fallback)
    Useful for resuming tests after reconnection or page refresh
    """
    try:
        user_id = user_info["uid"]
        # db already initialized

        # Verify test exists
        test_doc = db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Get session progress
        session = db["test_progress"].find_one({"session_id": session_id})

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session["user_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Session does not belong to user"
            )

        if str(session["test_id"]) != test_id:
            raise HTTPException(
                status_code=400, detail="Session does not belong to this test"
            )

        return ProgressResponse(
            session_id=session["session_id"],
            current_answers=session.get("current_answers", {}),
            time_remaining_seconds=session.get("time_remaining_seconds"),
            started_at=session["started_at"].isoformat(),
            last_saved_at=session.get(
                "last_saved_at", session["started_at"]
            ).isoformat(),
            is_completed=session.get("is_completed", False),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{test_id}/resume", response_model=dict, tags=["Phase 2 - Auto-save"])
async def resume_test_session(
    test_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    Resume an incomplete test session
    Returns the most recent session if one exists
    """
    try:
        user_id = user_info["uid"]
        # db already initialized

        # Verify test exists
        test_doc = db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Find most recent incomplete session for this user and test
        session = db["test_progress"].find_one(
            {"user_id": user_id, "test_id": ObjectId(test_id), "is_completed": False},
            sort=[("started_at", -1)],
        )

        if not session:
            raise HTTPException(
                status_code=404,
                detail="No incomplete session found. Please start a new test.",
            )

        # Calculate elapsed time
        elapsed_seconds = int(
            (datetime.utcnow() - session["started_at"]).total_seconds()
        )
        time_limit_seconds = test_doc["time_limit_minutes"] * 60
        time_remaining = max(0, time_limit_seconds - elapsed_seconds)

        # If time ran out, mark session as completed and return error
        if time_remaining == 0:
            db["test_progress"].update_one(
                {"_id": session["_id"]}, {"$set": {"is_completed": True}}
            )
            raise HTTPException(
                status_code=410,
                detail="Session expired due to time limit. Please start a new test.",
            )

        # Update time remaining in database
        db["test_progress"].update_one(
            {"_id": session["_id"]},
            {"$set": {"time_remaining_seconds": time_remaining}},
        )

        return {
            "session_id": session["session_id"],
            "current_answers": session.get("current_answers", {}),
            "time_limit_seconds": time_limit_seconds,
            "time_remaining_seconds": time_remaining,
            "is_completed": False,
            "started_at": session["started_at"].isoformat(),
            "last_saved_at": session.get(
                "last_saved_at", session["started_at"]
            ).isoformat(),
            "message": "Session resumed successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to resume session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Phase 4: Essay Grading Interface ==========


class GradeEssayRequest(BaseModel):
    """Request model for grading a single essay question"""

    question_id: str = Field(..., description="ID of the essay question to grade")
    points_awarded: float = Field(
        ..., ge=0, description="Points awarded (0 to max_points)"
    )
    feedback: Optional[str] = Field(
        default=None, max_length=5000, description="Grader's feedback"
    )


class GradeAllEssaysRequest(BaseModel):
    """Request model for grading all essay questions at once"""

    grades: list[GradeEssayRequest] = Field(
        ..., description="List of grades for all essay questions"
    )


@router.get("/{test_id}/participants", response_model=dict, tags=["Phase 3 - Editing"])
async def get_test_participants(
    test_id: str,
    user_info: dict = Depends(require_auth),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query(
        "latest", regex="^(latest|highest_score|lowest_score|most_attempts)$"
    ),
):
    """
    Get list of all participants for a test (OWNER ONLY)

    Returns detailed information about each participant:
    - User ID, email, display name
    - Number of attempts
    - Best score
    - Latest submission date
    - Total correct answers
    - Average time taken

    **Access:** Only test owner can view participants

    **Sort options:**
    - latest: Most recent participants first
    - highest_score: Best scores first
    - lowest_score: Lowest scores first
    - most_attempts: Most attempts first
    """
    try:
        user_id = user_info["uid"]
        # db already initialized

        # Verify test exists
        test_doc = db["online_tests"].find_one({"_id": ObjectId(test_id)})
        if not test_doc:
            raise HTTPException(status_code=404, detail="Test not found")

        # Check ownership
        if test_doc.get("creator_id") != user_id:
            raise HTTPException(
                status_code=403, detail="Only test owner can view participants"
            )

        # Get all unique participants who have started the test at least once
        progress_collection = db["test_progress"]
        submissions_collection = db["test_submissions"]
        users_collection = db["users"]

        # Get unique user IDs from test_progress (anyone who started)
        participant_ids = progress_collection.distinct("user_id", {"test_id": test_id})

        if not participant_ids:
            return {
                "test_id": test_id,
                "test_title": test_doc.get("title", "Untitled"),
                "total_participants": 0,
                "participants": [],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": 0,
                    "total_pages": 0,
                    "has_next": False,
                    "has_prev": False,
                },
            }

        # Build participant data
        participants_data = []

        for participant_id in participant_ids:
            # Get user info
            user_doc = users_collection.find_one({"firebase_uid": participant_id})
            if not user_doc:
                continue  # Skip if user not found

            # Get all submissions for this participant
            submissions = list(
                submissions_collection.find(
                    {"test_id": test_id, "user_id": participant_id}
                ).sort("submitted_at", -1)
            )

            # Calculate statistics
            num_attempts = len(submissions)
            best_score = 0
            total_correct = 0
            total_time = 0
            latest_submission = None

            if submissions:
                best_score = max(sub.get("score", 0) for sub in submissions)
                total_correct = sum(
                    sub.get("correct_answers", 0) for sub in submissions
                )
                total_time = sum(
                    sub.get("time_taken_seconds", 0) for sub in submissions
                )
                latest_submission = submissions[0].get("submitted_at")

            avg_time = total_time / num_attempts if num_attempts > 0 else 0

            participants_data.append(
                {
                    "user_id": participant_id,
                    "email": user_doc.get("email", "N/A"),
                    "display_name": user_doc.get("display_name", "Anonymous"),
                    "photo_url": user_doc.get("photo_url"),
                    "num_attempts": num_attempts,
                    "best_score": best_score,
                    "total_correct_answers": total_correct,
                    "avg_time_seconds": int(avg_time),
                    "latest_submission_at": (
                        latest_submission.isoformat() if latest_submission else None
                    ),
                    "has_submitted": num_attempts > 0,
                }
            )

        # Sort based on sort_by parameter
        if sort_by == "latest":
            participants_data.sort(
                key=lambda x: x["latest_submission_at"] or "", reverse=True
            )
        elif sort_by == "highest_score":
            participants_data.sort(key=lambda x: x["best_score"], reverse=True)
        elif sort_by == "lowest_score":
            participants_data.sort(key=lambda x: x["best_score"])
        elif sort_by == "most_attempts":
            participants_data.sort(key=lambda x: x["num_attempts"], reverse=True)

        # Pagination
        total_items = len(participants_data)
        total_pages = (total_items + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        paginated_participants = participants_data[start_idx:end_idx]

        logger.info(
            f"📊 Get participants for test {test_id}: "
            f"owner={user_id}, total={total_items}, page={page}/{total_pages}"
        )

        return {
            "test_id": test_id,
            "test_title": test_doc.get("title", "Untitled"),
            "total_participants": total_items,
            "participants": paginated_participants,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get participants: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Listening Test Audio Management ==========


@router.delete(
    "/{test_id}/audio-sections/{section_number}",
    summary="Delete audio from listening test section",
    tags=["Listening Tests"],
)
async def delete_audio_section(
    test_id: str,
    section_number: int,
    user_info: dict = Depends(require_auth),
):
    """
    **Delete audio from listening test section (Owner only)**

    Removes audio_url and audio_file_id from the audio section while keeping the transcript and script.
    The audio file is archived in the library.

    **Authentication:** Required (Owner only)

    **Path Parameters:**
    - `test_id`: Test ID
    - `section_number`: Audio section number (1-based)

    **Returns:**
    - 200: Audio deleted successfully
    - 403: Not test owner
    - 404: Test or section not found
    """
    try:
        from src.database.db_manager import DBManager
        from src.services.library_manager import LibraryManager
        from src.services.r2_storage_service import R2StorageService

        user_id = user_info["uid"]
        db_manager = DBManager()
        db = db_manager.db

        # 1. Get test and verify ownership
        test = db.online_tests.find_one({"_id": ObjectId(test_id)})
        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

        if test.get("creator_id") != user_id:
            raise HTTPException(
                status_code=403, detail="Only test owner can delete audio"
            )

        # 2. Verify test is listening type
        if test.get("test_type") != "listening":
            raise HTTPException(status_code=400, detail="Test is not a listening test")

        # 3. Find audio section
        audio_sections = test.get("audio_sections", [])
        section_index = section_number - 1

        if section_index < 0 or section_index >= len(audio_sections):
            raise HTTPException(
                status_code=404,
                detail=f"Audio section {section_number} not found (test has {len(audio_sections)} sections)",
            )

        audio_section = audio_sections[section_index]
        audio_file_id = audio_section.get("audio_file_id")

        # 4. Archive audio file in library if exists
        # Note: Archive functionality not implemented in LibraryManager yet
        # Old audio file will remain in library but not linked to test
        if audio_file_id:
            logger.info(
                f"📦 Old audio file {audio_file_id} will be preserved in library"
            )

        # 5. Remove audio_url and audio_file_id from section
        audio_section.pop("audio_url", None)
        audio_section.pop("audio_file_id", None)
        audio_section["has_audio"] = False

        # Update database
        db.online_tests.update_one(
            {"_id": ObjectId(test_id)},
            {"$set": {f"audio_sections.{section_index}": audio_section}},
        )

        logger.info(
            f"✅ User {user_id} deleted audio from test {test_id} section {section_number}"
        )

        return {
            "success": True,
            "message": f"Audio removed from section {section_number}",
            "section": {
                "section_number": section_number,
                "section_title": audio_section.get("section_title"),
                "has_audio": False,
                "transcript_preserved": True,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete audio section: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/{test_id}/audio-sections/{section_number}/audio",
    summary="Replace audio in listening test section",
    tags=["Listening Tests"],
)
async def replace_audio_section(
    test_id: str,
    section_number: int,
    audio_file: UploadFile = File(..., description="Audio file (MP3, WAV, M4A, OGG)"),
    user_info: dict = Depends(require_auth),
):
    """
    **Replace audio in listening test section (Owner only)**

    Uploads a new audio file and updates the audio_url and audio_file_id.
    The old audio file is archived in the library.

    **Authentication:** Required (Owner only)

    **Path Parameters:**
    - `test_id`: Test ID
    - `section_number`: Audio section number (1-based)

    **Request:**
    - Multipart form-data with audio file

    **Supported Formats:**
    - MP3 (recommended)
    - WAV
    - M4A
    - OGG

    **Max Size:** 50MB

    **Returns:**
    - 200: Audio replaced successfully
    - 400: Invalid file format or size
    - 403: Not test owner
    - 404: Test or section not found
    """
    try:
        from src.database.db_manager import DBManager
        from src.services.library_manager import LibraryManager
        from src.services.r2_storage_service import R2StorageService
        import mimetypes

        user_id = user_info["uid"]
        db_manager = DBManager()
        db = db_manager.db

        # 1. Get test and verify ownership
        test = db.online_tests.find_one({"_id": ObjectId(test_id)})
        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

        if test.get("creator_id") != user_id:
            raise HTTPException(
                status_code=403, detail="Only test owner can replace audio"
            )

        # 2. Verify test is listening type
        if test.get("test_type") != "listening":
            raise HTTPException(status_code=400, detail="Test is not a listening test")

        # 3. Find audio section
        audio_sections = test.get("audio_sections", [])
        section_index = section_number - 1

        if section_index < 0 or section_index >= len(audio_sections):
            raise HTTPException(
                status_code=404,
                detail=f"Audio section {section_number} not found (test has {len(audio_sections)} sections)",
            )

        audio_section = audio_sections[section_index]
        old_audio_file_id = audio_section.get("audio_file_id")

        # 4. Validate audio file
        if not audio_file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # Check file extension
        allowed_extensions = {".mp3", ".wav", ".m4a", ".ogg", ".webm"}
        file_ext = os.path.splitext(audio_file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid audio format. Allowed: {', '.join(allowed_extensions)}",
            )

        # Read file content
        file_content = await audio_file.read()
        file_size = len(file_content)

        # Check file size (50MB max)
        MAX_SIZE = 50 * 1024 * 1024
        if file_size > MAX_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large (max 50MB, got {file_size} bytes)",
            )

        # 5. Archive old audio file if exists
        # Note: Archive functionality not implemented in LibraryManager yet
        # Old audio file will remain in library but not linked to test
        if old_audio_file_id:
            logger.info(
                f"📦 Old audio file {old_audio_file_id} will be preserved in library"
            )

        # 6. Upload new audio to R2
        r2_service = R2StorageService()
        library_manager = LibraryManager(db, s3_client=r2_service.s3_client)

        # Generate R2 key
        file_id = str(uuid.uuid4())
        r2_key = f"listening-tests/{user_id}/{test_id}/section_{section_number}_{file_id}{file_ext}"

        # Detect content type
        content_type = (
            audio_file.content_type
            or mimetypes.guess_type(audio_file.filename)[0]
            or "audio/mpeg"
        )

        # Upload to R2
        await r2_service.upload_file(file_content, r2_key, content_type)
        audio_url = r2_service.get_public_url(r2_key)

        logger.info(f"☁️ Uploaded audio to R2: {r2_key}")

        # 7. Save to library
        library_file = library_manager.save_library_file(
            user_id=user_id,
            filename=audio_file.filename,
            file_type="audio",
            category="audio",
            r2_url=audio_url,
            r2_key=r2_key,
            file_size=file_size,
            mime_type=content_type,
            metadata={
                "test_id": test_id,
                "audio_section": section_number,
                "source_type": "user_upload_replacement",
                "audio_format": file_ext.lstrip("."),
            },
        )

        new_audio_file_id = str(library_file["_id"])

        # 8. Update audio section
        audio_section["audio_url"] = audio_url
        audio_section["audio_file_id"] = new_audio_file_id
        audio_section["has_audio"] = True
        audio_section["source_type"] = "user_upload"

        # Update database
        db.online_tests.update_one(
            {"_id": ObjectId(test_id)},
            {"$set": {f"audio_sections.{section_index}": audio_section}},
        )

        logger.info(
            f"✅ User {user_id} replaced audio in test {test_id} section {section_number}"
        )

        return {
            "success": True,
            "message": f"Audio replaced in section {section_number}",
            "audio": {
                "audio_url": audio_url,
                "audio_file_id": new_audio_file_id,
                "file_size_bytes": file_size,
                "format": file_ext.lstrip("."),
                "source_type": "user_upload",
            },
            "section": {
                "section_number": section_number,
                "section_title": audio_section.get("section_title"),
                "has_audio": True,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to replace audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== Phase 4: Question Media Upload ==========
