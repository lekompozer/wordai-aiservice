"""
USDT BEP20 Points Purchase Payment Routes

Endpoints for buying points with USDT cryptocurrency:
- POST /api/v1/payments/usdt/points/create - Create points payment request
- GET /api/v1/payments/usdt/points/{payment_id}/status - Check payment status
- POST /api/v1/payments/usdt/points/{payment_id}/verify - Verify transaction
- GET /api/v1/payments/usdt/points/packages - Get available points packages
"""

import os
from datetime import datetime
from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.models.usdt_payment import (
    CreateUSDTPointsPaymentRequest,
    USDTPaymentResponse,
    CheckUSDTPaymentStatusResponse,
    VerifyTransactionRequest,
    USDTRateResponse,
)
from src.services.usdt_payment_service import USDTPaymentService
from src.services.bsc_service import BSCService
from src.services.points_service import PointsService
from src.middleware.firebase_auth import require_auth
import logging

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/payments/usdt/points", tags=["USDT Points Purchase"])

# WordAI BEP20 wallet address
WORDAI_BEP20_ADDRESS = os.getenv(
    "WORDAI_BEP20_ADDRESS", "0xbab94f5bf90550c9f0147fffae8a1ef006b85a07"
)

# USDT BEP20 contract address
USDT_BEP20_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"

# Exchange rate
DEFAULT_USDT_RATE = float(os.getenv("RATE_USDT_VND", "22320"))  # 1 USDT = VND

# Points pricing packages (VND)
# Matches payment-service pricing
POINTS_PRICING_VND = {
    50: 50000,  # 50 points = 50,000 VND
    100: 95000,  # 100 points = 95,000 VND (5% discount)
    200: 180000,  # 200 points = 180,000 VND (10% discount)
}


def get_usdt_rate() -> float:
    """Get current USDT/VND exchange rate"""
    # TODO: Fetch from Binance API
    return DEFAULT_USDT_RATE


def calculate_points_price_vnd(points_amount: int) -> int:
    """
    Calculate VND price for points

    Uses tiered pricing with discounts for larger packages
    """
    if points_amount in POINTS_PRICING_VND:
        return POINTS_PRICING_VND[points_amount]

    # For custom amounts, use base price of 1000 VND/point
    return points_amount * 1000


class PointsPackage(BaseModel):
    """Points package information"""

    points: int = Field(..., description="Number of points")
    price_vnd: int = Field(..., description="Price in VND")
    price_usdt: float = Field(..., description="Price in USDT")
    discount_percentage: float = Field(0.0, description="Discount percentage")
    is_popular: bool = Field(False, description="Popular package")


# =========================================================================
# ENDPOINTS
# =========================================================================


@router.get("/packages", response_model=List[PointsPackage])
async def get_points_packages():
    """
    Get available points packages with pricing

    Returns list of predefined packages with VND and USDT prices
    """
    try:
        usdt_rate = get_usdt_rate()

        packages = []

        # Package 1: 50 points
        packages.append(
            PointsPackage(
                points=50,
                price_vnd=POINTS_PRICING_VND[50],
                price_usdt=round(POINTS_PRICING_VND[50] / usdt_rate, 2),
                discount_percentage=0.0,
                is_popular=False,
            )
        )

        # Package 2: 100 points (5% discount)
        packages.append(
            PointsPackage(
                points=100,
                price_vnd=POINTS_PRICING_VND[100],
                price_usdt=round(POINTS_PRICING_VND[100] / usdt_rate, 2),
                discount_percentage=5.0,
                is_popular=True,
            )
        )

        # Package 3: 200 points (10% discount)
        packages.append(
            PointsPackage(
                points=200,
                price_vnd=POINTS_PRICING_VND[200],
                price_usdt=round(POINTS_PRICING_VND[200] / usdt_rate, 2),
                discount_percentage=10.0,
                is_popular=False,
            )
        )

        return packages

    except Exception as e:
        logger.error(f"❌ Error getting points packages: {e}")
        raise HTTPException(status_code=500, detail="Failed to get points packages")


