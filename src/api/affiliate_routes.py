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


# ============================================================================
# Pydantic Models
# ============================================================================


class WithdrawRequest(BaseModel):
    amount: int = Field(
        ..., ge=100_000, description="Số tiền rút (VND), tối thiểu 100,000"
    )
    bank_name: str = Field(..., description="Tên ngân hàng")
    bank_account_number: str = Field(..., description="Số tài khoản")
    bank_account_name: str = Field(..., description="Tên chủ tài khoản")
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

    aff = db["affiliates"].find_one({"user_id": user_id})
    if not aff:
        raise HTTPException(
            status_code=404,
            detail="Bạn chưa có tài khoản đại lý. Liên hệ admin để đăng ký.",
        )

    return {
        "code": aff["code"],
        "name": aff.get("name", ""),
        "tier": aff["tier"],
        "tier_label": TIER_LABELS.get(aff["tier"], ""),
        "is_active": aff.get("is_active", False),
        "commission_rate": AFFILIATE_COMMISSION_RATES.get(aff["tier"], 0),
        "price_per_month": PRICING_TIERS.get(
            f"tier_{aff['tier']}", PRICING_TIERS["no_code"]
        ),
        "balances": {
            "pending_balance": aff.get("pending_balance", 0),
            "available_balance": aff.get("available_balance", 0),
            "total_earned": aff.get("total_earned", 0),
            "total_referred_users": aff.get("total_referred_users", 0),
        },
        "bank_info": aff.get("bank_info"),
        "created_at": (
            aff.get("created_at", "").isoformat() if aff.get("created_at") else None
        ),
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

    aff = db["affiliates"].find_one({"user_id": user_id}, {"_id": 1})
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
    """
    user_id = current_user["uid"]

    aff = db["affiliates"].find_one({"user_id": user_id})
    if not aff:
        raise HTTPException(status_code=404, detail="Bạn chưa có tài khoản đại lý.")

    available = aff.get("available_balance", 0)
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

    now = datetime.utcnow()
    bank_info = {
        "bank_name": body.bank_name,
        "account_number": body.bank_account_number,
        "account_name": body.bank_account_name,
    }

    doc = {
        "affiliate_id": str(aff["_id"]),
        "user_id": user_id,
        "amount": body.amount,
        "status": "pending",
        "bank_info": bank_info,
        "notes": body.notes,
        "created_at": now,
        "updated_at": now,
    }
    result = db["affiliate_withdrawals"].insert_one(doc)

    # Deduct from available_balance (hold until processed)
    db["affiliates"].update_one(
        {"_id": aff["_id"]},
        {
            "$inc": {"available_balance": -body.amount},
            "$set": {"updated_at": now},
        },
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
