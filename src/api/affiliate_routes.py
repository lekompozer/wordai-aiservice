"""
Affiliate System API Routes

Endpoints:
- GET  /api/v1/affiliates/validate/{code}   — Validate affiliate code (public)
- GET  /api/v1/affiliates/me                — My affiliate dashboard
- GET  /api/v1/affiliates/transactions      — My commission history
- POST /api/v1/affiliates/withdraw          — Request a withdrawal

Affiliate tiers:
- Tier 1 (Trung tâm / Đại lý cấp 1): 40% hoa hồng, giá học viên 99k/tháng
- Tier 2 (Cộng tác viên / Đại lý cấp 2): 25% hoa hồng, giá học viên 119k/tháng
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.models.conversation_subscription import (
    PRICING_TIERS,
    AFFILIATE_COMMISSION_RATES,
)
from src.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(
    prefix="/api/v1/affiliates",
    tags=["Affiliate"],
)

TIER_LABELS = {
    1: "Đại lý cấp 1 (Trung tâm)",
    2: "Đại lý cấp 2 (Cộng tác viên)",
}


def get_db():
    db_manager = DBManager()
    return db_manager.db


def _get_affiliate(db, user_id: str, email: str = None) -> dict:
    """Look up affiliate by Firebase UID, with email-based auto-link on first login."""
    # Fast path: already linked
    aff = db["affiliates"].find_one({"user_id": user_id})

    # First-time login: look up by email, then link UID
    if not aff and email:
        aff = db["affiliates"].find_one({"email": email.lower()})
        if aff:
            db["affiliates"].update_one(
                {"_id": aff["_id"]},
                {"$set": {"user_id": user_id, "updated_at": datetime.utcnow()}},
            )
            aff["user_id"] = user_id
            logger.info(
                f"🔗 Affiliate {aff['code']} UID linked: email={email} uid={user_id}"
            )

    return aff


# ============================================================================
# Pydantic Models
# ============================================================================


class WithdrawRequest(BaseModel):
    amount: int = Field(
        ..., ge=100_000, description="Số tiền rút (VND), tối thiểu 100,000"
    )
    bank_name: Optional[str] = Field(
        None, description="Tên ngân hàng (bỏ trống nếu đã lưu)"
    )
    bank_account_number: Optional[str] = Field(
        None, description="Số tài khoản (bỏ trống nếu đã lưu)"
    )
    bank_account_name: Optional[str] = Field(
        None, description="Tên chủ tài khoản (bỏ trống nếu đã lưu)"
    )
    notes: Optional[str] = Field(None, description="Ghi chú thêm")


# ============================================================================
# GET /validate/{code}  — PUBLIC
# ============================================================================


@router.get("/validate/{code}")
async def validate_affiliate_code(code: str, db=Depends(get_db)):
    """
    Public endpoint: Validate an affiliate code.
    Returns tier, discount info, and price preview for the checkout UI.
    No authentication required.
    """
    aff = db["affiliates"].find_one(
        {"code": code.upper(), "is_active": True},
        {"tier": 1, "code": 1, "name": 1},
    )
    if not aff:
        raise HTTPException(
            status_code=404, detail="Mã đại lý không tồn tại hoặc chưa được kích hoạt."
        )

    tier = aff["tier"]
    tier_key = f"tier_{tier}"
    price_per_month = PRICING_TIERS.get(tier_key, PRICING_TIERS["no_code"])
    original_price = PRICING_TIERS["no_code"]
    commission_rate = AFFILIATE_COMMISSION_RATES.get(tier, 0)

    discount_percent = round((1 - price_per_month / original_price) * 100)

    return {
        "valid": True,
        "code": aff["code"],
        "affiliate_name": aff.get("name", ""),
        "tier": tier,
        "tier_label": TIER_LABELS.get(tier, ""),
        "price_per_month": price_per_month,
        "original_price_per_month": original_price,
        "discount_percent": discount_percent,
        # Tier-1 (language centers) require student ID
        "requires_student_id": tier == 1,
    }


# ============================================================================
# GET /me  — My affiliate dashboard
# ============================================================================


@router.get("/me")
async def get_my_affiliate_dashboard(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Return the authenticated user's affiliate account details and balance summary.
    """
    user_id = current_user["uid"]

    aff = _get_affiliate(db, user_id, email=current_user.get("email"))
    if not aff:
        raise HTTPException(
            status_code=404,
            detail="Bạn chưa có tài khoản đại lý. Liên hệ admin để đăng ký.",
        )

    # Compute dynamic balances from withdrawal records
    pending_wd_agg = list(
        db["affiliate_withdrawals"].aggregate(
            [
                {"$match": {"affiliate_id": str(aff["_id"]), "status": "pending"}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]
        )
    )
    approved_wd_agg = list(
        db["affiliate_withdrawals"].aggregate(
            [
                {"$match": {"affiliate_id": str(aff["_id"]), "status": "approved"}},
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

    return {
        "code": aff["code"],
        "name": aff.get("name", ""),
        "email": aff.get("email"),
        "tier": aff["tier"],
        "tier_label": TIER_LABELS.get(aff["tier"], ""),
        "is_active": aff.get("is_active", False),
        "commission_rate": AFFILIATE_COMMISSION_RATES.get(aff["tier"], 0),
        "requires_student_id": aff["tier"] == 1,
        "price_per_month": PRICING_TIERS.get(
            f"tier_{aff['tier']}", PRICING_TIERS["no_code"]
        ),
        "total_students": aff.get("total_referred_users", 0),
        # Flat balance fields (read directly by frontend)
        "total_earned": total_earned,
        "total_withdrawn": total_withdrawn,  # Tổng đã rút (approved)
        "pending_balance": pending_withdrawal_amount,  # Chờ thanh toán = pending requests
        "available_balance": available_balance,  # Sẵn sàng rút = total_earned - total_withdrawn - pending
        # Nested for backward compat
        "balances": {
            "total_earned": total_earned,
            "total_withdrawn": total_withdrawn,
            "pending_balance": pending_withdrawal_amount,
            "available_balance": available_balance,
            "total_referred_users": aff.get("total_referred_users", 0),
        },
        "bank_info": aff.get("bank_info"),
        "created_at": (
            aff.get("created_at", "").isoformat() if aff.get("created_at") else None
        ),
    }


# ============================================================================
# GET /students  — List enrolled students via this affiliate code
# ============================================================================


@router.get("/students")
async def get_my_students(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    List all students who enrolled via this affiliate's code.
    Returns user email, student_id (entered at checkout), package, amount, date.
    """
    user_id = current_user["uid"]

    aff = _get_affiliate(db, user_id, email=current_user.get("email"))
    if not aff:
        raise HTTPException(status_code=404, detail="Bạn chưa có tài khoản đại lý.")

    code = aff["code"]
    query = {
        "affiliate_code": code,
        "plan_type": "conversation_learning",
        "status": "completed",
    }
    total = db["payments"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["payments"].find(query).sort("completed_at", -1).skip(skip).limit(page_size)
    )

    items = []
    for doc in docs:
        # Check if subscription is still active
        sub = db["user_conversation_subscription"].find_one(
            {"order_invoice_number": doc.get("order_invoice_number")},
            {"is_active": 1, "end_date": 1, "start_date": 1},
        )
        items.append(
            {
                "user_id": doc.get("user_id"),
                "user_email": doc.get("user_email"),
                "user_name": doc.get("user_name"),
                "student_id": doc.get("student_id"),
                "package_id": doc.get("package_id"),
                "amount_paid": doc.get("price", 0),
                "order_invoice_number": doc.get("order_invoice_number"),
                "enrolled_at": (
                    doc["completed_at"].isoformat() if doc.get("completed_at") else None
                ),
                "subscription_active": sub.get("is_active", False) if sub else False,
                "subscription_end_date": (
                    sub["end_date"].isoformat() if sub and sub.get("end_date") else None
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
async def get_my_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(
        default=None, description="pending | approved | paid"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    List the authenticated affiliate's commission transactions.
    """
    user_id = current_user["uid"]

    aff = _get_affiliate(db, user_id, email=current_user.get("email"))
    if not aff:
        raise HTTPException(status_code=404, detail="Bạn chưa có tài khoản đại lý.")

    affiliate_id = str(aff["_id"])

    query: dict = {"affiliate_id": affiliate_id}
    if status:
        query["status"] = status

    total = db["affiliate_commissions"].count_documents(query)
    skip = (page - 1) * page_size

    docs = list(
        db["affiliate_commissions"]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )

    items = []
    for doc in docs:
        items.append(
            {
                "id": str(doc["_id"]),
                "user_id": doc.get("user_id"),
                "amount_paid_by_user": doc.get("amount_paid_by_user"),
                "commission_rate": doc.get("commission_rate"),
                "commission_amount": doc.get("commission_amount"),
                "student_id": doc.get("student_id"),
                "status": doc.get("status"),
                "created_at": (
                    doc["created_at"].isoformat() if doc.get("created_at") else None
                ),
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


# ============================================================================
# GET /withdrawals  — List my withdrawal requests
# ============================================================================


@router.get("/withdrawals")
async def get_my_withdrawals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    List withdrawal requests submitted by this affiliate (newest first).
    """
    user_id = current_user["uid"]
    aff = _get_affiliate(db, user_id, email=current_user.get("email"))
    if not aff:
        raise HTTPException(status_code=404, detail="Bạn chưa có tài khoản đại lý.")

    query = {"affiliate_id": str(aff["_id"])}
    total = db["affiliate_withdrawals"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["affiliate_withdrawals"]
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
async def request_withdrawal(
    body: WithdrawRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Submit a withdrawal request for available affiliate balance.
    Bank info is optional if already saved to profile; new info will be saved.
    """
    user_id = current_user["uid"]

    aff = _get_affiliate(db, user_id, email=current_user.get("email"))
    if not aff:
        raise HTTPException(status_code=404, detail="Bạn chưa có tài khoản đại lý.")

    # Compute available balance dynamically (earned - pending requests)
    pending_wd_agg = list(
        db["affiliate_withdrawals"].aggregate(
            [
                {"$match": {"affiliate_id": str(aff["_id"]), "status": "pending"}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]
        )
    )
    approved_wd_agg_w = list(
        db["affiliate_withdrawals"].aggregate(
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
    pending_wd_amt = pending_wd_agg[0]["total"] if pending_wd_agg else 0
    total_withdrawn_w = approved_wd_agg_w[0]["total"] if approved_wd_agg_w else 0
    available = max(0, aff.get("total_earned", 0) - total_withdrawn_w - pending_wd_amt)

    if body.amount > available:
        raise HTTPException(
            status_code=400,
            detail=f"Số dư khả dụng không đủ. Hiện có: {available:,} VND.",
        )

    # Check no pending withdrawal already exists
    existing_pending = db["affiliate_withdrawals"].find_one(
        {"affiliate_id": str(aff["_id"]), "status": "pending"}
    )
    if existing_pending:
        raise HTTPException(
            status_code=400,
            detail="Bạn đang có yêu cầu rút tiền đang chờ xử lý. Vui lòng chờ admin duyệt.",
        )

    # Resolve bank info: use body fields or fall back to saved profile
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
    result = db["affiliate_withdrawals"].insert_one(doc)

    # Save bank info to profile for convenience on next withdrawal
    db["affiliates"].update_one(
        {"_id": aff["_id"]},
        {"$set": {"bank_info": bank_info, "updated_at": now}},
    )

    logger.info(
        f"💸 Withdrawal request: affiliate={aff['code']}, "
        f"amount={body.amount:,} VND, id={result.inserted_id}"
    )

    return {
        "withdrawal_id": str(result.inserted_id),
        "amount": body.amount,
        "status": "pending",
        "message": "Yêu cầu rút tiền đã được ghi nhận. Admin sẽ xử lý trong 1-3 ngày làm việc.",
        "bank_info": bank_info,
    }
