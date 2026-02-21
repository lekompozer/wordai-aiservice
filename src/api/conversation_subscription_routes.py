"""
Conversation Learning Subscription API Routes

Endpoints:
- GET  /api/v1/conversations/subscription/plans     — Available plans (optionally priced by affiliate code)
- GET  /api/v1/conversations/subscription/me        — Current user's subscription status
- POST /api/v1/conversations/subscription/activate  — Activate after payment (internal, X-Service-Secret)
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import os

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.models.conversation_subscription import (
    PRICING_TIERS,
    PACKAGE_MONTHS,
    AFFILIATE_COMMISSION_RATES,
    calculate_price,
    ConversationSubscriptionStatus,
    ActivateConversationSubscriptionRequest,
    ActivateConversationSubscriptionResponse,
)
from src.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(
    prefix="/api/v1/conversations/subscription",
    tags=["Conversation Subscription"],
)

SERVICE_SECRET = os.getenv(
    "API_SECRET_KEY", "wordai-payment-service-secret-2025-secure-key"
)

PACKAGE_LABELS = {
    "3_months": "3 Tháng",
    "6_months": "6 Tháng",
    "12_months": "12 Tháng",
}


def get_db():
    db_manager = DBManager()
    return db_manager.db


def verify_service_secret(
    x_service_secret: str = Header(..., alias="X-Service-Secret"),
):
    """Verify inter-service request from payment service."""
    if x_service_secret != SERVICE_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


# ============================================================================
# GET /plans
# ============================================================================


@router.get("/plans")
async def get_subscription_plans(
    code: Optional[str] = None,
    db=Depends(get_db),
):
    """
    Return available subscription plans with final prices.

    If `?code=` is provided and matches a valid affiliate code, prices are
    calculated at the affiliate's tier rate. The response also includes
    `original_price` (no-code price) for the frontend strikethrough display.

    No authentication required.
    """
    # Determine pricing tier from affiliate code
    price_tier = "no_code"
    affiliate_info = None

    if code:
        aff = db["affiliates"].find_one(
            {"code": code.upper(), "is_active": True}, {"tier": 1, "code": 1}
        )
        if aff:
            price_tier = f"tier_{aff['tier']}"
            affiliate_info = {"code": aff["code"], "tier": aff["tier"]}

    plans = []
    for pkg_id, months in PACKAGE_MONTHS.items():
        pricing = calculate_price(price_tier, pkg_id)
        original = calculate_price("no_code", pkg_id)

        plans.append(
            {
                "package_id": pkg_id,
                "package_label": PACKAGE_LABELS[pkg_id],
                "months": months,
                "price_tier": price_tier,
                "base_per_month": pricing["base_per_month"],
                "original_per_month": original["base_per_month"],
                "original_total": original["total"],
                "subtotal": pricing["subtotal"],
                "discount_rate": pricing["discount_rate"],
                "discount_amount": pricing["discount_amount"],
                "total": pricing["total"],
                "is_popular": pkg_id == "6_months",
                "features": [
                    "Học không giới hạn conversations",
                    "Nghe audio toàn bộ conversations",
                    "Làm Online Test miễn points",
                    "Mở khóa Song Learning",
                    "Theo dõi tiến trình học tập",
                ],
            }
        )

    return {
        "plans": plans,
        "affiliate": affiliate_info,
        "note": "Gói Conversation Learning cũng mở khóa toàn bộ Song Learning.",
    }


# ============================================================================
# GET /me
# ============================================================================


@router.get("/me", response_model=ConversationSubscriptionStatus)
async def get_my_subscription(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Return the current authenticated user's Conversation Learning subscription status.
    """
    user_id = current_user["uid"]
    now = datetime.utcnow()

    sub = db["user_conversation_subscription"].find_one(
        {"user_id": user_id, "is_active": True, "end_date": {"$gte": now}}
    )

    if not sub:
        return ConversationSubscriptionStatus(is_premium=False, subscription=None)

    days_remaining = max(0, (sub["end_date"] - now).days)

    return ConversationSubscriptionStatus(
        is_premium=True,
        subscription={
            "package": sub.get("plan_type"),
            "price_tier": sub.get("price_tier"),
            "start_date": sub["start_date"].isoformat(),
            "end_date": sub["end_date"].isoformat(),
            "days_remaining": days_remaining,
            "amount_paid": sub.get("amount_paid"),
            "affiliate_code": sub.get("affiliate_code"),
        },
    )


