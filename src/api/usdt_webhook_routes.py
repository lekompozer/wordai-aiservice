"""
USDT Payment Webhook Routes

Webhook endpoints for external payment notifications and manual triggers
"""

from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel, Field

from src.services.usdt_verification_job import get_verification_job
from src.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(prefix="/api/v1/webhooks/usdt", tags=["USDT Payment Webhooks"])


class WebhookPayload(BaseModel):
    """Generic webhook payload"""

    event: str = Field(..., description="Event type")
    data: dict = Field(..., description="Event data")


class ManualVerificationRequest(BaseModel):
    """Request to manually trigger verification"""

    transaction_hash: str = Field(..., description="Transaction hash to verify")


# =========================================================================
# WEBHOOK ENDPOINTS
# =========================================================================


@router.post("/notify", include_in_schema=False)
async def payment_notification_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str = Header(..., alias="X-Webhook-Secret"),
):
    """
    Webhook endpoint for payment notifications

    Can be called by:
    - External blockchain monitoring services
    - BSC scan webhooks
    - Manual triggers

    Security: Requires X-Webhook-Secret header
    """
    try:
        import os

        # Verify webhook secret
        expected_secret = os.getenv("WEBHOOK_SECRET", "dev-webhook-secret-123")
        if x_webhook_secret != expected_secret:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")

        logger.info(f"📨 Webhook received: {payload.event}")

        # Handle different event types
        if payload.event == "transaction_confirmed":
            tx_hash = payload.data.get("transaction_hash")

            if not tx_hash:
                raise HTTPException(status_code=400, detail="Missing transaction_hash")

            # Trigger verification in background
            job = get_verification_job()
            if job:
                logger.info(f"🔄 Triggering verification for {tx_hash}")
                # Job will pick it up in next cycle

            return {
                "status": "accepted",
                "message": "Verification queued",
                "transaction_hash": tx_hash,
            }

        else:
            logger.warning(f"⚠️ Unknown webhook event: {payload.event}")
            return {
                "status": "ignored",
                "message": f"Unknown event type: {payload.event}",
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Webhook processing failed: {str(e)}"
        )


@router.post("/manual-verify", include_in_schema=False)
async def manual_verification_trigger(
    request: ManualVerificationRequest,
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
):
    """
    Manually trigger verification for a transaction

    Admin endpoint to force verification check
    Requires X-Internal-Key header
    """
    try:
        import os

        # Verify internal key
        expected_key = os.getenv("INTERNAL_API_KEY", "dev-internal-key-123")
        if x_internal_key != expected_key:
            raise HTTPException(status_code=403, detail="Invalid internal key")

        logger.info(f"🔧 Manual verification triggered for {request.transaction_hash}")

        # Get verification job
        job = get_verification_job()

        if not job or not job.is_running:
            raise HTTPException(status_code=503, detail="Verification job not running")

        # Job will check this transaction in next cycle
        return {
            "status": "accepted",
            "message": "Verification will be checked in next cycle (~30 seconds)",
            "transaction_hash": request.transaction_hash,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Manual verification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/job/status", include_in_schema=False)
async def get_job_status(
    x_internal_key: str = Header(..., alias="X-Internal-Key"),
):
    """
    Get verification job status

    Admin endpoint to check if background job is running
    """
    try:
        import os

        # Verify internal key
        expected_key = os.getenv("INTERNAL_API_KEY", "dev-internal-key-123")
        if x_internal_key != expected_key:
            raise HTTPException(status_code=403, detail="Invalid internal key")

        job = get_verification_job()

        if not job:
            return {
                "status": "not_initialized",
                "is_running": False,
                "last_check": None,
            }

        return {
            "status": "running" if job.is_running else "stopped",
            "is_running": job.is_running,
            "last_check": job.last_check.isoformat() if job.last_check else None,
            "check_interval": job.check_interval,
            "required_confirmations": job.required_confirmations,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Job status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
