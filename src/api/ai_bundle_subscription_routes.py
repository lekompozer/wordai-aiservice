"""
AI Bundle Subscription Routes

Endpoints:
- GET  /api/v1/ai-bundle/plans           — Available plans (optionally priced by affiliate code)
- GET  /api/v1/ai-bundle/validate-code   — Validate affiliate code + get discounted prices
- GET  /api/v1/ai-bundle/me              — Current user's subscription status + quota
- POST /api/v1/ai-bundle/trial/activate  — Activate 15-day free trial (auth required)
- POST /api/v1/ai-bundle/activate        — Activate after payment (internal, X-Service-Secret)
"""

import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Header

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.models.ai_bundle_subscription import (
    AI_BUNDLE_PRICING,
    AI_BUNDLE_REQUESTS_LIMIT,
    PLAN_LABELS,
    AFFILIATE_COMMISSION_RATES,
    TRIAL_DAYS,
    TRIAL_REQUESTS_LIMIT,
    get_price,
    ActivateAiBundleSubscriptionRequest,
    ActivateAiBundleSubscriptionResponse,
)
from src.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(
    prefix="/api/v1/ai-bundle",
    tags=["AI Bundle Subscription"],
)

SERVICE_SECRET = os.getenv(
    "API_SECRET_KEY", "wordai-payment-service-secret-2025-secure-key"
)


def get_db():
    db_manager = DBManager()
    return db_manager.db


def verify_service_secret(
    x_service_secret: str = Header(..., alias="X-Service-Secret"),
):
    if x_service_secret != SERVICE_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


def _first_day_next_month(now: datetime) -> datetime:
    if now.month == 12:
        return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)


# ============================================================================
# GET /plans  — PUBLIC
# ============================================================================


@router.get("/plans")
async def get_ai_bundle_plans(
    code: Optional[str] = None,
    db=Depends(get_db),
):
    """
    Return available AI Bundle plans with final prices.

    If ?code= is provided and matches a valid ai_bundle_affiliates code,
    prices are calculated at the affiliate's tier rate.
    No authentication required.
    """
    price_tier = "no_code"
    affiliate_info = None

    if code:
        aff = db["ai_bundle_affiliates"].find_one(
            {"code": code.upper(), "is_active": True},
            {"tier": 1, "code": 1, "name": 1},
        )
        if aff:
            price_tier = f"tier_{aff['tier']}"
            affiliate_info = {"code": aff["code"], "tier": aff["tier"]}

    plans = []
    for plan_id in ("basic", "advanced"):
        price = get_price(price_tier, plan_id)
        original = get_price("no_code", plan_id)
        limit = AI_BUNDLE_REQUESTS_LIMIT[plan_id]

        plans.append(
            {
                "plan_id": plan_id,
                "plan_label": PLAN_LABELS[plan_id],
                "requests_per_month": limit,
                "months": 12,
                "price_tier": price_tier,
                "original_price": original,
                "price": price,
                "is_popular": plan_id == "advanced",
                "features": [
                    f"{limit} AI requests / tháng (reset ngày 1)",
                    "AI Giải bài tập (Learning Assistant)",
                    "AI Chấm điểm bài làm (Learning Assistant)",
                    "AI Tạo code (Code Studio)",
                    "AI Giải thích code (Code Studio)",
                    "AI Chuyển đổi code (Code Studio)",
                    "Lịch sử không giới hạn",
                ],
            }
        )

    return {
        "plans": plans,
        "affiliate": affiliate_info,
        "note": "Gói AI Bundle gồm AI Learning Assistant + AI Code Studio (3 tính năng cơ bản).",
    }


# ============================================================================
# GET /validate-code  — AUTH REQUIRED
# ============================================================================


