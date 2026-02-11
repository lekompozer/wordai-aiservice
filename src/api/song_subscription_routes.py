"""
Song Learning Subscription API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any
import httpx

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


# Payment routes - different prefix for frontend compatibility
payment_router = APIRouter(
    prefix="/api/v1/payments/song-learning", tags=["Song Payments"]
)


@payment_router.post("/checkout")
async def create_checkout(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_auth),
):
    """
    Create payment checkout session for song learning subscription

    Proxies request to payment service.

    Request body:
    {
        "plan_id": "monthly" | "6_months" | "yearly",
        "duration_months": 1 | 6 | 12,
        "amount": 29000 | 150000 | 250000
    }
    """
    user_id = current_user["uid"]

    try:
        # Get request body
        body = await request.json()

        # Validate plan_id
        plan_id = body.get("plan_id")
        if plan_id not in SUBSCRIPTION_PLANS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid plan_id. Must be one of: {list(SUBSCRIPTION_PLANS.keys())}",
            )

        # Get Firebase token from request headers
        auth_header = request.headers.get("Authorization", "")
        firebase_token = (
            auth_header.replace("Bearer ", "")
            if auth_header.startswith("Bearer ")
            else ""
        )

        if not firebase_token:
            raise HTTPException(status_code=401, detail="Missing Firebase token")

        # Forward request to payment service
        async with httpx.AsyncClient(timeout=30.0) as client:
            payment_response = await client.post(
                "http://payment-service:3000/api/payment/checkout",
                json=body,
                headers={
                    "Authorization": f"Bearer {firebase_token}",
                    "Content-Type": "application/json",
                },
            )

            if payment_response.status_code != 200:
                logger.error(
                    f"Payment service error: {payment_response.status_code} - {payment_response.text}"
                )
                raise HTTPException(
                    status_code=payment_response.status_code,
                    detail=f"Payment service error: {payment_response.text}",
                )

            return payment_response.json()

    except httpx.TimeoutException:
        logger.error("Payment service timeout")
        raise HTTPException(status_code=504, detail="Payment service timeout")
    except httpx.RequestError as e:
        logger.error(f"Payment service request error: {e}")
        raise HTTPException(status_code=503, detail="Payment service unavailable")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Checkout error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
