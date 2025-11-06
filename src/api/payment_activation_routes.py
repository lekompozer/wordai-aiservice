"""
Payment Activation API Routes
Handles subscription activation from payment service after successful payment
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta
import logging
import os

from src.services.subscription_service import get_subscription_service

router = APIRouter(prefix="/api/v1/subscriptions", tags=["Payment Activation"])
logger = logging.getLogger(__name__)

# Service secret for inter-service authentication
SERVICE_SECRET = os.getenv(
    "API_SECRET_KEY", "wordai-payment-service-secret-2025-secure-key"
)


class ActivateSubscriptionRequest(BaseModel):
    """Request from payment service to activate subscription after payment"""

    user_id: str = Field(..., description="Firebase UID")
    plan: str = Field(..., description="premium, pro, or vip")
    duration_months: int = Field(..., description="Subscription duration in months")
    payment_id: str = Field(..., description="MongoDB payment _id")
    order_invoice_number: str = Field(..., description="Unique order invoice number")
    payment_method: str = Field(..., description="Payment method used")
    amount: int = Field(..., description="Amount paid in VND")


class ActivateSubscriptionResponse(BaseModel):
    """Response after activating subscription"""

    subscription_id: str = Field(..., description="MongoDB subscription _id")
    expires_at: datetime = Field(..., description="Subscription expiration date")
    points_granted: int = Field(..., description="Points granted for this plan")
    message: str = Field(default="Subscription activated successfully")


def verify_service_secret(
    x_service_secret: str = Header(..., alias="X-Service-Secret")
):
    """Verify that request comes from payment service"""
    if x_service_secret != SERVICE_SECRET:
        logger.error(f"Invalid service secret in activation request")
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


@router.post("/activate", response_model=ActivateSubscriptionResponse)
async def activate_subscription(
    request: ActivateSubscriptionRequest, _: bool = Depends(verify_service_secret)
):
    """
    Activate subscription after successful payment

    Called by payment service (Node.js) after receiving IPN from SePay.
    This endpoint:
    1. Upgrades user's subscription to paid plan
    2. ADDS points to current balance (not replace)
    3. Sets expiration date

    **Authentication:** Requires X-Service-Secret header
    """
    try:
        logger.info(
            f"🎉 Activating subscription for user {request.user_id}, plan: {request.plan}, duration: {request.duration_months} months"
        )

        subscription_service = get_subscription_service()

        # Calculate expiration date
        expires_at = datetime.utcnow() + timedelta(days=30 * request.duration_months)

        # Determine points to grant based on plan and duration
        points_map = {
            "premium": {3: 300, 12: 1500},
            "pro": {3: 800, 12: 3500},
            "vip": {3: 2000, 12: 9000},
        }

        points_to_grant = points_map.get(request.plan, {}).get(
            request.duration_months, 0
        )

        if points_to_grant == 0:
            logger.warning(
                f"No points mapping for plan={request.plan}, duration={request.duration_months}"
            )
            # Use fallback calculation
            base_points = {"premium": 100, "pro": 267, "vip": 667}
            points_to_grant = (
                base_points.get(request.plan, 100) * request.duration_months
            )

        # Get or create subscription
        subscription = await subscription_service.get_or_create_subscription(
            request.user_id
        )

        # Get current points balance
        current_points = subscription.get("points_remaining", 0)
        current_total = subscription.get("points_total", 0)

        # Calculate new points (ADD to existing)
        new_points_remaining = current_points + points_to_grant
        new_points_total = current_total + points_to_grant

        logger.info(
            f"📊 Points calculation: current={current_points}, adding={points_to_grant}, new_total={new_points_remaining}"
        )

        # Update plan limits based on tier
        storage_limit_mb = 5120  # Default PREMIUM
        max_files = 500

        if request.plan == "premium":
            storage_limit_mb = 5120  # 5GB
            max_files = 500
        elif request.plan == "pro":
            storage_limit_mb = 10240  # 10GB
            max_files = 1000
        elif request.plan == "vip":
            storage_limit_mb = 20480  # 20GB
            max_files = 2000

        # Update subscription document
        update_result = subscription_service.subscriptions.update_one(
            {"user_id": request.user_id},
            {
                "$set": {
                    "plan": request.plan,
                    "is_active": True,
                    "started_at": datetime.utcnow(),
                    "expires_at": expires_at,
                    "auto_renew": False,
                    "cancelled_at": None,
                    "payment_id": request.payment_id,
                    "order_invoice_number": request.order_invoice_number,
                    "payment_method": request.payment_method,
                    "amount_paid": request.amount,
                    "points_total": new_points_total,  # ✅ ADD points
                    "points_remaining": new_points_remaining,  # ✅ ADD points
                    "storage_limit_mb": storage_limit_mb,
                    "upload_files_limit": max_files,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        if update_result.modified_count == 0:
            logger.error(f"❌ Failed to update subscription for user {request.user_id}")
            raise HTTPException(status_code=500, detail="Failed to update subscription")

        # Also update user document
        subscription_service.users.update_one(
            {"uid": request.user_id},
            {
                "$set": {
                    "current_plan": request.plan,
                    "subscription_expires_at": expires_at,
                    "points_remaining": new_points_remaining,  # ✅ ADD points
                    "storage_limit_mb": storage_limit_mb,
                    "plan_updated_at": datetime.utcnow(),
                }
            },
        )

        logger.info(
            f"✅ Subscription updated for user {request.user_id}: {request.plan} until {expires_at}"
        )
        logger.info(
            f"✅ Points updated: {current_points} → {new_points_remaining} (+{points_to_grant})"
        )

        # Get updated subscription for response
        updated_subscription = subscription_service.subscriptions.find_one(
            {"user_id": request.user_id}
        )

        return ActivateSubscriptionResponse(
            subscription_id=str(updated_subscription["_id"]),
            expires_at=expires_at,
            points_granted=points_to_grant,
            message=f"Subscription activated: {request.plan} for {request.duration_months} months. Points: {current_points} + {points_to_grant} = {new_points_remaining}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error activating subscription: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to activate subscription: {str(e)}"
        )


@router.get("/activation/health")
async def activation_health():
    """Health check for activation endpoint"""
    return {
        "status": "healthy",
        "endpoint": "subscription activation",
        "service": "python-backend",
    }
