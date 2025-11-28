"""
Payment Activation API Routes
Handles subscription activation from payment service after successful payment
"""

from fastapi import APIRouter, HTTPException, Header, Depends, Request, Body
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta
import logging
import os

from src.services.subscription_service import get_subscription_service
from src.models.subscription import PLAN_CONFIGS

router = APIRouter(prefix="/api/v1/subscriptions", tags=["Payment Activation"])
points_router = APIRouter(prefix="/api/v1/points", tags=["Points Management"])
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

        # Get plan configuration from PLAN_CONFIGS
        plan_config = PLAN_CONFIGS.get(request.plan)
        if not plan_config:
            raise HTTPException(status_code=400, detail=f"Invalid plan: {request.plan}")

        # Calculate expiration date
        expires_at = datetime.utcnow() + timedelta(days=30 * request.duration_months)

        # Get points based on duration from PLAN_CONFIGS
        if request.duration_months == 3:
            points_to_grant = plan_config.points_3_months
        elif request.duration_months == 12:
            points_to_grant = plan_config.points_12_months
        else:
            # Fallback for other durations (should not happen)
            logger.warning(
                f"⚠️ Unexpected duration: {request.duration_months} months for plan {request.plan}"
            )
            # Use 3-month points as base
            points_to_grant = plan_config.points_3_months

        logger.info(
            f"📊 Plan: {request.plan}, Duration: {request.duration_months}mo → Points: {points_to_grant}"
        )

        # Get or create subscription
        subscription = await subscription_service.get_or_create_subscription(
            request.user_id
        )

        # Get current points balance (subscription is a Pydantic model)
        current_points = (
            subscription.points_remaining
            if hasattr(subscription, "points_remaining")
            else 0
        )
        current_total = (
            subscription.points_total if hasattr(subscription, "points_total") else 0
        )

        # Calculate new points (ADD to existing)
        new_points_remaining = current_points + points_to_grant
        new_points_total = current_total + points_to_grant

        # Get plan limits
        storage_limit_mb = plan_config.storage_mb
        upload_files_limit = plan_config.upload_files_limit
        documents_limit = plan_config.documents_limit
        daily_chat_limit = plan_config.daily_chat_limit

        logger.info(
            f"� Points: current={current_points} + grant={points_to_grant} = new={new_points_remaining}"
        )
        logger.info(
            f"📋 Limits: storage={storage_limit_mb}MB, files={upload_files_limit}, docs={documents_limit}, chat={daily_chat_limit}"
        )

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
                    "points_total": new_points_total,
                    "points_remaining": new_points_remaining,
                    "storage_limit_mb": storage_limit_mb,
                    "upload_files_limit": upload_files_limit,
                    "documents_limit": documents_limit,
                    "daily_chat_limit": daily_chat_limit,
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


@points_router.post("/add")
async def add_points(
    request: Request,
    user_id: str = Body(...),
    points: int = Body(...),
    payment_id: str = Body(...),
    order_invoice_number: str = Body(...),
    payment_method: str = Body(None),
    amount: int = Body(...),
    reason: str = Body("Points purchase via payment service"),
):
    """Add points to user account (called by payment service webhook)"""
    try:
        # Verify service secret
        service_secret = request.headers.get("X-Service-Secret")
        expected_secret = os.getenv("SERVICE_SECRET")

        if not service_secret or service_secret != expected_secret:
            logger.warning(
                "❌ Unauthorized points add request - invalid service secret"
            )
            raise HTTPException(status_code=401, detail="Unauthorized")

        logger.info(
            f"🎯 Adding {points} points for user {user_id} (payment: {payment_id})"
        )

        # Get user subscription
        subscription = subscription_service.subscriptions.find_one({"user_id": user_id})

        if not subscription:
            logger.error(f"❌ Subscription not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Subscription not found")

        current_points = subscription.get("points_remaining", 0)
        new_points_total = current_points + points

        # Update subscription with new points
        update_result = subscription_service.subscriptions.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "points_remaining": new_points_total,
                    "updated_at": datetime.utcnow(),
                },
                "$push": {
                    "payment_history": {
                        "payment_id": payment_id,
                        "order_invoice_number": order_invoice_number,
                        "payment_method": payment_method,
                        "amount_paid": amount,
                        "points_purchased": points,
                        "reason": reason,
                        "timestamp": datetime.utcnow(),
                    }
                },
            },
        )

        if update_result.modified_count == 0:
            logger.error(f"❌ Failed to update points for user {user_id}")
            raise HTTPException(status_code=500, detail="Failed to update points")

        # Also update user document
        subscription_service.users.update_one(
            {"uid": user_id},
            {
                "$set": {
                    "points_remaining": new_points_total,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        logger.info(
            f"✅ Points updated for user {user_id}: {current_points} → {new_points_total} (+{points})"
        )

        return {
            "success": True,
            "user_id": user_id,
            "points_added": points,
            "previous_balance": current_points,
            "new_balance": new_points_total,
            "payment_id": payment_id,
            "message": f"Successfully added {points} points. New balance: {new_points_total}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error adding points: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add points: {str(e)}")


@router.get("/activation/health")
async def activation_health():
    """Health check for activation endpoint"""
    return {
        "status": "healthy",
        "endpoint": "subscription activation",
        "service": "python-backend",
    }