@router.post("/create", response_model=USDTPaymentResponse)
async def create_points_payment(
    request: CreateUSDTPointsPaymentRequest,
    current_user: dict = Depends(require_auth),
    req: Request = None,
):
    """
    Create USDT payment request for points purchase

    Steps:
    1. Validates points amount (minimum 100)
    2. Calculates VND price and USDT equivalent
    3. Creates payment record
    4. Returns wallet address and instructions

    Frontend:
    1. Show payment details (points, amount, address)
    2. User sends USDT from their wallet
    3. Poll /status endpoint for confirmation
    """
    try:
        user_id = current_user["uid"]
        user_email = current_user.get("email")

        # Get IP and user agent
        ip_address = req.client.host if req else None
        user_agent = req.headers.get("user-agent") if req else None

        logger.info(
            f"📝 Creating USDT points payment for user {user_id}: {request.points_amount} points"
        )

        # Validate points amount
        if request.points_amount < 50:
            raise HTTPException(
                status_code=400, detail="Minimum points purchase is 50 points"
            )

        # Calculate VND price
        amount_vnd = calculate_points_price_vnd(request.points_amount)

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
            payment_type="points",
            amount_usdt=amount_usdt,
            amount_vnd=amount_vnd,
            usdt_rate=usdt_rate,
            to_address=WORDAI_BEP20_ADDRESS,
            points_amount=request.points_amount,
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
            payment_type="points",
            amount_usdt=amount_usdt,
            amount_vnd=amount_vnd,
            usdt_rate=usdt_rate,
            to_address=WORDAI_BEP20_ADDRESS,
            network="BSC",
            token_contract=USDT_BEP20_CONTRACT,
            instructions=f"Send exactly {amount_usdt} USDT (BEP20) to receive {request.points_amount} points. Payment confirmed after 12 block confirmations (~36 seconds).",
            expires_at=payment["expires_at"],
            status=payment["status"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating USDT points payment: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create payment: {str(e)}"
        )


@router.get("/{payment_id}/status", response_model=CheckUSDTPaymentStatusResponse)
async def check_payment_status(
    payment_id: str,
    current_user: dict = Depends(require_auth),
):
    """
    Check USDT points payment status

    Poll this endpoint every 10-15 seconds to check confirmation

    Status flow:
    - pending: Awaiting payment
    - processing: Transaction detected, awaiting confirmations
    - confirmed: Transaction confirmed (12+ blocks)
    - completed: Points credited to account
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
            raise HTTPException(status_code=403, detail="Not authorized")

        # Build message
        message = None
        if payment["status"] == "pending":
            message = "Awaiting payment. Please send USDT to the provided address."
        elif payment["status"] == "processing":
            message = f"Transaction detected! Confirmations: {payment['confirmation_count']}/{payment['required_confirmations']}"
        elif payment["status"] == "confirmed":
            message = (
                f"Payment confirmed! Crediting {payment['points_amount']} points..."
            )
        elif payment["status"] == "completed":
            message = f"Payment completed! {payment['points_amount']} points credited to your account!"
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
            points_transaction_id=payment.get("points_transaction_id"),
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

    User pastes transaction hash after sending USDT
    Triggers immediate verification instead of waiting

    Note: Still requires 12 confirmations before points credit
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

        # Add to pending queue
        payment_service.add_pending_transaction(
            payment_id=payment_id,
            user_id=user_id,
            transaction_hash=verify_request.transaction_hash,
            from_address=payment.get("from_address", "unknown"),
            to_address=payment["to_address"],
            amount_usdt=payment["amount_usdt"],
        )

        logger.info(f"✅ Transaction registered: {verify_request.transaction_hash}")

        return JSONResponse(
            status_code=200,
            content={
                "message": "Transaction hash registered. Waiting for blockchain confirmations.",
                "transaction_hash": verify_request.transaction_hash,
                "required_confirmations": 12,
                "estimated_time": "~36 seconds",
                "points_amount": payment["points_amount"],
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
    Get user's USDT points payment history

    Returns list of all USDT points purchases by user
    """
    try:
        user_id = current_user["uid"]

        payment_service = USDTPaymentService()
        payments = payment_service.get_user_payments(
            user_id=user_id,
            payment_type="points",
            limit=limit,
            skip=skip,
        )

        # Convert ObjectId to string
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