@router.get("/validate-code")
async def validate_ai_bundle_affiliate_code(
    code: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Validate an AI Bundle affiliate code (requires login).
    Returns tier info and discounted prices for the checkout UI.
    """
    TIER_LABELS = {
        1: "Đại lý Cấp 1 (Trung tâm / Tổ chức)",
        2: "Đại lý Cấp 2 (Cộng tác viên)",
    }

    aff = db["ai_bundle_affiliates"].find_one(
        {"code": code.upper()},
        {"tier": 1, "code": 1, "name": 1, "is_active": 1, "user_id": 1},
    )
    if not aff:
        raise HTTPException(
            status_code=404,
            detail={"error": "invalid_code", "message": "Mã đại lý không tồn tại."},
        )
    if not aff.get("is_active", True):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "affiliate_not_active",
                "message": "Đại lý chưa được kích hoạt.",
            },
        )
    if not aff.get("user_id"):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "affiliate_not_registered",
                "message": "Đại lý chưa đăng nhập lần nào. Vui lòng yêu cầu đại lý đăng nhập trước.",
            },
        )

    tier = aff["tier"]
    price_tier = f"tier_{tier}"
    original_no_code_basic = get_price("no_code", "basic")
    discounted_basic = get_price(price_tier, "basic")
    discount_percent = round((1 - discounted_basic / original_no_code_basic) * 100)

    plans = []
    for plan_id in ("basic", "advanced"):
        plans.append(
            {
                "plan_id": plan_id,
                "original_price": get_price("no_code", plan_id),
                "price": get_price(price_tier, plan_id),
                "requests_per_month": AI_BUNDLE_REQUESTS_LIMIT[plan_id],
            }
        )

    return {
        "valid": True,
        "code": aff["code"],
        "affiliate_name": aff.get("name", ""),
        "tier": tier,
        "tier_label": TIER_LABELS.get(tier, ""),
        "discount_percent": discount_percent,
        "plans": plans,
    }


# ============================================================================
# GET /me  — AUTH REQUIRED
# ============================================================================


@router.get("/me")
async def get_my_ai_bundle_subscription(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Return the authenticated user's AI Bundle subscription status and remaining quota.
    Auto-resets monthly counter if past reset date.
    """
    user_id = current_user["uid"]
    now = datetime.now(timezone.utc)

    # Prefer paid subscription over trial when both exist; active only
    sub = db["user_ai_bundle_subscriptions"].find_one(
        {"user_id": user_id, "is_active": True},
        sort=[("is_trial", 1), ("created_at", -1)],  # False < True → paid first
    )

    if not sub:
        # Return whether the user has ever activated a trial (so UI knows)
        had_trial = db["user_ai_bundle_subscriptions"].find_one(
            {"user_id": user_id, "is_trial": True}
        )
        return {"is_active": False, "is_trial": False, "trial_used": bool(had_trial)}

    # Check expiry
    expires_at = sub.get("expires_at")
    if expires_at and expires_at <= now:
        # Mark expired
        db["user_ai_bundle_subscriptions"].update_one(
            {"_id": sub["_id"]},
            {"$set": {"is_active": False, "status": "expired", "updated_at": now}},
        )
        return {"is_active": False}

    # Auto-reset monthly counter if past reset date
    reset_date = sub.get("requests_reset_date")
    if reset_date and reset_date <= now:
        new_reset = _first_day_next_month(now)
        db["user_ai_bundle_subscriptions"].update_one(
            {"_id": sub["_id"]},
            {
                "$set": {
                    "requests_used_this_month": 0,
                    "requests_reset_date": new_reset,
                    "updated_at": now,
                }
            },
        )
        sub["requests_used_this_month"] = 0
        sub["requests_reset_date"] = new_reset

    limit = sub.get(
        "requests_monthly_limit",
        AI_BUNDLE_REQUESTS_LIMIT.get(sub.get("plan", "basic"), 100),
    )
    used = sub.get("requests_used_this_month", 0)

    is_trial = sub.get("is_trial", False)
    trial_days_remaining = None
    if is_trial and expires_at:
        trial_days_remaining = max(0, (expires_at - now).days)

    return {
        "is_active": True,
        "is_trial": is_trial,
        "trial_days_remaining": trial_days_remaining,
        "trial_used": True if is_trial else None,  # None = paid user (irrelevant)
        "plan": sub.get("plan"),
        "plan_label": (
            PLAN_LABELS.get(sub.get("plan", ""), "Dùng thử")
            if not is_trial
            else "Dùng thử (15 ngày)"
        ),
        "requests_monthly_limit": limit,
        "requests_used_this_month": used,
        "requests_remaining": max(0, limit - used),
        "requests_reset_date": (
            sub["requests_reset_date"].isoformat()
            if sub.get("requests_reset_date")
            else None
        ),
        "started_at": sub["started_at"].isoformat() if sub.get("started_at") else None,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "features": {
            "learning_assistant": True,
            "code_studio_basic": True,
        },
    }


# ============================================================================
# POST /trial/activate  — AUTH REQUIRED (one-time 15-day free trial)
# ============================================================================


@router.post("/trial/activate")
async def activate_ai_bundle_trial(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Activate a 15-day free trial of AI Bundle.
    - Each Firebase account can only activate once (even after trial expires).
    - Blocked if user already has an active paid subscription.
    - Trial gives TRIAL_REQUESTS_LIMIT requests total (no monthly reset within trial period).
    """
    user_id = current_user["uid"]
    now = datetime.now(timezone.utc)

    # One-time only: reject if trial ever activated (any status)
    already_used = db["user_ai_bundle_subscriptions"].find_one(
        {"user_id": user_id, "is_trial": True}
    )
    if already_used:
        raise HTTPException(
            status_code=409,
            detail="Bạn đã sử dụng dùng thử AI Bundle. Mỗi tài khoản chỉ được dùng thử 1 lần.",
        )

    # Don't create trial if already has active paid subscription
    paid_sub = db["user_ai_bundle_subscriptions"].find_one(
        {"user_id": user_id, "is_active": True, "is_trial": {"$ne": True}}
    )
    if paid_sub:
        raise HTTPException(
            status_code=409,
            detail="Bạn đã có gói AI Bundle đang hoạt động.",
        )

    expires_at = now + timedelta(days=TRIAL_DAYS)

    # Set reset_date AFTER expires_at so auto-reset in quota middleware never fires.
    # 20 requests is a hard cap for the full 15-day period — no mid-trial reset.
    reset_date = expires_at + timedelta(days=1)

    sub_doc = {
        "user_id": user_id,
        "plan": "trial",
        "status": "active",
        "is_active": True,
        "is_trial": True,
        "price_tier": "no_code",
        "amount_paid": 0,
        "payment_id": None,
        "order_invoice_number": None,
        "payment_method": None,
        "affiliate_code": None,
        "requests_monthly_limit": TRIAL_REQUESTS_LIMIT,
        "requests_used_this_month": 0,
        "requests_reset_date": reset_date,
        "started_at": now,
        "expires_at": expires_at,
        "created_at": now,
        "updated_at": now,
    }
    result = db["user_ai_bundle_subscriptions"].insert_one(sub_doc)
    logger.info(
        f"[ai_bundle] 🎁 Trial activated user={user_id} expires={expires_at.date()}"
    )

    return {
        "success": True,
        "message": f"Kích hoạt dùng thử AI Bundle thành công! Bạn có {TRIAL_DAYS} ngày và {TRIAL_REQUESTS_LIMIT} lượt sử dụng.",
        "plan": "trial",
        "is_trial": True,
        "requests_limit": TRIAL_REQUESTS_LIMIT,
        "trial_days_remaining": TRIAL_DAYS,
        "expires_at": expires_at.isoformat(),
        "features": {
            "learning_assistant": True,
            "code_studio_basic": True,
        },
    }


# ============================================================================
# POST /activate  — X-Service-Secret (payment service → Python service)
# ============================================================================


@router.post("/activate", response_model=ActivateAiBundleSubscriptionResponse)
async def activate_ai_bundle_subscription(
    body: ActivateAiBundleSubscriptionRequest,
    _: bool = Depends(verify_service_secret),
    db=Depends(get_db),
):
    """
    Activate or extend an AI Bundle subscription after payment confirmation.
    Called internally by the payment-service worker via X-Service-Secret.
    """
    user_id = body.user_id
    plan = body.plan
    now = datetime.now(timezone.utc)

    if plan not in ("basic", "advanced"):
        raise HTTPException(status_code=400, detail=f"Plan '{plan}' không hợp lệ.")

    requests_limit = AI_BUNDLE_REQUESTS_LIMIT[plan]
    expires_at = now + timedelta(days=365)
    next_reset = _first_day_next_month(now)

    # Check for existing active subscription
    existing = db["user_ai_bundle_subscriptions"].find_one(
        {"user_id": user_id, "is_active": True, "expires_at": {"$gt": now}}
    )

    if existing:
        # Extend from existing expiry date
        new_expires = max(existing["expires_at"], now) + timedelta(days=365)
        db["user_ai_bundle_subscriptions"].update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "plan": plan,
                    "price_tier": body.price_tier,
                    "expires_at": new_expires,
                    "requests_monthly_limit": requests_limit,
                    "affiliate_code": body.affiliate_code,
                    "updated_at": now,
                }
            },
        )
        subscription_id = str(existing["_id"])
        expires_at = new_expires
        logger.info(
            f"[ai_bundle] ↗ Extended subscription for user={user_id} to {new_expires.date()}"
        )
    else:
        sub_doc = {
            "user_id": user_id,
            "plan": plan,
            "status": "active",
            "is_active": True,
            "price_tier": body.price_tier,
            "amount_paid": body.amount_paid,
            "payment_id": body.payment_id,
            "order_invoice_number": body.order_invoice_number,
            "payment_method": body.payment_method,
            "affiliate_code": body.affiliate_code,
            "requests_monthly_limit": requests_limit,
            "requests_used_this_month": 0,
            "requests_reset_date": next_reset,
            "started_at": now,
            "expires_at": expires_at,
            "created_at": now,
            "updated_at": now,
        }
        result = db["user_ai_bundle_subscriptions"].insert_one(sub_doc)
        subscription_id = str(result.inserted_id)
        logger.info(
            f"[ai_bundle] ✅ New subscription for user={user_id} expires {expires_at.date()}"
        )

    return ActivateAiBundleSubscriptionResponse(
        subscription_id=subscription_id,
        user_id=user_id,
        plan=plan,
        plan_label=PLAN_LABELS[plan],
        requests_monthly_limit=requests_limit,
        expires_at=expires_at.isoformat(),
        message=f"Kích hoạt gói AI Bundle ({PLAN_LABELS[plan]}) thành công.",
    )
