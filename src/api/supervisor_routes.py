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


def _get_supervisor_by_uid(db, user_id: str, email: str = None) -> dict:
    """Look up supervisor by Firebase UID.
    If not found by UID, fall back to email lookup and auto-link UID on first login.
    """
    # 1. Fast path: already linked
    sup = db["supervisors"].find_one({"user_id": user_id})

    # 2. First-time login: look up by email, then link UID
    if not sup and email:
        sup = db["supervisors"].find_one({"email": email.lower()})
        if sup:
            db["supervisors"].update_one(
                {"_id": sup["_id"]},
                {"$set": {"user_id": user_id, "updated_at": datetime.utcnow()}},
            )
            sup["user_id"] = user_id
            logger.info(
                f"🔗 Supervisor {sup['code']} UID linked: email={email} uid={user_id}"
            )

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
    email: Optional[str] = Field(
        None,
        description="Gmail của đại lý. UID tự được link khi đại lý đăng nhập lần đầu.",
    )
    notes: Optional[str] = Field(None, description="Ghi chú nội bộ")
    bank_info: Optional[dict] = Field(None, description="Thông tin ngân hàng")


class UpdateManagedAffiliateRequest(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    email: Optional[str] = Field(
        None, description="Cập nhật Gmail (UID reset, re-link lần đăng nhập tiếp)"
    )
    notes: Optional[str] = None
    bank_info: Optional[dict] = None
    # Supervisor CANNOT change: code, tier, supervisor_id


class SupervisorWithdrawRequest(BaseModel):
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
    sup = _get_supervisor_by_uid(
        db, current_user["uid"], email=current_user.get("email")
    )

    # Count managed affiliates broken down by tier
    managed = list(
        db["affiliates"].find(
            {"supervisor_id": str(sup["_id"])},
            {"tier": 1, "is_active": 1, "code": 1},
        )
    )
    tier1_count = sum(1 for a in managed if a["tier"] == 1)
    tier2_count = sum(1 for a in managed if a["tier"] == 2)
    active_count = sum(1 for a in managed if a.get("is_active", True))

    # Count total unique students across all managed affiliates
    total_students = (
        db["payments"].count_documents(
            {
                "affiliate_code": {
                    "$in": [a["code"] for a in managed] if managed else []
                },
                "plan_type": "conversation_learning",
                "status": "completed",
            }
        )
        if managed
        else 0
    )

    # Compute dynamic balances from withdrawal records
    pending_wd_agg = list(
        db["supervisor_withdrawals"].aggregate(
            [
                {"$match": {"supervisor_id": str(sup["_id"]), "status": "pending"}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]
        )
    )
    approved_wd_agg = list(
        db["supervisor_withdrawals"].aggregate(
            [
                {"$match": {"supervisor_id": str(sup["_id"]), "status": "approved"}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]
        )
    )
    pending_withdrawal_amount = pending_wd_agg[0]["total"] if pending_wd_agg else 0
    total_withdrawn = approved_wd_agg[0]["total"] if approved_wd_agg else 0
    total_earned = sup.get("total_earned", 0)
    available_balance = max(
        0, total_earned - total_withdrawn - pending_withdrawal_amount
    )

    return {
        "code": sup["code"],
        "name": sup.get("name", ""),
        "email": sup.get("email"),
        "is_active": sup.get("is_active", True),
        "commission_rate": SUPERVISOR_COMMISSION_RATE,
        "total_students": total_students,
        # Flat fields (read directly by frontend)
        "total_affiliates": len(managed),
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
@router.get("/affiliates/")
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
    sup = _get_supervisor_by_uid(
        db, current_user["uid"], email=current_user.get("email")
    )
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
                "login_status": (
                    "đã đăng nhập" if aff.get("user_id") else "chưa đăng nhập"
                ),
                "email": aff.get("email"),
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
@router.post("/affiliates/")
async def create_managed_affiliate(
    body: CreateManagedAffiliateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Create a new tier-1 or tier-2 affiliate account.
    The new affiliate is automatically linked to this supervisor.
    """
    sup = _get_supervisor_by_uid(
        db, current_user["uid"], email=current_user.get("email")
    )

    code = re.sub(r"[^A-Z0-9]", "", body.code.upper())
    if not code:
        raise HTTPException(status_code=400, detail="Mã đại lý không hợp lệ.")

    if db["affiliates"].find_one({"code": code}):
        raise HTTPException(status_code=409, detail=f"Mã đại lý '{code}' đã tồn tại.")

    supervisor_id = str(sup["_id"])
    email = body.email.strip().lower() if body.email else None
    now = datetime.utcnow()
    doc = {
        "code": code,
        "name": body.name,
        "tier": body.tier,
        "is_active": True,
        "email": email,
        "user_id": None,  # Auto-linked on first login
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
@router.put("/affiliates/{code}/")
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
    sup = _get_supervisor_by_uid(
        db, current_user["uid"], email=current_user.get("email")
    )
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
    if body.email is not None:
        updates["email"] = body.email.strip().lower()
        updates["user_id"] = None  # Reset UID — re-linked on next login
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
            "email": updated.get("email"),
            "user_id": updated.get("user_id"),
            "bank_info": updated.get("bank_info"),
            "notes": updated.get("notes"),
        },
    }


# ============================================================================
# GET /students  — All students enrolled via any affiliate under this supervisor
# ============================================================================


@router.get("/students")
async def get_supervisor_students(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    affiliate_code: Optional[str] = Query(
        default=None, description="Filter by specific affiliate code"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    List all students enrolled via any affiliate managed by this supervisor.
    Includes user email, student_id, which affiliate they used, package, amount, date.
    """
    sup = _get_supervisor_by_uid(
        db, current_user["uid"], email=current_user.get("email")
    )
    supervisor_id = str(sup["_id"])

    # Get all affiliate codes under this supervisor
    managed_affiliates = list(
        db["affiliates"].find(
            {"supervisor_id": supervisor_id},
            {"code": 1, "name": 1, "tier": 1},
        )
    )
    managed_codes = [a["code"] for a in managed_affiliates]
    aff_map = {a["code"]: a for a in managed_affiliates}

    if not managed_codes:
        return {
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 1,
        }

    query: dict = {
        "affiliate_code": {
            "$in": [affiliate_code.upper()] if affiliate_code else managed_codes
        },
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
        sub = db["user_conversation_subscription"].find_one(
            {"order_invoice_number": doc.get("order_invoice_number")},
            {"is_active": 1, "end_date": 1},
        )
        aff_code = doc.get("affiliate_code", "")
        aff_info = aff_map.get(aff_code, {})
        items.append(
            {
                "user_id": doc.get("user_id"),
                "user_email": doc.get("user_email"),
                "user_name": doc.get("user_name"),
                "student_id": doc.get("student_id"),
                "affiliate_code": aff_code,
                "affiliate_name": aff_info.get("name", ""),
                "affiliate_tier": aff_info.get("tier"),
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
        "managed_affiliate_codes": managed_codes,
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
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
    sup = _get_supervisor_by_uid(
        db, current_user["uid"], email=current_user.get("email")
    )
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
# GET /withdrawals  — List my withdrawal requests
# ============================================================================


@router.get("/withdrawals")
async def get_supervisor_withdrawals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    List withdrawal requests submitted by this supervisor (newest first).
    """
    sup = _get_supervisor_by_uid(
        db, current_user["uid"], email=current_user.get("email")
    )

    query = {"supervisor_id": str(sup["_id"])}
    total = db["supervisor_withdrawals"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["supervisor_withdrawals"]
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
async def supervisor_request_withdrawal(
    body: SupervisorWithdrawRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Submit a withdrawal request for supervisor's available balance.
    Bank info is optional if already saved to profile; new info will be saved.
    """
    sup = _get_supervisor_by_uid(
        db, current_user["uid"], email=current_user.get("email")
    )

    # Compute available balance dynamically (earned - withdrawn - pending requests)
    pending_wd_agg = list(
        db["supervisor_withdrawals"].aggregate(
            [
                {"$match": {"supervisor_id": str(sup["_id"]), "status": "pending"}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]
        )
    )
    approved_wd_agg_w = list(
        db["supervisor_withdrawals"].aggregate(
            [
                {"$match": {"supervisor_id": str(sup["_id"]), "status": "approved"}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]
        )
    )
    pending_wd_amt = pending_wd_agg[0]["total"] if pending_wd_agg else 0
    total_withdrawn_w = approved_wd_agg_w[0]["total"] if approved_wd_agg_w else 0
    available = max(0, sup.get("total_earned", 0) - total_withdrawn_w - pending_wd_amt)

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

    # Resolve bank info: use body fields or fall back to saved profile
    saved_bank = sup.get("bank_info") or {}
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

    # Save bank info to profile for convenience on next withdrawal
    db["supervisors"].update_one(
        {"_id": sup["_id"]},
        {"$set": {"bank_info": bank_info, "updated_at": now}},
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
