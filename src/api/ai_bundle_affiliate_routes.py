"""
AI Bundle Affiliate Routes

Mirrors src/api/affiliate_routes.py but uses ai_bundle_* collections.

Endpoints:
- GET  /api/v1/ai-bundle/affiliate/validate/{code}  — Validate code (public)
- GET  /api/v1/ai-bundle/affiliate/me               — Dashboard
- GET  /api/v1/ai-bundle/affiliate/students         — Customers list
- GET  /api/v1/ai-bundle/affiliate/transactions     — Commission history
- GET  /api/v1/ai-bundle/affiliate/withdrawals      — Withdrawal requests
- POST /api/v1/ai-bundle/affiliate/withdraw         — Request withdrawal
"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.models.ai_bundle_subscription import (
    AI_BUNDLE_PRICING,
    AFFILIATE_COMMISSION_RATES,
    get_price,
)
from src.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(
    prefix="/api/v1/ai-bundle/affiliate",
    tags=["AI Bundle Affiliate"],
)

TIER_LABELS = {
    1: "Đại lý cấp 1 (Trung tâm)",
    2: "Đại lý cấp 2 (Cộng tác viên)",
}


def get_db():
    db_manager = DBManager()
    return db_manager.db


def _get_ai_bundle_affiliate(db, user_id: str, email: str = None) -> dict:
    """Look up ai_bundle_affiliates by Firebase UID.
    If not found, auto-link UID via email on first login."""
    aff = db["ai_bundle_affiliates"].find_one({"user_id": user_id})

    if not aff and email:
        aff = db["ai_bundle_affiliates"].find_one({"email": email.lower()})
        if aff:
            db["ai_bundle_affiliates"].update_one(
                {"_id": aff["_id"]},
                {"$set": {"user_id": user_id, "updated_at": datetime.utcnow()}},
            )
            aff["user_id"] = user_id
            logger.info(
                f"🔗 [AI Bundle] Affiliate {aff['code']} UID linked: "
                f"email={email} uid={user_id}"
            )

    return aff


class WithdrawRequest(BaseModel):
    amount: int = Field(
        ..., ge=100_000, description="Số tiền rút (VND), tối thiểu 100,000"
    )
    bank_name: Optional[str] = Field(None)
    bank_account_number: Optional[str] = Field(None)
    bank_account_name: Optional[str] = Field(None)
    notes: Optional[str] = Field(None)


# ============================================================================
# GET /validate/{code}  — PUBLIC
# ============================================================================


@router.get("/validate/{code}")
async def validate_ai_bundle_affiliate_code(code: str, db=Depends(get_db)):
    """
    Validate an AI Bundle affiliate code (no auth required).
    Returns tier, discount %, and discounted plan prices.
    """
    aff = db["ai_bundle_affiliates"].find_one(
        {"code": code.upper(), "is_active": True},
        {"tier": 1, "code": 1, "name": 1},
    )
    if not aff:
        raise HTTPException(
            status_code=404,
            detail="Mã đại lý AI Bundle không tồn tại hoặc chưa được kích hoạt.",
        )

    tier = aff["tier"]
    price_tier = f"tier_{tier}"
    original_basic = get_price("no_code", "basic")
    discounted_basic = get_price(price_tier, "basic")
    discount_percent = round((1 - discounted_basic / original_basic) * 100)

    plans = []
    for plan_id in ("basic", "advanced"):
        plans.append(
            {
                "plan_id": plan_id,
                "original_price": get_price("no_code", plan_id),
                "price": get_price(price_tier, plan_id),
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
# GET /me  — Affiliate dashboard
# ============================================================================


@router.get("/me")
async def get_my_ai_bundle_affiliate_dashboard(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    user_id = current_user["uid"]
    aff = _get_ai_bundle_affiliate(db, user_id, email=current_user.get("email"))
    if not aff:
        raise HTTPException(
            status_code=404,
            detail="Bạn chưa có tài khoản đại lý AI Bundle. Liên hệ admin để đăng ký.",
        )

    pending_wd_agg = list(
        db["ai_bundle_withdrawals"].aggregate(
            [
                {"$match": {"affiliate_id": str(aff["_id"]), "status": "pending"}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]
        )
    )
    approved_wd_agg = list(
        db["ai_bundle_withdrawals"].aggregate(
            [
                {
                    "$match": {
                        "affiliate_id": str(aff["_id"]),
                        "status": {"$in": ["approved", "paid"]},
                    }
                },
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]
        )
    )
    pending_withdrawal_amount = pending_wd_agg[0]["total"] if pending_wd_agg else 0
    total_withdrawn = approved_wd_agg[0]["total"] if approved_wd_agg else 0
    total_earned = aff.get("total_earned", 0)
    available_balance = max(
        0, total_earned - total_withdrawn - pending_withdrawal_amount
    )

    tier = aff["tier"]
    price_tier = f"tier_{tier}"

    return {
        "code": aff["code"],
        "name": aff.get("name", ""),
        "email": aff.get("email"),
        "tier": tier,
        "tier_label": TIER_LABELS.get(tier, ""),
        "is_active": aff.get("is_active", False),
        "commission_rate": AFFILIATE_COMMISSION_RATES.get(tier, 0),
        "plan_prices": {
            "basic": get_price(price_tier, "basic"),
            "advanced": get_price(price_tier, "advanced"),
        },
        "total_customers": aff.get("total_referred_users", 0),
        "total_earned": total_earned,
        "total_withdrawn": total_withdrawn,
        "pending_balance": pending_withdrawal_amount,
        "available_balance": available_balance,
        "balances": {
            "total_earned": total_earned,
            "total_withdrawn": total_withdrawn,
            "pending_balance": pending_withdrawal_amount,
            "available_balance": available_balance,
        },
        "bank_info": aff.get("bank_info"),
        "created_at": (
            aff["created_at"].isoformat() if aff.get("created_at") else None
        ),
    }


# ============================================================================
# GET /students  — Customers list
# ============================================================================


@router.get("/students")
async def get_my_ai_bundle_customers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    user_id = current_user["uid"]
    aff = _get_ai_bundle_affiliate(db, user_id, email=current_user.get("email"))
    if not aff:
        raise HTTPException(
            status_code=404, detail="Bạn chưa có tài khoản đại lý AI Bundle."
        )

    code = aff["code"]
    query = {"affiliate_code": code, "plan_type": "ai_bundle", "status": "completed"}

    total = db["payments"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["payments"].find(query).sort("completed_at", -1).skip(skip).limit(page_size)
    )

    items = []
    for doc in docs:
        sub = db["user_ai_bundle_subscriptions"].find_one(
            {"order_invoice_number": doc.get("order_invoice_number")},
            {"status": 1, "expires_at": 1, "started_at": 1, "plan": 1},
        )
        items.append(
            {
                "user_id": doc.get("user_id"),
                "user_email": doc.get("user_email"),
                "plan": doc.get("plan", ""),
                "amount_paid": doc.get("price", 0),
                "order_invoice_number": doc.get("order_invoice_number"),
                "enrolled_at": (
                    doc["completed_at"].isoformat() if doc.get("completed_at") else None
                ),
                "subscription_active": sub.get("status") == "active" if sub else False,
                "subscription_expires": (
                    sub["expires_at"].isoformat()
                    if sub and sub.get("expires_at")
                    else None
                ),
            }
        )

    return {
        "code": code,
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


# ============================================================================
# GET /transactions  — Commission history
# ============================================================================


@router.get("/transactions")
async def get_my_ai_bundle_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    user_id = current_user["uid"]
    aff = _get_ai_bundle_affiliate(db, user_id, email=current_user.get("email"))
    if not aff:
        raise HTTPException(
            status_code=404, detail="Bạn chưa có tài khoản đại lý AI Bundle."
        )

    affiliate_id = str(aff["_id"])
    query: dict = {"affiliate_id": affiliate_id}
    if status:
        query["status"] = status

    total = db["ai_bundle_commissions"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["ai_bundle_commissions"]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )

    items = [
        {
            "id": str(doc["_id"]),
            "user_id": doc.get("user_id"),
            "amount_paid_by_user": doc.get("amount_paid_by_user"),
            "commission_rate": doc.get("commission_rate"),
            "commission_amount": doc.get("commission_amount"),
            "plan": doc.get("plan"),
            "status": doc.get("status"),
            "created_at": (
                doc["created_at"].isoformat() if doc.get("created_at") else None
            ),
        }
        for doc in docs
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


# ============================================================================
# GET /withdrawals  — List withdrawal requests
# ============================================================================


@router.get("/withdrawals")
async def get_my_ai_bundle_withdrawals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    user_id = current_user["uid"]
    aff = _get_ai_bundle_affiliate(db, user_id, email=current_user.get("email"))
    if not aff:
        raise HTTPException(
            status_code=404, detail="Bạn chưa có tài khoản đại lý AI Bundle."
        )

    query = {"affiliate_id": str(aff["_id"])}
    total = db["ai_bundle_withdrawals"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["ai_bundle_withdrawals"]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )

    items = [
        {
            "id": str(doc["_id"]),
            "amount": doc.get("amount"),
            "status": doc.get("status"),
            "bank_info": doc.get("bank_info"),
            "notes": doc.get("notes"),
            "admin_notes": doc.get("admin_notes"),
            "created_at": (
                doc["created_at"].isoformat() if doc.get("created_at") else None
            ),
            "processed_at": (
                doc["processed_at"].isoformat() if doc.get("processed_at") else None
            ),
        }
        for doc in docs
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


# ============================================================================
# POST /withdraw  — Request withdrawal
# ============================================================================


@router.post("/withdraw")
async def request_ai_bundle_withdrawal(
    body: WithdrawRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    user_id = current_user["uid"]
    aff = _get_ai_bundle_affiliate(db, user_id, email=current_user.get("email"))
    if not aff:
        raise HTTPException(
            status_code=404, detail="Bạn chưa có tài khoản đại lý AI Bundle."
        )

    # Compute available balance
    pending_wd_agg = list(
        db["ai_bundle_withdrawals"].aggregate(
            [
                {"$match": {"affiliate_id": str(aff["_id"]), "status": "pending"}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]
        )
    )
    approved_wd_agg = list(
        db["ai_bundle_withdrawals"].aggregate(
            [
                {
                    "$match": {
                        "affiliate_id": str(aff["_id"]),
                        "status": {"$in": ["approved", "paid"]},
                    }
                },
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]
        )
    )
    pending_amt = pending_wd_agg[0]["total"] if pending_wd_agg else 0
    total_withdrawn = approved_wd_agg[0]["total"] if approved_wd_agg else 0
    available = max(0, aff.get("total_earned", 0) - total_withdrawn - pending_amt)

    if body.amount > available:
        raise HTTPException(
            status_code=400,
            detail=f"Số dư khả dụng không đủ. Hiện có: {available:,} VND.",
        )

    existing_pending = db["ai_bundle_withdrawals"].find_one(
        {"affiliate_id": str(aff["_id"]), "status": "pending"}
    )
    if existing_pending:
        raise HTTPException(
            status_code=400,
            detail="Bạn đang có yêu cầu rút tiền đang chờ xử lý. Vui lòng chờ admin duyệt.",
        )

    saved_bank = aff.get("bank_info") or {}
    bank_name = body.bank_name or saved_bank.get("bank_name")
    bank_account_number = body.bank_account_number or saved_bank.get("account_number")
    bank_account_name = body.bank_account_name or saved_bank.get("account_name")

    if not (bank_name and bank_account_number and bank_account_name):
        raise HTTPException(
            status_code=400,
            detail="Vui lòng cung cấp thông tin ngân hàng (lần đầu rút tiền).",
        )

    bank_info = {
        "bank_name": bank_name,
        "account_number": bank_account_number,
        "account_name": bank_account_name,
    }

    now = datetime.utcnow()
    doc = {
        "affiliate_id": str(aff["_id"]),
        "affiliate_code": aff["code"],
        "user_id": user_id,
        "amount": body.amount,
        "status": "pending",
        "bank_info": bank_info,
        "notes": body.notes,
        "created_at": now,
        "updated_at": now,
    }
    result = db["ai_bundle_withdrawals"].insert_one(doc)

    db["ai_bundle_affiliates"].update_one(
        {"_id": aff["_id"]},
        {"$set": {"bank_info": bank_info, "updated_at": now}},
    )

    logger.info(
        f"💸 [AI Bundle] Withdrawal request: affiliate={aff['code']}, "
        f"amount={body.amount:,} VND, id={result.inserted_id}"
    )

    return {
        "withdrawal_id": str(result.inserted_id),
        "amount": body.amount,
        "status": "pending",
        "message": "Yêu cầu rút tiền đã được ghi nhận. Admin sẽ xử lý trong 1-3 ngày làm việc.",
    }
