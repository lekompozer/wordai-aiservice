"""
Song Learning Subscription API Routes
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import require_auth
from src.models.song_subscription import (
    SUBSCRIPTION_PLANS,
    SubscriptionStatusResponse,
)
from src.services.song_subscription_service import get_song_subscription_service
from src.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(prefix="/api/v1/songs/subscription", tags=["Song Subscription"])


def get_db():
    """Get database connection"""
    db_manager = DBManager()
    return db_manager.db


@router.get("/plans")
async def get_subscription_plans():
    """
    Get all available subscription plans

    No authentication required - public endpoint
    """
    return {"plans": [plan.model_dump() for plan in SUBSCRIPTION_PLANS.values()]}


@router.get("/me", response_model=SubscriptionStatusResponse)
async def get_my_subscription(
    current_user: Dict[str, Any] = Depends(require_auth),
    db=Depends(get_db),
):
    """
    Get current user's subscription status

    Returns:
    - is_premium: boolean
    - subscription: subscription details if active, else null
    """
    user_id = current_user["uid"]

    subscription_service = get_song_subscription_service(db)
    subscription = await subscription_service.get_subscription(user_id)

    if not subscription:
        return SubscriptionStatusResponse(is_premium=False, subscription=None)

    # Calculate days remaining
    days_remaining = (subscription["end_date"] - subscription["start_date"]).days

    subscription_info = {
        "plan_type": subscription["plan_type"],
        "status": subscription["status"],
        "start_date": subscription["start_date"].isoformat(),
        "end_date": subscription["end_date"].isoformat(),
        "days_remaining": days_remaining,
        "price_paid": subscription["price_paid"],
        "auto_renew": subscription.get("auto_renew", False),
    }

    return SubscriptionStatusResponse(is_premium=True, subscription=subscription_info)


@router.post("/cancel")
async def cancel_subscription(
    current_user: Dict[str, Any] = Depends(require_auth),
    db=Depends(get_db),
):
    """
    Cancel subscription

    User keeps access until end_date, but won't auto-renew
    """
    user_id = current_user["uid"]

    subscription_service = get_song_subscription_service(db)
    subscription = await subscription_service.cancel_subscription(user_id)

    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")

    return {
        "message": f"Subscription cancelled. You still have access until {subscription['end_date'].strftime('%Y-%m-%d')}",
        "subscription": {
            "status": "cancelled",
            "end_date": subscription["end_date"].isoformat(),
            "cancelled_at": subscription["cancelled_at"].isoformat(),
        },
    }
