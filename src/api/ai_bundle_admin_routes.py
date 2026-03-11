"""
AI Bundle Admin Routes

Mirrors src/api/affiliate_admin_routes.py but uses ai_bundle_* collections.
All endpoints require admin auth (Firebase Bearer OR X-Service-Secret).

Endpoints:
- POST /api/v1/admin/ai-bundle/affiliates                         — Create affiliate
- GET  /api/v1/admin/ai-bundle/affiliates                         — List affiliates
- GET  /api/v1/admin/ai-bundle/affiliates/{code}                  — Get affiliate
- PUT  /api/v1/admin/ai-bundle/affiliates/{code}                  — Update affiliate
- GET  /api/v1/admin/ai-bundle/withdrawals/list                   — List withdrawals
- POST /api/v1/admin/ai-bundle/withdrawals/{id}/approve           — Approve
- POST /api/v1/admin/ai-bundle/withdrawals/{id}/reject            — Reject
- POST /api/v1/admin/ai-bundle/supervisors                        — Create supervisor
- GET  /api/v1/admin/ai-bundle/supervisors                        — List supervisors
- PUT  /api/v1/admin/ai-bundle/supervisors/{code}                 — Update supervisor
- GET  /api/v1/admin/ai-bundle/supervisor-withdrawals/list        — Supervisor withdrawals
- POST /api/v1/admin/ai-bundle/supervisor-withdrawals/{id}/approve — Approve
- POST /api/v1/admin/ai-bundle/supervisor-withdrawals/{id}/reject  — Reject
"""

