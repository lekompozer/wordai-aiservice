"""
AI Bundle Supervisor Routes

Mirrors src/api/supervisor_routes.py but uses ai_bundle_* collections.

Endpoints:
- GET  /api/v1/ai-bundle/supervisor/me                     — Dashboard
- GET  /api/v1/ai-bundle/supervisor/affiliates             — List managed affiliates
- POST /api/v1/ai-bundle/supervisor/affiliates             — Create new affiliate
- PUT  /api/v1/ai-bundle/supervisor/affiliates/{code}      — Update affiliate
- GET  /api/v1/ai-bundle/supervisor/transactions           — Commission history
- GET  /api/v1/ai-bundle/supervisor/withdrawals            — Withdrawal list
- POST /api/v1/ai-bundle/supervisor/withdraw               — Request withdrawal
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.models.ai_bundle_subscription import (
    AFFILIATE_COMMISSION_RATES,
    SUPERVISOR_COMMISSION_RATE,
    get_price,
)
from src.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(
    prefix="/api/v1/ai-bundle/supervisor",
    tags=["AI Bundle Supervisor"],
)

TIER_LABELS = {
    1: "Đại lý cấp 1 (Trung tâm)",
    2: "Đại lý cấp 2 (Cộng tác viên)",
}


def get_db():
    db_manager = DBManager()
    return db_manager.db


def _get_ai_bundle_supervisor(db, user_id: str, email: str = None) -> dict:
    """Look up ai_bundle_supervisors by Firebase UID with email auto-link."""
    sup = db["ai_bundle_supervisors"].find_one({"user_id": user_id})

    if not sup and email:
        sup = db["ai_bundle_supervisors"].find_one({"email": email.lower()})
        if sup:
            db["ai_bundle_supervisors"].update_one(
                {"_id": sup["_id"]},
                {"$set": {"user_id": user_id, "updated_at": datetime.utcnow()}},
            )
            sup["user_id"] = user_id
            logger.info(
                f"🔗 [AI Bundle] Supervisor {sup['code']} UID linked: "
                f"email={email} uid={user_id}"
            )

    if not sup:
        raise HTTPException(
            status_code=404,
            detail="Bạn chưa có tài khoản Supervisor AI Bundle. Liên hệ admin để đăng ký.",
        )
    if not sup.get("is_active", True):
        raise HTTPException(
            status_code=403, detail="Tài khoản Supervisor AI Bundle đã bị vô hiệu hóa."
        )
    return sup


# ============================================================================
# Pydantic Models
# ============================================================================


class CreateManagedAffiliateRequest(BaseModel):
    code: str = Field(..., description="Mã đại lý (uppercase)")
    name: str = Field(..., description="Tên trung tâm hoặc đại lý")
    tier: int = Field(..., ge=1, le=2)
    email: Optional[str] = Field(None)
    notes: Optional[str] = Field(None)
    bank_info: Optional[dict] = Field(None)


class UpdateManagedAffiliateRequest(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    bank_info: Optional[dict] = None


class SupervisorWithdrawRequest(BaseModel):
    amount: int = Field(..., ge=100_000)
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_account_name: Optional[str] = None
    notes: Optional[str] = None


# ============================================================================
# GET /me  — Dashboard
# ============================================================================


@router.get("/me")
async def get_ai_bundle_supervisor_dashboard(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    sup = _get_ai_bundle_supervisor(
        db, current_user["uid"], email=current_user.get("email")
    )

    managed = list(
        db["ai_bundle_affiliates"].find(
            {"supervisor_id": str(sup["_id"])},
            {"tier": 1, "is_active": 1, "code": 1},
        )
    )
    tier1_count = sum(1 for a in managed if a["tier"] == 1)
    tier2_count = sum(1 for a in managed if a["tier"] == 2)
    active_count = sum(1 for a in managed if a.get("is_active", True))

    total_customers = (
        db["payments"].count_documents(
            {
                "affiliate_code": {"$in": [a["code"] for a in managed]},
                "plan_type": "ai_bundle",
                "status": "completed",
            }
        )
        if managed
        else 0
    )

    pending_wd_agg = list(
        db["ai_bundle_supervisor_withdrawals"].aggregate(
            [
                {"$match": {"supervisor_id": str(sup["_id"]), "status": "pending"}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]
        )
    )
    approved_wd_agg = list(
        db["ai_bundle_supervisor_withdrawals"].aggregate(
            [
                {
                    "$match": {
                        "supervisor_id": str(sup["_id"]),
                        "status": {"$in": ["approved", "paid"]},
                    }
                },
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
        "total_customers": total_customers,
        "total_affiliates": len(managed),
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
# GET /affiliates  — List managed affiliates
# ============================================================================


@router.get("/affiliates")
async def list_ai_bundle_managed_affiliates(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    tier: Optional[int] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    sup = _get_ai_bundle_supervisor(
        db, current_user["uid"], email=current_user.get("email")
    )
    supervisor_id = str(sup["_id"])

    query: dict = {"supervisor_id": supervisor_id}
    if tier is not None:
        query["tier"] = tier
    if is_active is not None:
        query["is_active"] = is_active

    total = db["ai_bundle_affiliates"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["ai_bundle_affiliates"]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )

    items = [
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
            "commission_rate": AFFILIATE_COMMISSION_RATES.get(aff["tier"], 0),
            "total_earned": aff.get("total_earned", 0),
            "total_referred_users": aff.get("total_referred_users", 0),
            "bank_info": aff.get("bank_info"),
            "notes": aff.get("notes"),
            "created_at": (
                aff["created_at"].isoformat() if aff.get("created_at") else None
            ),
        }
        for aff in docs
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


# ============================================================================
# POST /affiliates  — Create new affiliate under this supervisor
# ============================================================================


@router.post("/affiliates")
async def create_ai_bundle_managed_affiliate(
    body: CreateManagedAffiliateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    sup = _get_ai_bundle_supervisor(
        db, current_user["uid"], email=current_user.get("email")
    )

    code = re.sub(r"[^A-Z0-9]", "", body.code.upper())
    if not code:
        raise HTTPException(status_code=400, detail="Mã đại lý không hợp lệ.")

    if db["ai_bundle_affiliates"].find_one({"code": code}):
        raise HTTPException(
            status_code=409, detail=f"Mã đại lý AI Bundle '{code}' đã tồn tại."
        )

    supervisor_id = str(sup["_id"])
    email = body.email.strip().lower() if body.email else None
    now = datetime.utcnow()

    doc = {
        "code": code,
        "name": body.name,
        "tier": body.tier,
        "is_active": True,
        "email": email,
        "user_id": None,
        "supervisor_id": supervisor_id,
        "notes": body.notes,
        "bank_info": body.bank_info,
        "total_earned": 0,
        "total_referred_users": 0,
        "created_at": now,
        "updated_at": now,
    }
    result = db["ai_bundle_affiliates"].insert_one(doc)

    db["ai_bundle_supervisors"].update_one(
        {"_id": sup["_id"]},
        {"$inc": {"total_managed_affiliates": 1}, "$set": {"updated_at": now}},
    )

    logger.info(
        f"🤝 [AI Bundle] Supervisor {sup['code']} created affiliate: "
        f"code={code}, tier={body.tier}"
    )

    return {
        "message": "Tạo đại lý AI Bundle thành công.",
        "affiliate": {
            "id": str(result.inserted_id),
            "code": code,
            "name": body.name,
            "tier": body.tier,
            "tier_label": TIER_LABELS.get(body.tier, ""),
            "supervisor_id": supervisor_id,
            "supervisor_code": sup["code"],
        },
    }


# ============================================================================
# PUT /affiliates/{code}  — Update affiliate
# ============================================================================


@router.put("/affiliates/{code}")
async def update_ai_bundle_managed_affiliate(
    code: str,
    body: UpdateManagedAffiliateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    sup = _get_ai_bundle_supervisor(
        db, current_user["uid"], email=current_user.get("email")
    )
    supervisor_id = str(sup["_id"])

    aff = db["ai_bundle_affiliates"].find_one({"code": code.upper()})
    if not aff:
        raise HTTPException(status_code=404, detail="Không tìm thấy đại lý AI Bundle.")
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
        updates["user_id"] = None  # Force re-link via email next login
    if body.notes is not None:
        updates["notes"] = body.notes
    if body.bank_info is not None:
        updates["bank_info"] = body.bank_info

    db["ai_bundle_affiliates"].update_one({"_id": aff["_id"]}, {"$set": updates})

    return {"message": "Cập nhật đại lý AI Bundle thành công.", "code": code.upper()}


# ============================================================================
# GET /transactions  — Commission history
# ============================================================================


@router.get("/transactions")
async def get_ai_bundle_supervisor_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    sup = _get_ai_bundle_supervisor(
        db, current_user["uid"], email=current_user.get("email")
    )

    query = {"supervisor_id": str(sup["_id"])}
    total = db["ai_bundle_supervisor_commissions"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["ai_bundle_supervisor_commissions"]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )

    items = [
        {
            "id": str(doc["_id"]),
            "affiliate_code": doc.get("affiliate_code"),
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
async def get_ai_bundle_supervisor_withdrawals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    sup = _get_ai_bundle_supervisor(
        db, current_user["uid"], email=current_user.get("email")
    )

    query = {"supervisor_id": str(sup["_id"])}
    total = db["ai_bundle_supervisor_withdrawals"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["ai_bundle_supervisor_withdrawals"]
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
async def request_ai_bundle_supervisor_withdrawal(
    body: SupervisorWithdrawRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    sup = _get_ai_bundle_supervisor(
        db, current_user["uid"], email=current_user.get("email")
    )

    pending_wd_agg = list(
        db["ai_bundle_supervisor_withdrawals"].aggregate(
            [
                {"$match": {"supervisor_id": str(sup["_id"]), "status": "pending"}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]
        )
    )
    approved_wd_agg = list(
        db["ai_bundle_supervisor_withdrawals"].aggregate(
            [
                {
                    "$match": {
                        "supervisor_id": str(sup["_id"]),
                        "status": {"$in": ["approved", "paid"]},
                    }
                },
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]
        )
    )
    pending_amt = pending_wd_agg[0]["total"] if pending_wd_agg else 0
    total_withdrawn = approved_wd_agg[0]["total"] if approved_wd_agg else 0
    available = max(0, sup.get("total_earned", 0) - total_withdrawn - pending_amt)

    if body.amount > available:
        raise HTTPException(
            status_code=400,
            detail=f"Số dư khả dụng không đủ. Hiện có: {available:,} VND.",
        )

    existing_pending = db["ai_bundle_supervisor_withdrawals"].find_one(
        {"supervisor_id": str(sup["_id"]), "status": "pending"}
    )
    if existing_pending:
        raise HTTPException(
            status_code=400,
            detail="Bạn đang có yêu cầu rút tiền đang chờ xử lý.",
        )

    saved_bank = sup.get("bank_info") or {}
    bank_name = body.bank_name or saved_bank.get("bank_name")
    bank_account_number = body.bank_account_number or saved_bank.get("account_number")
    bank_account_name = body.bank_account_name or saved_bank.get("account_name")

    if not (bank_name and bank_account_number and bank_account_name):
        raise HTTPException(
            status_code=400,
            detail="Vui lòng cung cấp thông tin ngân hàng.",
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
        "user_id": current_user["uid"],
        "amount": body.amount,
        "status": "pending",
        "bank_info": bank_info,
        "notes": body.notes,
        "created_at": now,
        "updated_at": now,
    }
    result = db["ai_bundle_supervisor_withdrawals"].insert_one(doc)

    db["ai_bundle_supervisors"].update_one(
        {"_id": sup["_id"]},
        {"$set": {"bank_info": bank_info, "updated_at": now}},
    )

    return {
        "withdrawal_id": str(result.inserted_id),
        "amount": body.amount,
        "status": "pending",
        "message": "Yêu cầu rút tiền đã được ghi nhận. Admin sẽ xử lý trong 1-3 ngày làm việc.",
    }
