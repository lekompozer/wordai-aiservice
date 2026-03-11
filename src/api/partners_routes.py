"""
Partners Portal Routes

Single endpoint that checks which partner products a Firebase user has access to.
Frontend uses this to know which tabs to show on the /partners page.

Endpoints:
- GET /api/v1/partners/me  — Returns all product accounts associated with this user
"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user

router = APIRouter(
    prefix="/api/v1/partners",
    tags=["Partners"],
)


def get_db():
    db_manager = DBManager()
    return db_manager.db


def _link_if_unlinked(db, collection: str, user_id: str, email: str) -> Optional[dict]:
    """
    Look up a partner record by email and auto-link Firebase UID on first visit.
    Returns the record (possibly just UID-linked), or None if not found.
    """
    doc = db[collection].find_one({"user_id": user_id})
    if not doc and email:
        doc = db[collection].find_one({"email": email.lower()})
        if doc:
            db[collection].update_one(
                {"_id": doc["_id"]},
                {"$set": {"user_id": user_id, "updated_at": datetime.utcnow()}},
            )
            doc["user_id"] = user_id
    return doc


@router.get("/me")
async def get_my_partner_profile(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Return summary of all partner/affiliate accounts for the authenticated user.
    The frontend uses the `products` list to decide which tab sections to render.
    """
    user_id = current_user["uid"]
    email = current_user.get("email", "")

    # Check all four partner collections in one pass
    conv_affiliate = _link_if_unlinked(db, "affiliates", user_id, email)
    conv_supervisor = _link_if_unlinked(db, "supervisors", user_id, email)
    aib_affiliate = _link_if_unlinked(db, "ai_bundle_affiliates", user_id, email)
    aib_supervisor = _link_if_unlinked(db, "ai_bundle_supervisors", user_id, email)

    products = []

    if conv_affiliate:
        products.append(
            {
                "product": "conversations",
                "role": "affiliate",
                "code": conv_affiliate["code"],
                "name": conv_affiliate.get("name", ""),
                "tier": conv_affiliate.get("tier"),
                "is_active": conv_affiliate.get("is_active", True),
            }
        )

    if conv_supervisor:
        products.append(
            {
                "product": "conversations",
                "role": "supervisor",
                "code": conv_supervisor["code"],
                "name": conv_supervisor.get("name", ""),
                "is_active": conv_supervisor.get("is_active", True),
            }
        )

    if aib_affiliate:
        products.append(
            {
                "product": "ai_bundle",
                "role": "affiliate",
                "code": aib_affiliate["code"],
                "name": aib_affiliate.get("name", ""),
                "tier": aib_affiliate.get("tier"),
                "is_active": aib_affiliate.get("is_active", True),
            }
        )

    if aib_supervisor:
        products.append(
            {
                "product": "ai_bundle",
                "role": "supervisor",
                "code": aib_supervisor["code"],
                "name": aib_supervisor.get("name", ""),
                "is_active": aib_supervisor.get("is_active", True),
            }
        )

    return {
        "user_id": user_id,
        "email": email,
        "products": products,
        "has_any_product": len(products) > 0,
    }
