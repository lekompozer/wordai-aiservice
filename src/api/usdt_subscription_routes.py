"""
USDT BEP20 Subscription Payment Routes

Endpoints for cryptocurrency (USDT BEP20) subscription payments:
- POST /api/v1/payments/usdt/subscription/create - Create payment request
- GET /api/v1/payments/usdt/subscription/{payment_id}/status - Check status
- POST /api/v1/payments/usdt/subscription/{payment_id}/verify - Verify transaction
- GET /api/v1/payments/usdt/subscription/rate - Get current USDT rate
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import JSONResponse

from src.models.usdt_payment import (
    CreateUSDTSubscriptionPaymentRequest,
    USDTPaymentResponse,
    CheckUSDTPaymentStatusResponse,
    VerifyTransactionRequest,
    USDTRateResponse,
    PaymentStatus,
)
from src.models.subscription import (
    PLAN_CONFIGS,
    get_price_for_plan,
    get_points_for_plan,
    PlanType,
    DurationType,
    CreateSubscriptionRequest,
)
from src.services.usdt_payment_service import USDTPaymentService
from src.services.bsc_service import BSCService
from src.services.subscription_service import SubscriptionService
from src.middleware.firebase_auth import require_auth
from src.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(
    prefix="/api/v1/payments/usdt/subscription", tags=["USDT Subscription Payments"]
)

# WordAI BEP20 wallet address (from .env)
WORDAI_BEP20_ADDRESS = os.getenv(
    "WORDAI_BEP20_ADDRESS", "0xbab94f5bf90550c9f0147fffae8a1ef006b85a07"
)

# USDT BEP20 contract address (Binance Smart Chain)
USDT_BEP20_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"

# Exchange rate (can be updated dynamically from Binance API later)
DEFAULT_USDT_RATE = 22320.0  # 1 USDT = 22,320 VND


def get_usdt_rate() -> float:
    """
    Get current USDT/VND exchange rate

    TODO: Integrate with Binance API to get real-time rate
    For now, uses fixed rate
    """
    # TODO: Fetch from Binance API
    # https://api.binance.com/api/v3/ticker/price?symbol=USDTVND
    return DEFAULT_USDT_RATE


# =========================================================================
# ENDPOINTS
# =========================================================================


@router.get("/rate", response_model=USDTRateResponse)
async def get_current_usdt_rate():
    """
    Get current USDT/VND exchange rate

    Returns current exchange rate used for payment calculations
    """
    try:
        rate = get_usdt_rate()

        return USDTRateResponse(
            rate=rate, last_updated=datetime.utcnow(), source="binance"
        )

    except Exception as e:
        logger.error(f"❌ Error getting USDT rate: {e}")
        raise HTTPException(status_code=500, detail="Failed to get USDT rate")


@router.post("/create", response_model=USDTPaymentResponse)
async def create_subscription_payment(
    request: CreateUSDTSubscriptionPaymentRequest,
    current_user: dict = Depends(require_auth),
    req: Request = None,
):
    """
    Create USDT payment request for subscription

    Steps:
    1. Validates plan and duration
    2. Calculates VND price and USDT equivalent
    3. Creates payment record in database
    4. Returns wallet address and payment instructions

    Frontend should:
    1. Show payment details (amount, address, network)
    2. Allow user to send USDT from their wallet
    3. Poll /status endpoint to check payment confirmation
    """
    try:
        user_id = current_user["uid"]
        user_email = current_user.get("email", "unknown")

        # Get IP and user agent
        ip_address = req.client.host if req else None
        user_agent = req.headers.get("user-agent") if req else None

        logger.info(
            f"📝 Creating USDT subscription payment for user {user_id}: {request.plan} {request.duration}"
        )

        # Validate plan and duration
        if request.plan not in ["premium", "pro", "vip"]:
            raise HTTPException(status_code=400, detail="Invalid subscription plan")

        if request.duration not in ["3_months", "12_months"]:
            raise HTTPException(status_code=400, detail="Invalid subscription duration")

        # Get VND price
        amount_vnd = get_price_for_plan(request.plan, request.duration)

        # Get USDT rate
        usdt_rate = get_usdt_rate()

        # Calculate USDT amount
        amount_usdt = round(amount_vnd / usdt_rate, 2)

        logger.info(
            f"💰 Amount: {amount_vnd} VND = {amount_usdt} USDT (rate: {usdt_rate})"
        )

        # Validate wallet balance (required)
        try:
            bsc_service = BSCService()
            wallet_balance = bsc_service.get_usdt_balance(request.from_address)

            if wallet_balance is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot verify wallet balance. Please check your wallet address: {request.from_address}",
                )

            if wallet_balance < amount_usdt:
                shortage = round(amount_usdt - wallet_balance, 2)
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "insufficient_balance",
                        "message": f"Insufficient USDT balance in your wallet",
                        "required_amount": amount_usdt,
                        "current_balance": round(wallet_balance, 2),
                        "shortage": shortage,
                        "wallet_address": request.from_address,
                    },
                )

            logger.info(
                f"✅ Balance check passed: {wallet_balance} USDT >= {amount_usdt} USDT"
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Error checking wallet balance: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to verify wallet balance: {str(e)}"
            )

        # Create payment service
        payment_service = USDTPaymentService()

        # Create payment record
        payment = payment_service.create_payment(
            user_id=user_id,
            payment_type="subscription",
            amount_usdt=amount_usdt,
            amount_vnd=amount_vnd,
            usdt_rate=usdt_rate,
            to_address=WORDAI_BEP20_ADDRESS,
            plan=request.plan,
            duration=request.duration,
            from_address=request.from_address,
            user_email=user_email,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Register wallet if provided
        if request.from_address:
            payment_service.register_wallet(user_id, request.from_address)

        logger.info(f"✅ Created payment: {payment['payment_id']}")

        # Build response
        return USDTPaymentResponse(
            payment_id=payment["payment_id"],
            order_invoice_number=payment["order_invoice_number"],
            payment_type="subscription",
            amount_usdt=amount_usdt,
            amount_vnd=amount_vnd,
            usdt_rate=usdt_rate,
            to_address=WORDAI_BEP20_ADDRESS,
            network="BSC",
            token_contract=USDT_BEP20_CONTRACT,
            instructions=f"Send exactly {amount_usdt} USDT (BEP20) to the address above. Payment will be confirmed after 12 block confirmations (~36 seconds).",
            expires_at=payment["expires_at"],
            status=payment["status"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating USDT payment: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create payment: {str(e)}"
        )


@router.get("/{payment_id}/status", response_model=CheckUSDTPaymentStatusResponse)
async def check_payment_status(
    payment_id: str,
    current_user: dict = Depends(require_auth),
):
    """
    Check USDT payment status

    Frontend should poll this endpoint every 10-15 seconds
    to check if payment has been confirmed

    Status flow:
    - pending: Awaiting payment
    - processing: Transaction detected, awaiting confirmations
    - confirmed: Transaction confirmed (12+ blocks)
    - completed: Subscription activated
    - failed/cancelled: Error or timeout
    """
    try:
        user_id = current_user["uid"]

        # Get payment
        payment_service = USDTPaymentService()
        payment = payment_service.get_payment_by_id(payment_id)

        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        # Verify ownership
        if payment["user_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to view this payment"
            )

        # Build response
        message = None
        if payment["status"] == "pending":
            message = "Awaiting payment. Please send USDT to the provided address."
        elif payment["status"] == "processing":
            message = f"Transaction detected! Confirmations: {payment['confirmation_count']}/{payment['required_confirmations']}"
        elif payment["status"] == "confirmed":
            message = "Payment confirmed! Activating subscription..."
        elif payment["status"] == "completed":
            message = "Payment completed and subscription activated!"
        elif payment["status"] == "failed":
            message = f"Payment failed: {payment.get('error_message', 'Unknown error')}"
        elif payment["status"] == "cancelled":
            message = "Payment cancelled or expired"

        return CheckUSDTPaymentStatusResponse(
            payment_id=payment["payment_id"],
            status=payment["status"],
            payment_type=payment["payment_type"],
            transaction_hash=payment.get("transaction_hash"),
            confirmation_count=payment.get("confirmation_count", 0),
            required_confirmations=payment.get("required_confirmations", 12),
            amount_usdt=payment["amount_usdt"],
            from_address=payment.get("from_address"),
            created_at=payment["created_at"],
            payment_received_at=payment.get("payment_received_at"),
            confirmed_at=payment.get("confirmed_at"),
            completed_at=payment.get("completed_at"),
            subscription_id=payment.get("subscription_id"),
            message=message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error checking payment status: {e}")
        raise HTTPException(status_code=500, detail="Failed to check payment status")


@router.post("/{payment_id}/verify")
async def verify_transaction(
    payment_id: str,
    verify_request: VerifyTransactionRequest,
    current_user: dict = Depends(require_auth),
):
    """
    Manually submit transaction hash for verification

    User can paste their transaction hash after sending USDT
    This triggers immediate verification instead of waiting for webhook

    Note: Still requires 12 confirmations before subscription activation
    """
    try:
        user_id = current_user["uid"]

        logger.info(
            f"🔍 Verifying transaction {verify_request.transaction_hash} for payment {payment_id}"
        )

        # Get payment
        payment_service = USDTPaymentService()
        payment = payment_service.get_payment_by_id(payment_id)

        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        # Verify ownership
        if payment["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        # Check if already has transaction
        if payment.get("transaction_hash"):
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Transaction already registered",
                    "transaction_hash": payment["transaction_hash"],
                    "status": payment["status"],
                },
            )

        # Update payment with transaction hash
        payment_service.update_payment_status(
            payment_id=payment_id,
            status="processing",
            transaction_hash=verify_request.transaction_hash,
        )

        # Add to pending queue for background verification
        # (Phase 5/6 will implement BSC blockchain verification)
        payment_service.add_pending_transaction(
            payment_id=payment_id,
            user_id=user_id,
            transaction_hash=verify_request.transaction_hash,
            from_address=payment.get("from_address", "unknown"),
            to_address=payment["to_address"],
            amount_usdt=payment["amount_usdt"],
        )

        logger.info(
            f"✅ Transaction registered for verification: {verify_request.transaction_hash}"
        )

        return JSONResponse(
            status_code=200,
            content={
                "message": "Transaction hash registered. Waiting for blockchain confirmations.",
                "transaction_hash": verify_request.transaction_hash,
                "required_confirmations": 12,
                "estimated_time": "~36 seconds",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error verifying transaction: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify transaction")


@router.get("/history")
async def get_payment_history(
    limit: int = 20,
    skip: int = 0,
    current_user: dict = Depends(require_auth),
):
    """
    Get user's USDT subscription payment history

    Returns list of all USDT subscription payments by user
    """
    try:
        user_id = current_user["uid"]

        payment_service = USDTPaymentService()
        payments = payment_service.get_user_payments(
            user_id=user_id,
            payment_type="subscription",
            limit=limit,
            skip=skip,
        )

        # Convert ObjectId to string for JSON serialization
        for payment in payments:
            if "_id" in payment:
                payment["_id"] = str(payment["_id"])

        return {
            "payments": payments,
            "count": len(payments),
            "limit": limit,
            "skip": skip,
        }

    except Exception as e:
        logger.error(f"❌ Error getting payment history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get payment history")


# =========================================================================
# INTERNAL ENDPOINT - For background job/webhook to activate subscription
# =========================================================================


@router.post("/{payment_id}/activate", include_in_schema=False)
async def activate_subscription_after_payment(
    payment_id: str,
    internal_key: str = Header(..., alias="X-Internal-Key"),
):
    """
    Internal endpoint to activate subscription after payment confirmation

    Called by:
    - Background job after 12 confirmations
    - Webhook after receiving payment notification

    Requires X-Internal-Key header for security
    """
    try:
        # Verify internal key
        expected_key = os.getenv("INTERNAL_API_KEY", "dev-internal-key-123")
        if internal_key != expected_key:
            raise HTTPException(status_code=403, detail="Invalid internal key")

        logger.info(f"🔐 Activating subscription for payment {payment_id}")

        # Get payment
        payment_service = USDTPaymentService()
        payment = payment_service.get_payment_by_id(payment_id)

        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        # Check if already activated
        if payment["status"] == "completed" and payment.get("subscription_id"):
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Subscription already activated",
                    "subscription_id": payment["subscription_id"],
                },
            )

        # Check if payment is confirmed
        if payment["status"] not in ["confirmed", "completed"]:
            raise HTTPException(
                status_code=400,
                detail=f"Payment not confirmed yet. Current status: {payment['status']}",
            )

        # Create subscription
        subscription_service = SubscriptionService()

        # Duration in months
        duration_months = 3 if payment["duration"] == "3_months" else 12

        # Create subscription request
        sub_request = CreateSubscriptionRequest(
            user_id=payment["user_id"],
            plan=payment["plan"],
            duration=payment["duration"],
            payment_id=payment["payment_id"],
            payment_method="USDT_BEP20",
        )

        # Create subscription
        subscription = await subscription_service.create_paid_subscription(sub_request)

        # Link payment to subscription
        subscription_id = str(subscription.id)
        payment_service.link_subscription(payment_id, subscription_id)

        # Update payment status to completed
        payment_service.update_payment_status(payment_id, "completed")

        # Update wallet usage
        if payment.get("from_address"):
            payment_service.update_wallet_usage(
                user_id=payment["user_id"],
                wallet_address=payment["from_address"],
                amount_usdt=payment["amount_usdt"],
            )

        logger.info(
            f"✅ Subscription {subscription_id} activated for payment {payment_id}"
        )

        return JSONResponse(
            status_code=200,
            content={
                "message": "Subscription activated successfully",
                "subscription_id": subscription_id,
                "plan": payment["plan"],
                "duration": payment["duration"],
                "points_granted": subscription.points_total,
                "expires_at": subscription.expires_at.isoformat(),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error activating subscription: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to activate subscription: {str(e)}"
        )
