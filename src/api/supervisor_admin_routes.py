"""
Supervisor Admin API Routes

All endpoints require X-Service-Secret header (inter-service auth).
Only Admin (partners.wordai.pro) can create supervisor accounts.

Endpoints:
- POST /api/v1/admin/supervisors                               — Create supervisor
- GET  /api/v1/admin/supervisors                               — List all supervisors
- GET  /api/v1/admin/supervisors/{code}                        — Get one supervisor
- PUT  /api/v1/admin/supervisors/{code}                        — Update supervisor
- GET  /api/v1/admin/supervisors/withdrawals/list              — List withdrawal requests
- POST /api/v1/admin/supervisors/withdrawals/{id}/approve      — Approve withdrawal
- POST /api/v1/admin/supervisors/withdrawals/{id}/reject       — Reject withdrawal
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.database.db_manager import DBManager
from src.middleware.admin_auth import verify_admin
from src.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(
    prefix="/api/v1/admin/supervisors",
    tags=["Supervisor Admin"],
)


def get_db():
    db_manager = DBManager()
    return db_manager.db


# ============================================================================
# Pydantic Models
# ============================================================================


class CreateSupervisorRequest(BaseModel):
    code: str = Field(
        ..., description="Mã Supervisor (uppercase, không dấu, không khoảng trắng)"
    )
    name: str = Field(..., description="Tên công ty / cá nhân Supervisor")
    email: str = Field(
        ...,
        description="Gmail của Supervisor. Hệ thống tự link Firebase UID khi supervisor đăng nhập lần đầu.",
    )
    notes: Optional[str] = Field(None, description="Ghi chú nội bộ")
    bank_info: Optional[dict] = Field(None, description="Thông tin ngân hàng")


class UpdateSupervisorRequest(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    email: Optional[str] = Field(
        None,
        description="Cập nhật Gmail (UID sẽ được link lại lần đăng nhập tiếp theo)",
    )
    notes: Optional[str] = None
    bank_info: Optional[dict] = None


class ApproveWithdrawalRequest(BaseModel):
    notes: Optional[str] = Field(None, description="Ghi chú admin")


class RejectWithdrawalRequest(BaseModel):
    reason: str = Field(..., description="Lý do từ chối")


# ============================================================================
# Helpers
# ============================================================================


def fmt_supervisor(sup: dict) -> dict:
    return {
        "id": str(sup["_id"]),
        "code": sup["code"],
        "name": sup.get("name", ""),
        "is_active": sup.get("is_active", True),
        "login_status": "đã đăng nhập" if sup.get("user_id") else "chưa đăng nhập",
        "email": sup.get("email"),
        "user_id": sup.get("user_id"),
        "notes": sup.get("notes"),
        "bank_info": sup.get("bank_info"),
        "pending_balance": sup.get("pending_balance", 0),
        "available_balance": sup.get("available_balance", 0),
        "total_earned": sup.get("total_earned", 0),
        "total_managed_affiliates": sup.get("total_managed_affiliates", 0),
        "created_at": sup["created_at"].isoformat() if sup.get("created_at") else None,
        "updated_at": sup["updated_at"].isoformat() if sup.get("updated_at") else None,
    }


# ============================================================================
# POST / — Create supervisor
# ============================================================================


@router.post("/")
async def create_supervisor(
    body: CreateSupervisorRequest,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    """Create a new supervisor account by email only.
    Firebase UID will be auto-linked when the supervisor logs in for the first time.
    """
    code = re.sub(r"[^A-Z0-9_]", "", body.code.upper())
    if not code:
        raise HTTPException(status_code=400, detail="Mã Supervisor không hợp lệ.")

    email = body.email.strip().lower()

    if db["supervisors"].find_one({"code": code}):
        raise HTTPException(
            status_code=409, detail=f"Mã Supervisor '{code}' đã tồn tại."
        )

    if db["supervisors"].find_one({"email": email}):
        raise HTTPException(
            status_code=409,
            detail=f"Email '{email}' đã được gán cho một Supervisor khác.",
        )

    now = datetime.utcnow()
    doc = {
        "code": code,
        "name": body.name,
        "is_active": True,
        "email": email,
        "user_id": None,  # Will be linked automatically on first login
        "notes": body.notes,
        "bank_info": body.bank_info,
        "pending_balance": 0,
        "available_balance": 0,
        "total_earned": 0,
        "total_managed_affiliates": 0,
        "created_at": now,
        "updated_at": now,
    }
    result = db["supervisors"].insert_one(doc)
    doc["_id"] = result.inserted_id

    logger.info(
        f"👑 New supervisor created: code={code}, name={body.name}, email={email}"
    )

    return {
        "message": "Tạo Supervisor thành công.",
        "supervisor": fmt_supervisor(doc),
    }


# ============================================================================
# GET / — List supervisors
# ============================================================================


@router.get("/")
async def list_supervisors(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    is_active: Optional[bool] = Query(default=None),
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    """List all supervisor accounts."""
    query: dict = {}
    if is_active is not None:
        query["is_active"] = is_active

    total = db["supervisors"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["supervisors"].find(query).sort("created_at", -1).skip(skip).limit(page_size)
    )

    return {
        "items": [fmt_supervisor(d) for d in docs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


# ============================================================================
# GET /withdrawals/list — Must be BEFORE /{code}
# ============================================================================


@router.get("/withdrawals/list")
async def list_supervisor_withdrawals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    status: Optional[str] = Query(
        default=None, description="pending | paid | rejected"
    ),
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    """List all supervisor withdrawal requests."""
    query: dict = {}
    if status:
        query["status"] = status

    total = db["supervisor_withdrawals"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["supervisor_withdrawals"]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )

    items = []
    for doc in docs:
        item: Dict[str, Any] = {
            "id": str(doc["_id"]),
            "supervisor_id": doc.get("supervisor_id"),
            "supervisor_code": doc.get("supervisor_code"),
            "amount": doc.get("amount", 0),
            "status": doc.get("status"),
            "bank_info": doc.get("bank_info"),
            "notes": doc.get("notes"),
            "created_at": (
                doc["created_at"].isoformat() if doc.get("created_at") else None
            ),
            "updated_at": (
                doc["updated_at"].isoformat() if doc.get("updated_at") else None
            ),
        }
        items.append(item)

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
async def approve_supervisor_withdrawal(
    withdrawal_id: str,
    body: ApproveWithdrawalRequest,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    """Approve a supervisor withdrawal request."""
    try:
        wd_oid = ObjectId(withdrawal_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID không hợp lệ.")

    wd = db["supervisor_withdrawals"].find_one({"_id": wd_oid})
    if not wd:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu rút tiền.")
    if wd["status"] != "pending":
        raise HTTPException(
            status_code=409, detail=f"Yêu cầu đã ở trạng thái '{wd['status']}'."
        )

    now = datetime.utcnow()
    amount = wd["amount"]
    supervisor_id = wd["supervisor_id"]

    db["supervisor_withdrawals"].update_one(
        {"_id": wd_oid},
        {"$set": {"status": "paid", "notes": body.notes, "updated_at": now}},
    )

    # Mark related supervisor_commissions as paid
    db["supervisor_commissions"].update_many(
        {"supervisor_id": supervisor_id, "status": "pending"},
        {"$set": {"status": "paid"}},
    )

    # Deduct from pending_balance (available_balance already deducted on withdraw request)
    try:
        db["supervisors"].update_one(
            {"_id": ObjectId(supervisor_id)},
            {
                "$inc": {"pending_balance": -amount},
                "$set": {"updated_at": now},
            },
        )
    except Exception:
        pass

    logger.info(f"✅ Supervisor withdrawal approved: {withdrawal_id}, amount={amount}")

    return {
        "message": "Đã duyệt yêu cầu rút tiền Supervisor.",
        "withdrawal_id": withdrawal_id,
    }


# ============================================================================
# POST /withdrawals/{id}/reject
# ============================================================================


@router.post("/withdrawals/{withdrawal_id}/reject")
async def reject_supervisor_withdrawal(
    withdrawal_id: str,
    body: RejectWithdrawalRequest,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    """Reject a supervisor withdrawal request and refund available balance."""
    try:
        wd_oid = ObjectId(withdrawal_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID không hợp lệ.")

    wd = db["supervisor_withdrawals"].find_one({"_id": wd_oid})
    if not wd:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu rút tiền.")
    if wd["status"] != "pending":
        raise HTTPException(
            status_code=409, detail=f"Yêu cầu đã ở trạng thái '{wd['status']}'."
        )

    now = datetime.utcnow()
    amount = wd["amount"]
    supervisor_id = wd["supervisor_id"]

    db["supervisor_withdrawals"].update_one(
        {"_id": wd_oid},
        {"$set": {"status": "rejected", "notes": body.reason, "processed_at": now, "updated_at": now}},
    )

    # Note: available_balance is computed dynamically (pending_balance - pending_withdrawals)
    # No DB balance update needed — rejected record is excluded from pending sum automatically

    logger.info(
        f"❌ Supervisor withdrawal rejected: {withdrawal_id}, reason={body.reason}"
    )

    return {
        "message": "Đã từ chối yêu cầu rút tiền Supervisor.",
        "withdrawal_id": withdrawal_id,
    }


# ============================================================================
# GET /{code}  — Get one supervisor  (must be after static routes)
# ============================================================================


@router.get("/{code}")
async def get_supervisor(
    code: str,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    """Get one supervisor by code."""
    sup = db["supervisors"].find_one({"code": code.upper()})
    if not sup:
        raise HTTPException(status_code=404, detail="Không tìm thấy Supervisor.")
    return fmt_supervisor(sup)


# ============================================================================
# PUT /{code}  — Update supervisor
# ============================================================================


@router.put("/{code}")
async def update_supervisor(
    code: str,
    body: UpdateSupervisorRequest,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    """Update supervisor details."""
    sup = db["supervisors"].find_one({"code": code.upper()})
    if not sup:
        raise HTTPException(status_code=404, detail="Không tìm thấy Supervisor.")

    updates: dict = {"updated_at": datetime.utcnow()}
    if body.name is not None:
        updates["name"] = body.name
    if body.is_active is not None:
        updates["is_active"] = body.is_active
    if body.email is not None:
        email = body.email.strip().lower()
        try:
            from firebase_admin import auth as fb_auth
            from src.config.firebase_config import FirebaseConfig

            FirebaseConfig()
            fb_user = fb_auth.get_user_by_email(email)
            updates["email"] = email
            updates["user_id"] = fb_user.uid
            logger.info(f"✅ Updated supervisor {code} email={email} uid={fb_user.uid}")
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"Không tìm thấy tài khoản Firebase với email '{email}'.",
            )
    if body.notes is not None:
        updates["notes"] = body.notes
    if body.bank_info is not None:
        updates["bank_info"] = body.bank_info

    db["supervisors"].update_one({"_id": sup["_id"]}, {"$set": updates})
    updated = db["supervisors"].find_one({"_id": sup["_id"]})

    return {
        "message": "Cập nhật Supervisor thành công.",
        "supervisor": fmt_supervisor(updated),
    }