# ============================================================================
# POST /activate  (internal — called by payment service)
# ============================================================================


@router.post("/activate", response_model=ActivateConversationSubscriptionResponse)
async def activate_conversation_subscription(
    request: ActivateConversationSubscriptionRequest,
    _: bool = Depends(verify_service_secret),
    db=Depends(get_db),
):
    """
    Activate or extend a Conversation Learning subscription after successful payment.

    Called by the Payment Service (Node.js) after receiving an IPN webhook.
    Requires `X-Service-Secret` header for inter-service authentication.

    - Creates/extends `user_conversation_subscription`
    - Records affiliate commission in `affiliate_commissions` if code is present
    """
    user_id = request.user_id
    now = datetime.utcnow()
    months = PACKAGE_MONTHS.get(request.package, 3)

    logger.info(
        f"🎉 Activating conversation subscription: user={user_id}, "
        f"package={request.package}, tier={request.price_tier}"
    )

    # Check for existing active subscription to extend
    existing = db["user_conversation_subscription"].find_one(
        {"user_id": user_id, "is_active": True, "end_date": {"$gte": now}}
    )

    if existing:
        # Extend from current end_date
        new_end = existing["end_date"] + timedelta(days=30 * months)
        db["user_conversation_subscription"].update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "end_date": new_end,
                    "plan_type": request.package,
                    "price_tier": request.price_tier,
                    "amount_paid": existing.get("amount_paid", 0) + request.amount_paid,
                    "updated_at": now,
                }
            },
        )
        subscription_id = str(existing["_id"])
        expires_at = new_end
        logger.info(f"   ↗ Extended existing subscription to {new_end.date()}")
    else:
        # Create new subscription
        new_end = now + timedelta(days=30 * months)
        sub_doc = {
            "user_id": user_id,
            "is_active": True,
            "start_date": now,
            "end_date": new_end,
            "plan_type": request.package,
            "price_tier": request.price_tier,
            "amount_paid": request.amount_paid,
            "payment_id": request.payment_id,
            "order_invoice_number": request.order_invoice_number,
            "payment_method": request.payment_method,
            "affiliate_code": request.affiliate_code,
            "created_at": now,
            "updated_at": now,
        }
        result = db["user_conversation_subscription"].insert_one(sub_doc)
        subscription_id = str(result.inserted_id)
        expires_at = new_end
        logger.info(f"   ✅ New subscription created, expires {new_end.date()}")

    # Record affiliate commission if code provided
    if request.affiliate_code:
        aff = db["affiliates"].find_one(
            {"code": request.affiliate_code.upper(), "is_active": True}
        )
        if aff:
            commission_rate = AFFILIATE_COMMISSION_RATES.get(aff["tier"], 0.0)
            commission_amount = round(request.amount_paid * commission_rate)

            db["affiliate_commissions"].insert_one(
                {
                    "affiliate_id": str(aff["_id"]),
                    "affiliate_code": request.affiliate_code.upper(),
                    "user_id": user_id,
                    "subscription_id": subscription_id,
                    "amount_paid_by_user": request.amount_paid,
                    "commission_rate": commission_rate,
                    "commission_amount": commission_amount,
                    "status": "pending",
                    "created_at": now,
                }
            )

            # Increment affiliate balance counters
            db["affiliates"].update_one(
                {"_id": aff["_id"]},
                {
                    "$inc": {
                        "total_earned": commission_amount,
                        "pending_balance": commission_amount,
                        "total_referred_users": 1,
                    },
                    "$set": {"updated_at": now},
                },
            )

            logger.info(
                f"   💰 Commission recorded: {commission_amount} VND "
                f"for affiliate {request.affiliate_code} (tier {aff['tier']})"
            )

    return ActivateConversationSubscriptionResponse(
        subscription_id=subscription_id,
        expires_at=expires_at,
    )
