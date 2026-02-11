"""
Song Learning Subscription Activation API
Handles subscription activation from payment service after successful payment
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from datetime import datetime, timedelta
import os

from src.database.db_manager import DBManager
from src.models.song_subscription import (
    SUBSCRIPTION_PLANS,
    ActivateSongSubscriptionRequest,
    ActivateSongSubscriptionResponse,
)
from src.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(prefix="/api/v1/songs/subscription", tags=["Song Subscription"])

# Service secret for inter-service authentication
SERVICE_SECRET = os.getenv(
    "API_SECRET_KEY", "wordai-payment-service-secret-2025-secure-key"
)


def get_db():
    """Get database connection"""
    db_manager = DBManager()
    return db_manager.db


def verify_service_secret(
    x_service_secret: str = Header(..., alias="X-Service-Secret")
):
    """Verify that request comes from payment service"""
    if x_service_secret != SERVICE_SECRET:
        logger.error(f"Invalid service secret in song activation request")
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


@router.post("/activate", response_model=ActivateSongSubscriptionResponse)
async def activate_song_subscription(
    request: ActivateSongSubscriptionRequest,
    _: bool = Depends(verify_service_secret),
    db=Depends(get_db),
):
    """
    Activate song learning subscription after successful payment

    Called by payment service (Node.js) after receiving IPN from SePay.
    This endpoint:
    1. Creates/extends user's song learning subscription
    2. Sets expiration date based on duration_months
    3. Records payment information

    **Authentication:** Requires X-Service-Secret header
    """
    try:
        logger.info(f"Activating song subscription for user: {request.user_id}")
        logger.info(
            f"Plan: {request.plan_id}, Duration: {request.duration_months} months"
        )

        # Validate plan exists
        if request.plan_id not in SUBSCRIPTION_PLANS:
            raise HTTPException(
                status_code=400, detail=f"Invalid plan_id: {request.plan_id}"
            )

        plan = SUBSCRIPTION_PLANS[request.plan_id]

        # Calculate subscription dates
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=30 * request.duration_months)

        # Check for existing subscription
        subscription_col = db["user_song_subscription"]
        existing_sub = subscription_col.find_one({"user_id": request.user_id})

        if existing_sub and existing_sub.get("status") == "active":
            # Extend existing subscription
            current_end = existing_sub["end_date"]
            if current_end > start_date:
                # Still active, extend from current end date
                start_date = current_end
                end_date = start_date + timedelta(days=30 * request.duration_months)
                logger.info(f"Extending subscription from {current_end} to {end_date}")

        # Create or update subscription
        subscription_doc = {
            "user_id": request.user_id,
            "plan_type": request.plan_id,
            "status": "active",
            "start_date": start_date,
            "end_date": end_date,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "price_paid": request.amount,
            "payment_method": request.payment_method,
            "payment_id": request.payment_id,
            "order_invoice_number": request.order_invoice_number,
            "auto_renew": False,
            "source": "web",
        }

        result = subscription_col.update_one(
            {"user_id": request.user_id}, {"$set": subscription_doc}, upsert=True
        )

        subscription_id = (
            str(result.upserted_id) if result.upserted_id else request.user_id
        )

        logger.info(
            f"Song subscription activated: {subscription_id}, expires: {end_date}"
        )

        return ActivateSongSubscriptionResponse(
            subscription_id=subscription_id,
            expires_at=end_date,
            message=f"Song learning subscription activated successfully until {end_date.strftime('%Y-%m-%d')}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating song subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Activation failed: {str(e)}")