import re
from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.database.db_manager import DBManager
from src.middleware.admin_auth import verify_admin
from src.models.ai_bundle_subscription import (
    AFFILIATE_COMMISSION_RATES,
    get_price,
)
from src.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(
    prefix="/api/v1/admin/ai-bundle",
    tags=["AI Bundle Admin"],
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


class CreateAiBundleAffiliateRequest(BaseModel):
    code: str = Field(...)
    name: str = Field(...)
    tier: int = Field(..., ge=1, le=2)
    email: Optional[str] = Field(None)
    notes: Optional[str] = Field(None)
    bank_info: Optional[dict] = Field(None)
    supervisor_id: Optional[str] = Field(None)


class UpdateAiBundleAffiliateRequest(BaseModel):
    name: Optional[str] = None
    tier: Optional[int] = Field(None, ge=1, le=2)
    is_active: Optional[bool] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    bank_info: Optional[dict] = None
    supervisor_id: Optional[str] = None


class CreateAiBundleSupervisorRequest(BaseModel):
    code: str = Field(...)
    name: str = Field(...)
    email: Optional[str] = Field(None)
    notes: Optional[str] = Field(None)
    bank_info: Optional[dict] = Field(None)


class UpdateAiBundleSupervisorRequest(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    bank_info: Optional[dict] = None


class ApproveRequest(BaseModel):
    notes: Optional[str] = None


class RejectRequest(BaseModel):
    reason: Optional[str] = None


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
        "commission_rate": AFFILIATE_COMMISSION_RATES.get(aff["tier"], 0),
        "total_earned": aff.get("total_earned", 0),
        "total_referred_users": aff.get("total_referred_users", 0),
        "notes": aff.get("notes"),
        "bank_info": aff.get("bank_info"),
        "created_at": aff["created_at"].isoformat() if aff.get("created_at") else None,
        "updated_at": aff["updated_at"].isoformat() if aff.get("updated_at") else None,
    }


def fmt_supervisor(sup: dict) -> dict:
    return {
        "id": str(sup["_id"]),
        "code": sup["code"],
        "name": sup.get("name", ""),
        "is_active": sup.get("is_active", True),
        "login_status": "đã đăng nhập" if sup.get("user_id") else "chưa đăng nhập",
        "email": sup.get("email"),
        "user_id": sup.get("user_id"),
        "total_earned": sup.get("total_earned", 0),
        "total_managed_affiliates": sup.get("total_managed_affiliates", 0),
        "notes": sup.get("notes"),
        "bank_info": sup.get("bank_info"),
        "created_at": sup["created_at"].isoformat() if sup.get("created_at") else None,
        "updated_at": sup["updated_at"].isoformat() if sup.get("updated_at") else None,
    }


# ============================================================================
# AFFILIATES — POST /affiliates
# ============================================================================


@router.post("/affiliates")
async def create_ai_bundle_affiliate(
    body: CreateAiBundleAffiliateRequest,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    code = re.sub(r"[^A-Z0-9]", "", body.code.upper())
    if not code:
        raise HTTPException(status_code=400, detail="Mã đại lý không hợp lệ.")

    if db["ai_bundle_affiliates"].find_one({"code": code}):
        raise HTTPException(
            status_code=409, detail=f"Mã đại lý AI Bundle '{code}' đã tồn tại."
        )

    supervisor_id = None
    if body.supervisor_id:
        try:
            sup = db["ai_bundle_supervisors"].find_one(
                {"_id": ObjectId(body.supervisor_id), "is_active": True}
            )
        except Exception:
            sup = None
        if not sup:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy Supervisor AI Bundle.",
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
    doc["_id"] = result.inserted_id

    if supervisor_id:
        db["ai_bundle_supervisors"].update_one(
            {"_id": ObjectId(supervisor_id)},
            {"$inc": {"total_managed_affiliates": 1}, "$set": {"updated_at": now}},
        )

    logger.info(f"🤝 [AI Bundle Admin] New affiliate: code={code}, tier={body.tier}")
    return {
        "message": "Tạo đại lý AI Bundle thành công.",
        "affiliate": fmt_affiliate(doc),
    }


# ============================================================================
# AFFILIATES — GET /affiliates
# ============================================================================


@router.get("/affiliates")
async def list_ai_bundle_affiliates(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    tier: Optional[int] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    query: dict = {}
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
    return {
        "items": [fmt_affiliate(d) for d in docs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


# ============================================================================
# AFFILIATES — GET /withdrawals/list  (BEFORE /{code} to avoid route conflict)
# ============================================================================


@router.get("/withdrawals/list")
async def list_ai_bundle_withdrawals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    status: Optional[str] = Query(default=None),
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    query: dict = {}
    if status:
        query["status"] = status

    total = db["ai_bundle_withdrawals"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["ai_bundle_withdrawals"]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )

    items = []
    for doc in docs:
        aff = None
        if doc.get("affiliate_id"):
            try:
                aff = db["ai_bundle_affiliates"].find_one(
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
# AFFILIATES — GET /{code}
# ============================================================================


@router.get("/affiliates/{code}")
async def get_ai_bundle_affiliate(
    code: str,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    aff = db["ai_bundle_affiliates"].find_one({"code": code.upper()})
    if not aff:
        raise HTTPException(status_code=404, detail="Không tìm thấy đại lý AI Bundle.")
    return fmt_affiliate(aff)


# ============================================================================
# AFFILIATES — PUT /{code}
# ============================================================================


@router.put("/affiliates/{code}")
async def update_ai_bundle_affiliate(
    code: str,
    body: UpdateAiBundleAffiliateRequest,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    aff = db["ai_bundle_affiliates"].find_one({"code": code.upper()})
    if not aff:
        raise HTTPException(status_code=404, detail="Không tìm thấy đại lý AI Bundle.")

    now = datetime.utcnow()
    updates: dict = {"updated_at": now}
    if body.name is not None:
        updates["name"] = body.name
    if body.tier is not None:
        updates["tier"] = body.tier
    if body.is_active is not None:
        updates["is_active"] = body.is_active
    if body.email is not None:
        updates["email"] = body.email.strip().lower()
        updates["user_id"] = None
    if body.notes is not None:
        updates["notes"] = body.notes
    if body.bank_info is not None:
        updates["bank_info"] = body.bank_info
    if body.supervisor_id is not None:
        if body.supervisor_id == "":
            updates["supervisor_id"] = None
        else:
            try:
                sup = db["ai_bundle_supervisors"].find_one(
                    {"_id": ObjectId(body.supervisor_id), "is_active": True}
                )
            except Exception:
                sup = None
            if not sup:
                raise HTTPException(
                    status_code=404, detail="Không tìm thấy Supervisor AI Bundle."
                )
            updates["supervisor_id"] = body.supervisor_id
            old_sup_id = aff.get("supervisor_id")
            if old_sup_id and old_sup_id != body.supervisor_id:
                try:
                    db["ai_bundle_supervisors"].update_one(
                        {"_id": ObjectId(old_sup_id)},
                        {
                            "$inc": {"total_managed_affiliates": -1},
                            "$set": {"updated_at": now},
                        },
                    )
                except Exception:
                    pass
            if not old_sup_id or old_sup_id != body.supervisor_id:
                db["ai_bundle_supervisors"].update_one(
                    {"_id": ObjectId(body.supervisor_id)},
                    {
                        "$inc": {"total_managed_affiliates": 1},
                        "$set": {"updated_at": now},
                    },
                )

    db["ai_bundle_affiliates"].update_one({"_id": aff["_id"]}, {"$set": updates})
    updated = db["ai_bundle_affiliates"].find_one({"_id": aff["_id"]})
    return {"message": "Cập nhật thành công.", "affiliate": fmt_affiliate(updated)}


# ============================================================================
# WITHDRAWALS — POST /withdrawals/{id}/approve
# ============================================================================


@router.post("/withdrawals/{withdrawal_id}/approve")
async def approve_ai_bundle_withdrawal(
    withdrawal_id: str,
    body: Optional[ApproveRequest] = None,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    try:
        oid = ObjectId(withdrawal_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID không hợp lệ.")

    doc = db["ai_bundle_withdrawals"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu rút tiền.")
    if doc["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Yêu cầu đã ở trạng thái '{doc['status']}'.",
        )

    now = datetime.utcnow()
    db["ai_bundle_withdrawals"].update_one(
        {"_id": oid},
        {
            "$set": {
                "status": "paid",
                "admin_notes": body.notes if body else None,
                "processed_at": now,
                "updated_at": now,
            }
        },
    )
    db["ai_bundle_commissions"].update_many(
        {"affiliate_id": doc["affiliate_id"], "status": "pending"},
        {"$set": {"status": "paid", "updated_at": now}},
    )

    logger.info(
        f"✅ [AI Bundle] Withdrawal approved: id={withdrawal_id}, amount={doc['amount']:,} VND"
    )
    return {
        "message": "Đã duyệt yêu cầu rút tiền AI Bundle.",
        "withdrawal_id": withdrawal_id,
        "amount": doc["amount"],
        "status": "paid",
    }


# ============================================================================
# WITHDRAWALS — POST /withdrawals/{id}/reject
# ============================================================================


@router.post("/withdrawals/{withdrawal_id}/reject")
async def reject_ai_bundle_withdrawal(
    withdrawal_id: str,
    body: Optional[RejectRequest] = None,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    try:
        oid = ObjectId(withdrawal_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID không hợp lệ.")

    doc = db["ai_bundle_withdrawals"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu rút tiền.")
    if doc["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Yêu cầu đã ở trạng thái '{doc['status']}'.",
        )

    now = datetime.utcnow()
    db["ai_bundle_withdrawals"].update_one(
        {"_id": oid},
        {
            "$set": {
                "status": "rejected",
                "admin_notes": body.reason if body else None,
                "processed_at": now,
                "updated_at": now,
            }
        },
    )
    return {"message": "Đã từ chối yêu cầu rút tiền.", "withdrawal_id": withdrawal_id}


# ============================================================================
# SUPERVISORS — POST /supervisors
# ============================================================================


@router.post("/supervisors")
async def create_ai_bundle_supervisor(
    body: CreateAiBundleSupervisorRequest,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    code = re.sub(r"[^A-Z0-9]", "", body.code.upper())
    if not code:
        raise HTTPException(status_code=400, detail="Mã supervisor không hợp lệ.")

    if db["ai_bundle_supervisors"].find_one({"code": code}):
        raise HTTPException(
            status_code=409, detail=f"Mã supervisor AI Bundle '{code}' đã tồn tại."
        )

    email = body.email.strip().lower() if body.email else None
    now = datetime.utcnow()
    doc = {
        "code": code,
        "name": body.name,
        "is_active": True,
        "email": email,
        "user_id": None,
        "notes": body.notes,
        "bank_info": body.bank_info,
        "total_earned": 0,
        "total_managed_affiliates": 0,
        "created_at": now,
        "updated_at": now,
    }
    result = db["ai_bundle_supervisors"].insert_one(doc)
    doc["_id"] = result.inserted_id

    logger.info(f"🏢 [AI Bundle Admin] New supervisor: code={code}")
    return {
        "message": "Tạo supervisor AI Bundle thành công.",
        "supervisor": fmt_supervisor(doc),
    }


# ============================================================================
# SUPERVISORS — GET /supervisors
# ============================================================================


@router.get("/supervisors")
async def list_ai_bundle_supervisors(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    is_active: Optional[bool] = Query(default=None),
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    query: dict = {}
    if is_active is not None:
        query["is_active"] = is_active

    total = db["ai_bundle_supervisors"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["ai_bundle_supervisors"]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )
    return {
        "items": [fmt_supervisor(d) for d in docs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


# ============================================================================
# SUPERVISORS — PUT /supervisors/{code}
# ============================================================================


@router.put("/supervisors/{code}")
async def update_ai_bundle_supervisor(
    code: str,
    body: UpdateAiBundleSupervisorRequest,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    sup = db["ai_bundle_supervisors"].find_one({"code": code.upper()})
    if not sup:
        raise HTTPException(
            status_code=404, detail="Không tìm thấy supervisor AI Bundle."
        )

    now = datetime.utcnow()
    updates: dict = {"updated_at": now}
    if body.name is not None:
        updates["name"] = body.name
    if body.is_active is not None:
        updates["is_active"] = body.is_active
    if body.email is not None:
        updates["email"] = body.email.strip().lower()
        updates["user_id"] = None
    if body.notes is not None:
        updates["notes"] = body.notes
    if body.bank_info is not None:
        updates["bank_info"] = body.bank_info

    db["ai_bundle_supervisors"].update_one({"_id": sup["_id"]}, {"$set": updates})
    updated = db["ai_bundle_supervisors"].find_one({"_id": sup["_id"]})
    return {"message": "Cập nhật thành công.", "supervisor": fmt_supervisor(updated)}


# ============================================================================
# SUPERVISOR WITHDRAWALS — GET /supervisor-withdrawals/list
# ============================================================================


@router.get("/supervisor-withdrawals/list")
async def list_ai_bundle_supervisor_withdrawals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    status: Optional[str] = Query(default=None),
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    query: dict = {}
    if status:
        query["status"] = status

    total = db["ai_bundle_supervisor_withdrawals"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["ai_bundle_supervisor_withdrawals"]
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )

    items = []
    for doc in docs:
        sup = None
        if doc.get("supervisor_id"):
            try:
                sup = db["ai_bundle_supervisors"].find_one(
                    {"_id": ObjectId(doc["supervisor_id"])},
                    {"code": 1, "name": 1},
                )
            except Exception:
                pass
        items.append(
            {
                "id": str(doc["_id"]),
                "supervisor_id": doc.get("supervisor_id"),
                "supervisor_code": sup["code"] if sup else doc.get("supervisor_code"),
                "supervisor_name": sup["name"] if sup else None,
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
# SUPERVISOR WITHDRAWALS — POST /supervisor-withdrawals/{id}/approve
# ============================================================================


@router.post("/supervisor-withdrawals/{withdrawal_id}/approve")
async def approve_ai_bundle_supervisor_withdrawal(
    withdrawal_id: str,
    body: Optional[ApproveRequest] = None,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    try:
        oid = ObjectId(withdrawal_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID không hợp lệ.")

    doc = db["ai_bundle_supervisor_withdrawals"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu rút tiền.")
    if doc["status"] != "pending":
        raise HTTPException(
            status_code=400, detail=f"Yêu cầu đã ở trạng thái '{doc['status']}'."
        )

    now = datetime.utcnow()
    db["ai_bundle_supervisor_withdrawals"].update_one(
        {"_id": oid},
        {
            "$set": {
                "status": "paid",
                "admin_notes": body.notes if body else None,
                "processed_at": now,
                "updated_at": now,
            }
        },
    )
    db["ai_bundle_supervisor_commissions"].update_many(
        {"supervisor_id": doc["supervisor_id"], "status": "pending"},
        {"$set": {"status": "paid", "updated_at": now}},
    )

    return {
        "message": "Đã duyệt yêu cầu rút tiền supervisor AI Bundle.",
        "withdrawal_id": withdrawal_id,
        "amount": doc["amount"],
        "status": "paid",
    }


# ============================================================================
# SUPERVISOR WITHDRAWALS — POST /supervisor-withdrawals/{id}/reject
# ============================================================================


@router.post("/supervisor-withdrawals/{withdrawal_id}/reject")
async def reject_ai_bundle_supervisor_withdrawal(
    withdrawal_id: str,
    body: Optional[RejectRequest] = None,
    _: bool = Depends(verify_admin),
    db=Depends(get_db),
):
    try:
        oid = ObjectId(withdrawal_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID không hợp lệ.")

    doc = db["ai_bundle_supervisor_withdrawals"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu rút tiền.")
    if doc["status"] != "pending":
        raise HTTPException(
            status_code=400, detail=f"Yêu cầu đã ở trạng thái '{doc['status']}'."
        )

    now = datetime.utcnow()
    db["ai_bundle_supervisor_withdrawals"].update_one(
        {"_id": oid},
        {
            "$set": {
                "status": "rejected",
                "admin_notes": body.reason if body else None,
                "processed_at": now,
                "updated_at": now,
            }
        },
    )
    return {
        "message": "Đã từ chối yêu cầu rút tiền supervisor.",
        "withdrawal_id": withdrawal_id,
    }
