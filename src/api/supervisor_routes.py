"""
Supervisor Portal API Routes

All endpoints require Firebase Auth (supervisor's account).

Endpoints:
- GET  /api/v1/supervisors/me                            — Dashboard
- GET  /api/v1/supervisors/affiliates                    — List managed affiliates
- POST /api/v1/supervisors/affiliates                    — Create new tier-1/2 affiliate
- PUT  /api/v1/supervisors/affiliates/{code}             — Update affiliate (limited)
- GET  /api/v1/supervisors/transactions                  — Commission history
- POST /api/v1/supervisors/withdraw                      — Request withdrawal
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.models.conversation_subscription import (
    AFFILIATE_COMMISSION_RATES,
    PRICING_TIERS,
    SUPERVISOR_COMMISSION_RATE,
)
from src.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(
    prefix="/api/v1/supervisors",
    tags=["Supervisor"],
)

TIER_LABELS = {
    1: "Đại lý cấp 1 (Trung tâm)",
    2: "Đại lý cấp 2 (Cộng tác viên)",
}


def get_db():
    db_manager = DBManager()
    return db_manager.db


def _get_supervisor_by_uid(db, user_id: str) -> dict:
    """Look up registered supervisor by Firebase UID. Raises 404 if not found."""
    sup = db["supervisors"].find_one({"user_id": user_id})
    if not sup:
        raise HTTPException(
            status_code=404,
            detail="Bạn chưa có tài khoản Supervisor. Liên hệ admin để đăng ký.",
        )
    if not sup.get("is_active", True):
        raise HTTPException(
            status_code=403, detail="Tài khoản Supervisor đã bị vô hiệu hóa."
        )
    return sup


# ============================================================================
# Pydantic Models
# ============================================================================


class CreateManagedAffiliateRequest(BaseModel):
    code: str = Field(
        ..., description="Mã đại lý (uppercase, không dấu, không khoảng trắng)"
    )
    name: str = Field(..., description="Tên trung tâm hoặc đại lý")
    tier: int = Field(..., ge=1, le=2, description="1 = Trung tâm, 2 = Cộng tác viên")
    user_id: Optional[str] = Field(None, description="Firebase UID của đại lý (nếu có)")
    notes: Optional[str] = Field(None, description="Ghi chú nội bộ")
    bank_info: Optional[dict] = Field(None, description="Thông tin ngân hàng")


class UpdateManagedAffiliateRequest(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    user_id: Optional[str] = None
    notes: Optional[str] = None
    bank_info: Optional[dict] = None
    # Supervisor CANNOT change: code, tier, supervisor_id


class SupervisorWithdrawRequest(BaseModel):
    amount: int = Field(
        ..., ge=100_000, description="Số tiền rút (VND), tối thiểu 100,000"
    )
    bank_name: str = Field(..., description="Tên ngân hàng")
    bank_account_number: str = Field(..., description="Số tài khoản")
    bank_account_name: str = Field(..., description="Tên chủ tài khoản")
    notes: Optional[str] = Field(None, description="Ghi chú thêm")


# ============================================================================
# GET /me  — Supervisor dashboard
# ============================================================================


@router.get("/me")
async def get_supervisor_dashboard(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Return the authenticated supervisor's account details, balance summary,
    and managed affiliate stats.
    """
    sup = _get_supervisor_by_uid(db, current_user["uid"])

    # Count managed affiliates broken down by tier
    managed = list(
        db["affiliates"].find(
            {"supervisor_id": str(sup["_id"])},
            {"tier": 1, "is_active": 1},
        )
    )
    tier1_count = sum(1 for a in managed if a["tier"] == 1)
    tier2_count = sum(1 for a in managed if a["tier"] == 2)
    active_count = sum(1 for a in managed if a.get("is_active", True))

    return {
        "code": sup["code"],
        "name": sup.get("name", ""),
        "is_active": sup.get("is_active", True),
        "commission_rate": SUPERVISOR_COMMISSION_RATE,
        "balances": {
            "pending_balance": sup.get("pending_balance", 0),
            "available_balance": sup.get("available_balance", 0),
            "total_earned": sup.get("total_earned", 0),
        },
        "managed_affiliates": {
            "total": len(managed),
            "active": active_count,
            "tier_1_count": tier1_count,
            "tier_2_count": tier2_count,
        },
        "bank_info": sup.get("bank_info"),
        "created_at": (
            sup["created_at"].isoformat() if sup.get("created_at") else None
        ),
    }


