"""
Feedback & Review API Routes
Allow users to submit reviews and get rewarded for social sharing
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException

from src.middleware.firebase_auth import get_current_user
from src.database.db_manager import DBManager
from src.models.feedback_models import (
    SubmitReviewRequest,
    SubmitReviewResponse,
    ShareStatusResponse,
)
from src.services.points_service import get_points_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/feedback", tags=["Feedback & Reviews"])

# Constants
SHARE_REWARD_POINTS = 5  # Points awarded for sharing


def _get_today_date_string() -> str:
    """Get today's date in YYYY-MM-DD format (Vietnam timezone)"""
    from datetime import timezone, timedelta

    # Vietnam is UTC+7
    vietnam_tz = timezone(timedelta(hours=7))
    return datetime.now(vietnam_tz).strftime("%Y-%m-%d")


def _check_can_share_today(user_id: str, db_manager: DBManager) -> Dict[str, Any]:
    """
    Check if user can share today for points

    Returns:
        Dict with: can_share, last_share_date, next_share_date
    """
    today = _get_today_date_string()

    # Find user's last share
    last_share = db_manager.db.user_feedback.find_one(
        {"user_id": user_id, "shared_platform": {"$ne": None}},
        sort=[("shared_at", -1)],
    )

    if not last_share:
        return {
            "can_share": True,
            "last_share_date": None,
            "next_share_date": None,
        }

    last_share_date = last_share.get("share_date")  # YYYY-MM-DD format

    if last_share_date == today:
        # Already shared today
        tomorrow = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
        return {
            "can_share": False,
            "last_share_date": last_share_date,
            "next_share_date": tomorrow,
        }
    else:
        # Can share today
        return {
            "can_share": True,
            "last_share_date": last_share_date,
            "next_share_date": None,
        }


@router.post(
    "/review",
    response_model=SubmitReviewResponse,
    summary="Submit Review & Share for Reward",
    description="""
    Submit a review/rating and optionally share on social media.

    **Reward System:**
    - Share on social media → Get 5 points
    - Limit: 1 share per day
    - Rating is required (1-5 stars)
    - Feedback text is optional (max 500 chars)

    **Share Platforms:**
    - facebook: Share on Facebook
    - twitter: Tweet on X/Twitter
    - linkedin: Share on LinkedIn
    - copy: Copy link to share anywhere
    """,
)
async def submit_review(
    request: SubmitReviewRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Submit review and get reward for sharing"""
    try:
        user_id = current_user["uid"]
        user_email = current_user.get("email", "unknown")

        logger.info(f"📝 Review from user {user_email} (rating: {request.rating})")

        db_manager = DBManager()
        points_service = get_points_service()

        # Check if user can share today for points
        share_check = _check_can_share_today(user_id, db_manager)
        can_award_points = share_check["can_share"] and request.share_platform

        # Prepare review document
        review_doc = {
            "user_id": user_id,
            "user_email": user_email,
            "rating": request.rating,
            "feedback_text": request.feedback_text,
            "shared_platform": request.share_platform,
            "created_at": datetime.utcnow(),
            "share_date": _get_today_date_string() if request.share_platform else None,
            "shared_at": datetime.utcnow() if request.share_platform else None,
            "points_awarded": SHARE_REWARD_POINTS if can_award_points else 0,
        }

        # Save to database
        result = db_manager.db.user_feedback.insert_one(review_doc)
        review_id = str(result.inserted_id)

        logger.info(f"✅ Review saved: {review_id}")

        # Award points if user shared and eligible
        points_awarded = 0
        if can_award_points:
            try:
                await points_service.add_points(
                    user_id=user_id,
                    amount=SHARE_REWARD_POINTS,
                    service="review_share",
                    resource_id=review_id,
                    description=f"Shared review on {request.share_platform}",
                )
                points_awarded = SHARE_REWARD_POINTS
                logger.info(
                    f"🎁 Awarded {SHARE_REWARD_POINTS} points to {user_email} for sharing on {request.share_platform}"
                )
            except Exception as points_error:
                logger.error(f"❌ Failed to award points: {points_error}")
                # Don't fail the review submission if points fail

        # Build response
        response = SubmitReviewResponse(
            success=True,
            message=(
                f"Cảm ơn bạn đã đánh giá! Bạn đã nhận {points_awarded} điểm."
                if points_awarded > 0
                else "Cảm ơn bạn đã đánh giá!"
            ),
            points_awarded=points_awarded,
            can_share_again_at=share_check.get("next_share_date"),
            review_id=review_id,
        )

        if not can_award_points and request.share_platform:
            if not share_check["can_share"]:
                response.message = (
                    "Cảm ơn bạn đã đánh giá! "
                    f"Bạn đã chia sẻ hôm nay. Quay lại ngày mai để nhận thêm điểm!"
                )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to submit review: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to submit review: {str(e)}")


@router.get(
    "/share-status",
    response_model=ShareStatusResponse,
    summary="Check Share Status",
    description="""
    Check if user can share today for points reward.

    Returns information about:
    - Whether user can share today
    - Last share date
    - Next available share date
    - Total shares made
    """,
)
async def get_share_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Check if user can share today for points"""
    try:
        user_id = current_user["uid"]

        db_manager = DBManager()
        share_check = _check_can_share_today(user_id, db_manager)

        # Count total shares
        total_shares = db_manager.db.user_feedback.count_documents(
            {"user_id": user_id, "shared_platform": {"$ne": None}}
        )

        return ShareStatusResponse(
            can_share_today=share_check["can_share"],
            last_share_date=share_check["last_share_date"],
            next_share_available=share_check["next_share_date"],
            total_shares=total_shares,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get share status: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get share status: {str(e)}")