@router.post("/{payment_id}/confirm-sent")
async def confirm_payment_sent(
    payment_id: str,
    current_user: dict = Depends(require_auth),
):
    """
    User confirms they have sent USDT

    This triggers automatic blockchain scanning to find the transaction.
    No transaction hash needed - system will scan blockchain for matching transfer.

    Scans every 15 seconds, up to 12 times (3 minutes total).
    """
    try:
        user_id = current_user.get("user_id") or current_user.get("uid")

        logger.info(f"👤 User {user_id} confirms sent USDT for payment: {payment_id}")

        # Get payment
        payment_service = USDTPaymentService()
        payment = payment_service.get_payment_by_id(payment_id)

        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        # Verify ownership
        if payment["user_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="You don't have permission for this payment"
            )

        # Check payment status
        if payment["status"] == "completed":
            return {
                "success": True,
                "message": "Payment already completed",
                "status": "completed",
            }

        if payment["status"] not in ["pending", "awaiting_payment"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot confirm payment in status: {payment['status']}",
            )

        # Check required fields for scanning
        if not payment.get("from_address"):
            raise HTTPException(
                status_code=400,
                detail="Payment missing from_address. Cannot scan blockchain.",
            )

        # Update payment status to scanning
        payment_service.update_payment_status(
            payment_id=payment_id,
            status="scanning",
        )

        # Add to pending transactions for background verification
        # No transaction_hash yet - will be found by blockchain scan
        payment_service.add_pending_transaction(
            payment_id=payment_id,
            transaction_hash=None,  # Will be found by scan
            from_address=payment["from_address"],
            retry_count=0,
            max_retries=12,  # 12 attempts × 15s = 3 minutes
        )

        logger.info(
            f"✅ Started blockchain scanning for payment: {payment_id} "
            f"from address: {payment['from_address'][:8]}..."
        )

        return {
            "success": True,
            "message": "Blockchain scanning started. We will automatically detect your transaction.",
            "status": "scanning",
            "scan_info": {
                "max_attempts": 12,
                "interval_seconds": 15,
                "total_duration_minutes": 3,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error confirming payment sent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# INTERNAL ENDPOINT - Credit points after payment confirmation
# =========================================================================


@router.post("/{payment_id}/credit", include_in_schema=False)
async def credit_points_after_payment(
    payment_id: str,
    internal_key: str = Header(..., alias="X-Internal-Key"),
):
    """
    Internal endpoint to credit points after payment confirmation

    Called by:
    - Background job after 12 confirmations
    - Webhook after payment notification

    Requires X-Internal-Key header for security
    """
    try:
        # Verify internal key
        expected_key = os.getenv("INTERNAL_API_KEY", "dev-internal-key-123")
        if internal_key != expected_key:
            raise HTTPException(status_code=403, detail="Invalid internal key")

        logger.info(f"🔐 Crediting points for payment {payment_id}")

        # Get payment
        payment_service = USDTPaymentService()
        payment = payment_service.get_payment_by_id(payment_id)

        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        # Check if already credited
        if payment["status"] == "completed" and payment.get("points_transaction_id"):
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Points already credited",
                    "points_transaction_id": payment["points_transaction_id"],
                },
            )

        # Check if payment is confirmed
        if payment["status"] not in ["confirmed", "completed"]:
            raise HTTPException(
                status_code=400,
                detail=f"Payment not confirmed yet. Current status: {payment['status']}",
            )

        # Credit points
        points_service = PointsService()

        transaction_id = points_service.add_points(
            user_id=payment["user_id"],
            amount=payment["points_amount"],
            transaction_type="purchase",
            description=f"Points purchase via USDT: {payment['payment_id']}",
            metadata={
                "payment_id": payment["payment_id"],
                "payment_method": "USDT_BEP20",
                "amount_usdt": payment["amount_usdt"],
                "amount_vnd": payment["amount_vnd"],
                "transaction_hash": payment.get("transaction_hash"),
            },
        )

        # Link payment to transaction
        payment_service.link_points_transaction(payment_id, transaction_id)

        # Update payment status
        payment_service.update_payment_status(payment_id, "completed")

        # Update wallet usage
        if payment.get("from_address"):
            payment_service.update_wallet_usage(
                user_id=payment["user_id"],
                wallet_address=payment["from_address"],
                amount_usdt=payment["amount_usdt"],
            )

        logger.info(
            f"✅ Credited {payment['points_amount']} points (txn: {transaction_id})"
        )

        return JSONResponse(
            status_code=200,
            content={
                "message": "Points credited successfully",
                "points_transaction_id": transaction_id,
                "points_amount": payment["points_amount"],
                "user_id": payment["user_id"],
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error crediting points: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to credit points: {str(e)}"
        )