# ============================================================================
# GET /affiliates  — List affiliates managed by this supervisor
# ============================================================================


@router.get("/affiliates")
async def list_managed_affiliates(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    tier: Optional[int] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    List all tier-1 and tier-2 affiliates created/managed by this supervisor.
    """
    sup = _get_supervisor_by_uid(db, current_user["uid"])
    supervisor_id = str(sup["_id"])

    query: dict = {"supervisor_id": supervisor_id}
    if tier is not None:
        query["tier"] = tier
    if is_active is not None:
        query["is_active"] = is_active

    total = db["affiliates"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["affiliates"].find(query).sort("created_at", -1).skip(skip).limit(page_size)
    )

    items = []
    for aff in docs:
        items.append(
            {
                "id": str(aff["_id"]),
                "code": aff["code"],
                "name": aff.get("name", ""),
                "tier": aff["tier"],
                "tier_label": TIER_LABELS.get(aff["tier"], ""),
                "is_active": aff.get("is_active", True),
                "user_id": aff.get("user_id"),
                "price_per_month": PRICING_TIERS.get(
                    f"tier_{aff['tier']}", PRICING_TIERS["no_code"]
                ),
                "commission_rate": AFFILIATE_COMMISSION_RATES.get(aff["tier"], 0),
                "pending_balance": aff.get("pending_balance", 0),
                "available_balance": aff.get("available_balance", 0),
                "total_earned": aff.get("total_earned", 0),
                "total_referred_users": aff.get("total_referred_users", 0),
                "bank_info": aff.get("bank_info"),
                "notes": aff.get("notes"),
                "created_at": (
                    aff["created_at"].isoformat() if aff.get("created_at") else None
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
# POST /affiliates  — Create new tier-1 / tier-2 under this supervisor
# ============================================================================


@router.post("/affiliates")
async def create_managed_affiliate(
    body: CreateManagedAffiliateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Create a new tier-1 or tier-2 affiliate account.
    The new affiliate is automatically linked to this supervisor.
    """
    sup = _get_supervisor_by_uid(db, current_user["uid"])

    code = re.sub(r"[^A-Z0-9]", "", body.code.upper())
    if not code:
        raise HTTPException(status_code=400, detail="Mã đại lý không hợp lệ.")

    if db["affiliates"].find_one({"code": code}):
        raise HTTPException(status_code=409, detail=f"Mã đại lý '{code}' đã tồn tại.")

    supervisor_id = str(sup["_id"])
    now = datetime.utcnow()
    doc = {
        "code": code,
        "name": body.name,
        "tier": body.tier,
        "is_active": True,
        "user_id": body.user_id,
        "supervisor_id": supervisor_id,
        "notes": body.notes,
        "bank_info": body.bank_info,
        "pending_balance": 0,
        "available_balance": 0,
        "total_earned": 0,
        "total_referred_users": 0,
        "created_at": now,
        "updated_at": now,
    }
    result = db["affiliates"].insert_one(doc)
    doc["_id"] = result.inserted_id

    # Increment supervisor managed count
    db["supervisors"].update_one(
        {"_id": sup["_id"]},
        {"$inc": {"total_managed_affiliates": 1}, "$set": {"updated_at": now}},
    )

    logger.info(
        f"🤝 Supervisor {sup['code']} created affiliate: code={code}, tier={body.tier}"
    )

    return {
        "message": "Tạo đại lý thành công.",
        "affiliate": {
            "id": str(doc["_id"]),
            "code": doc["code"],
            "name": doc["name"],
            "tier": doc["tier"],
            "tier_label": TIER_LABELS.get(doc["tier"], ""),
            "supervisor_id": supervisor_id,
            "supervisor_code": sup["code"],
        },
    }


# ============================================================================
# PUT /affiliates/{code}  — Update affiliate (supervisor scope only)
# ============================================================================


@router.put("/affiliates/{code}")
async def update_managed_affiliate(
    code: str,
    body: UpdateManagedAffiliateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Update a tier-1 or tier-2 affiliate that belongs to this supervisor.
    Supervisor cannot change: code, tier, supervisor_id.
    """
    sup = _get_supervisor_by_uid(db, current_user["uid"])
    supervisor_id = str(sup["_id"])

    aff = db["affiliates"].find_one({"code": code.upper()})
    if not aff:
        raise HTTPException(status_code=404, detail="Không tìm thấy đại lý.")

    # Ensure this affiliate belongs to this supervisor
    if aff.get("supervisor_id") != supervisor_id:
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền chỉnh sửa đại lý này.",
        )

    updates: dict = {"updated_at": datetime.utcnow()}
    if body.name is not None:
        updates["name"] = body.name
    if body.is_active is not None:
        updates["is_active"] = body.is_active
    if body.user_id is not None:
        updates["user_id"] = body.user_id
    if body.notes is not None:
        updates["notes"] = body.notes
    if body.bank_info is not None:
        updates["bank_info"] = body.bank_info

    db["affiliates"].update_one({"_id": aff["_id"]}, {"$set": updates})
    updated = db["affiliates"].find_one({"_id": aff["_id"]})

    return {
        "message": "Cập nhật đại lý thành công.",
        "affiliate": {
            "id": str(updated["_id"]),
            "code": updated["code"],
            "name": updated.get("name", ""),
            "tier": updated["tier"],
            "tier_label": TIER_LABELS.get(updated["tier"], ""),
            "is_active": updated.get("is_active", True),
            "user_id": updated.get("user_id"),
            "bank_info": updated.get("bank_info"),
            "notes": updated.get("notes"),
        },
    }


# ============================================================================
# GET /transactions  — Supervisor commission history
# ============================================================================


@router.get("/transactions")
async def get_supervisor_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(
        default=None, description="pending | paid | rejected"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    List this supervisor's commission transactions (10% from managed affiliates).
    """
    sup = _get_supervisor_by_uid(db, current_user["uid"])
    supervisor_id = str(sup["_id"])

    query: dict = {"supervisor_id": supervisor_id}
    if status:
        query["status"] = status

    total = db["supervisor_commissions"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["supervisor_commissions"]
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
                "affiliate_code": doc.get("affiliate_code"),
                "user_id": doc.get("user_id"),
                "subscription_id": doc.get("subscription_id"),
                "amount_paid_by_user": doc.get("amount_paid_by_user", 0),
                "commission_rate": doc.get("commission_rate", 0.10),
                "commission_amount": doc.get("commission_amount", 0),
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
async def supervisor_request_withdrawal(
    body: SupervisorWithdrawRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Submit a withdrawal request for supervisor's available balance.
    """
    sup = _get_supervisor_by_uid(db, current_user["uid"])

    available = sup.get("available_balance", 0)
    if body.amount > available:
        raise HTTPException(
            status_code=400,
            detail=f"Số dư khả dụng không đủ. Hiện có: {available:,} VND.",
        )

    # Check no pending withdrawal already exists
    existing_pending = db["supervisor_withdrawals"].find_one(
        {"supervisor_id": str(sup["_id"]), "status": "pending"}
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
        "supervisor_id": str(sup["_id"]),
        "supervisor_code": sup["code"],
        "amount": body.amount,
        "status": "pending",
        "bank_info": bank_info,
        "notes": body.notes,
        "created_at": now,
        "updated_at": now,
    }
    result = db["supervisor_withdrawals"].insert_one(doc)

    # Deduct from available_balance (hold until processed)
    db["supervisors"].update_one(
        {"_id": sup["_id"]},
        {
            "$inc": {"available_balance": -body.amount},
            "$set": {"updated_at": now},
        },
    )

    logger.info(
        f"💸 Supervisor withdrawal request: {sup['code']}, "
        f"amount={body.amount:,} VND, id={result.inserted_id}"
    )

    return {
        "withdrawal_id": str(result.inserted_id),
        "amount": body.amount,
        "status": "pending",
        "message": "Yêu cầu rút tiền đã được ghi nhận. Admin sẽ xử lý trong 1-3 ngày làm việc.",
        "bank_info": bank_info,
    }
