"""
Affiliate Admin API Routes

All endpoints require X-Service-Secret header (inter-service auth).

Endpoints:
- POST /api/v1/admin/affiliates                          — Create affiliate
- GET  /api/v1/admin/affiliates                          — List all affiliates
- GET  /api/v1/admin/affiliates/{code}                   — Get one affiliate
- PUT  /api/v1/admin/affiliates/{code}                   — Update affiliate
- GET  /api/v1/admin/affiliates/withdrawals              — List withdrawal requests
- POST /api/v1/admin/affiliates/withdrawals/{id}/approve — Approve withdrawal
- POST /api/v1/admin/affiliates/withdrawals/{id}/reject  — Reject withdrawal
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.database.db_manager import DBManager
from src.middleware.admin_auth import verify_admin
from src.models.conversation_subscription import (
    AFFILIATE_COMMISSION_RATES,
    PRICING_TIERS,
)
from src.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(
    prefix="/api/v1/admin/affiliates",
    tags=["Affiliate Admin"],
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


class CreateAffiliateRequest(BaseModel):
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
    supervisor_id: Optional[str] = Field(
        None, description="ObjectId string của Supervisor quản lý (nếu có)"
    )


class UpdateAffiliateRequest(BaseModel):
    name: Optional[str] = None
    tier: Optional[int] = Field(None, ge=1, le=2)
    is_active: Optional[bool] = None
    email: Optional[str] = Field(
        None, description="Cập nhật Gmail (UID reset, re-link lần đăng nhập tiếp)"
    )
    notes: Optional[str] = None
    bank_info: Optional[dict] = None
    supervisor_id: Optional[str] = Field(
        None, description="ObjectId string của Supervisor (đặt null để bỏ gán)"
    )


class ApproveWithdrawalRequest(BaseModel):
    notes: Optional[str] = Field(None, description="Ghi chú admin")


class RejectWithdrawalRequest(BaseModel):
    reason: str = Field(..., description="Lý do từ chối")


# ============================================================================
# Helpers
# ============================================================================


def fmt_affiliate(aff: dict) -> dict:
    return {
        "id": str(aff["_id"]),
        "code": aff["code"],
        "name": aff.get("name", ""),
        "tier": aff["tier"],
        "tier_label": TIER_LABELS.get(aff["tier"], ""),
        "is_active": aff.get("is_active", True),
        "login_status": "đã đăng nhập" if aff.get("user_id") else "chưa đăng nhập",
        "email": aff.get("email"),
        "user_id": aff.get("user_id"),
        "supervisor_id": aff.get("supervisor_id"),
        "price_per_month": PRICING_TIERS.get(
            f"tier_{aff['tier']}", PRICING_TIERS["no_code"]
        ),
        "commission_rate": AFFILIATE_COMMISSION_RATES.get(aff["tier"], 0),
        "pending_balance": aff.get("pending_balance", 0),
        "available_balance": aff.get("available_balance", 0),
        "total_earned": aff.get("total_earned", 0),
        "total_referred_users": aff.get("total_referred_users", 0),
        "notes": aff.get("notes"),
        "bank_info": aff.get("bank_info"),
        "created_at": aff["created_at"].isoformat() if aff.get("created_at") else None,
        "updated_at": aff["updated_at"].isoformat() if aff.get("updated_at") else None,
    }


# ============================================================================
# POST / — Create affiliate
# ============================================================================


@router.post("/")
async def create_affiliate(
    body: CreateAffiliateRequest,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    """Create a new affiliate account."""
    code = re.sub(r"[^A-Z0-9]", "", body.code.upper())
    if not code:
        raise HTTPException(status_code=400, detail="Mã đại lý không hợp lệ.")

    if db["affiliates"].find_one({"code": code}):
        raise HTTPException(status_code=409, detail=f"Mã đại lý '{code}' đã tồn tại.")

    # Validate supervisor_id if provided
    supervisor_id = None
    if body.supervisor_id:
        try:
            sup = db["supervisors"].find_one(
                {"_id": ObjectId(body.supervisor_id), "is_active": True}
            )
        except Exception:
            sup = None
        if not sup:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy Supervisor hoặc đã bị vô hiệu hóa.",
            )
        supervisor_id = body.supervisor_id

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

    # Increment supervisor's managed affiliate count
    if supervisor_id:
        db["supervisors"].update_one(
            {"_id": ObjectId(supervisor_id)},
            {"$inc": {"total_managed_affiliates": 1}, "$set": {"updated_at": now}},
        )

    logger.info(
        f"🤝 New affiliate created: code={code}, tier={body.tier}, supervisor_id={supervisor_id}"
    )

    return {
        "message": f"Tạo đại lý thành công.",
        "affiliate": fmt_affiliate(doc),
    }


# ============================================================================
# GET / — List affiliates
# ============================================================================


@router.get("/")
async def list_affiliates(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    tier: Optional[int] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    """List all affiliates with optional filters."""
    query: dict = {}
    if tier is not None:
        query["tier"] = tier
    if is_active is not None:
        query["is_active"] = is_active

    total = db["affiliates"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["affiliates"].find(query).sort("created_at", -1).skip(skip).limit(page_size)
    )

    return {
        "items": [fmt_affiliate(d) for d in docs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


# ============================================================================
# GET /{code}  — Get one affiliate
# ============================================================================


@router.get("/{code}")
async def get_affiliate(
    code: str,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    """Get details for a specific affiliate by code."""
    aff = db["affiliates"].find_one({"code": code.upper()})
    if not aff:
        raise HTTPException(status_code=404, detail="Không tìm thấy đại lý.")
    return fmt_affiliate(aff)


# ============================================================================
# PUT /{code}  — Update affiliate
# ============================================================================


@router.put("/{code}")
async def update_affiliate(
    code: str,
    body: UpdateAffiliateRequest,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    """Update affiliate details."""
    aff = db["affiliates"].find_one({"code": code.upper()})
    if not aff:
        raise HTTPException(status_code=404, detail="Không tìm thấy đại lý.")

    updates: dict = {"updated_at": datetime.utcnow()}
    if body.name is not None:
        updates["name"] = body.name
    if body.tier is not None:
        updates["tier"] = body.tier
    if body.is_active is not None:
        updates["is_active"] = body.is_active
    if body.email is not None:
        updates["email"] = body.email.strip().lower()
        updates["user_id"] = None  # Reset UID — re-linked on next login
    if body.notes is not None:
        updates["notes"] = body.notes
    if body.bank_info is not None:
        updates["bank_info"] = body.bank_info
    if body.supervisor_id is not None:
        # Validate new supervisor if a non-empty value is given
        if body.supervisor_id == "":
            updates["supervisor_id"] = None  # Unassign supervisor
        else:
            try:
                sup = db["supervisors"].find_one(
                    {"_id": ObjectId(body.supervisor_id), "is_active": True}
                )
            except Exception:
                sup = None
            if not sup:
                raise HTTPException(
                    status_code=404, detail="Không tìm thấy Supervisor."
                )
            updates["supervisor_id"] = body.supervisor_id
            # If changing supervisor, update managed counts
            old_sup_id = aff.get("supervisor_id")
            now_dt = updates["updated_at"]
            if old_sup_id and old_sup_id != body.supervisor_id:
                try:
                    db["supervisors"].update_one(
                        {"_id": ObjectId(old_sup_id)},
                        {
                            "$inc": {"total_managed_affiliates": -1},
                            "$set": {"updated_at": now_dt},
                        },
                    )
                except Exception:
                    pass
            if not old_sup_id or old_sup_id != body.supervisor_id:
                db["supervisors"].update_one(
                    {"_id": ObjectId(body.supervisor_id)},
                    {
                        "$inc": {"total_managed_affiliates": 1},
                        "$set": {"updated_at": now_dt},
                    },
                )

    db["affiliates"].update_one({"_id": aff["_id"]}, {"$set": updates})
    updated = db["affiliates"].find_one({"_id": aff["_id"]})

    return {"message": "Cập nhật thành công.", "affiliate": fmt_affiliate(updated)}


# ============================================================================
# GET /withdrawals  — List withdrawal requests (route must be before /{code})
# ============================================================================


@router.get("/withdrawals/list")
async def list_withdrawals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    status: Optional[str] = Query(
        default=None, description="pending | approved | rejected | paid"
    ),
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    """List all withdrawal requests across all affiliates."""
    query: dict = {}
    if status:
        query["status"] = status

    total = db["affiliate_withdrawals"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["affiliate_withdrawals"]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )

    items = []
    for doc in docs:
        # Enrich with affiliate code + name
        aff = None
        if doc.get("affiliate_id"):
            try:
                aff = db["affiliates"].find_one(
                    {"_id": ObjectId(doc["affiliate_id"])},
                    {"code": 1, "name": 1, "tier": 1},
                )
            except Exception:
                pass

        items.append(
            {
                "id": str(doc["_id"]),
                "affiliate_id": doc.get("affiliate_id"),
                "affiliate_code": aff["code"] if aff else None,
                "affiliate_name": aff["name"] if aff else None,
                "user_id": doc.get("user_id"),
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
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


# ============================================================================
# POST /withdrawals/{id}/approve
# ============================================================================


@router.post("/withdrawals/{withdrawal_id}/approve")
async def approve_withdrawal(
    withdrawal_id: str,
    body: ApproveWithdrawalRequest,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    """Approve a withdrawal request — marks commission as paid."""
    try:
        oid = ObjectId(withdrawal_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID không hợp lệ.")

    doc = db["affiliate_withdrawals"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu rút tiền.")
    if doc["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Yêu cầu đã ở trạng thái '{doc['status']}', không thể duyệt lại.",
        )

    now = datetime.utcnow()

    db["affiliate_withdrawals"].update_one(
        {"_id": oid},
        {
            "$set": {
                "status": "paid",
                "admin_notes": body.notes,
                "processed_at": now,
                "updated_at": now,
            }
        },
    )

    # Update commission records linked to this withdrawal
    db["affiliate_commissions"].update_many(
        {"affiliate_id": doc["affiliate_id"], "status": "pending"},
        {"$set": {"status": "paid", "updated_at": now}},
    )

    # Reduce pending_balance & total_earned stays unchanged (already tracked)
    db["affiliates"].update_one(
        {"_id": ObjectId(doc["affiliate_id"])},
        {
            "$inc": {"pending_balance": -doc["amount"]},
            "$set": {"updated_at": now},
        },
    )

    logger.info(
        f"✅ Withdrawal approved: id={withdrawal_id}, amount={doc['amount']:,} VND"
    )

    return {
        "message": "Đã duyệt yêu cầu rút tiền.",
        "withdrawal_id": withdrawal_id,
        "amount": doc["amount"],
        "status": "paid",
    }


# ============================================================================
# POST /withdrawals/{id}/reject
# ============================================================================


@router.post("/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(
    withdrawal_id: str,
    body: RejectWithdrawalRequest,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    """Reject a withdrawal request — refunds the held balance back to available."""
    try:
        oid = ObjectId(withdrawal_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID không hợp lệ.")

    doc = db["affiliate_withdrawals"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu rút tiền.")
    if doc["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Yêu cầu đã ở trạng thái '{doc['status']}', không thể từ chối.",
        )

    now = datetime.utcnow()

    db["affiliate_withdrawals"].update_one(
        {"_id": oid},
        {
            "$set": {
                "status": "rejected",
                "rejection_reason": body.reason,
                "processed_at": now,
                "updated_at": now,
            }
        },
    )

    # Refund the held amount back to available_balance
    db["affiliates"].update_one(
        {"_id": ObjectId(doc["affiliate_id"])},
        {
            "$inc": {"available_balance": doc["amount"]},
            "$set": {"updated_at": now},
        },
    )

    logger.info(f"❌ Withdrawal rejected: id={withdrawal_id}, reason={body.reason}")

    return {
        "message": "Đã từ chối yêu cầu rút tiền. Số dư đã được hoàn trả.",
        "withdrawal_id": withdrawal_id,
        "reason": body.reason,
        "status": "rejected",
    }
