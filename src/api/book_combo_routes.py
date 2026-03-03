"""
Book Combo API Routes
Handles combo creation, browsing, purchasing and access control.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional, Dict, Any
import logging
import uuid
from datetime import datetime, timezone, timedelta

from src.middleware.firebase_auth import get_current_user
from src.database.db_manager import DBManager
from src.models.combo_models import (
    ComboAccessConfig,
    ComboBookItem,
    ComboListItem,
    ComboListResponse,
    ComboResponse,
    ComboStats,
    ComboPurchaseItem,
    ComboPurchaseType,
    MyComboPurchasesResponse,
    MyPublishedComboItem,
    MyPublishedCombosResponse,
    CreateComboRequest,
    UpdateComboRequest,
    PurchaseComboRequest,
    PurchaseComboResponse,
    ComboAccessResponse,
)

logger = logging.getLogger("chatbot")
router = APIRouter(prefix="/api/v1/books/combos", tags=["Book Combos"])

db_manager = DBManager()
db = db_manager.db


# ==============================================================================
# HELPERS
# ==============================================================================


def _resolve_book_previews(
    book_ids: List[str], limit: int = 999
) -> List[ComboBookItem]:
    """Fetch lightweight book info for a list of book_ids."""
    items = []
    for bid in book_ids[:limit]:
        book = db.online_books.find_one(
            {"book_id": bid},
            {
                "book_id": 1,
                "title": 1,
                "slug": 1,
                "community_config.cover_image_url": 1,
                "cover_image_url": 1,
                "community_config.is_public": 1,
                "is_deleted": 1,
            },
        )
        if book:
            cover = book.get("community_config", {}).get("cover_image_url") or book.get(
                "cover_image_url"
            )
            is_public = book.get("community_config", {}).get("is_public", False)
            is_deleted = book.get("is_deleted", False)
            items.append(
                ComboBookItem(
                    book_id=book["book_id"],
                    title=book.get("title", "Untitled"),
                    slug=book.get("slug", ""),
                    cover_image_url=cover,
                    is_available=(is_public and not is_deleted),
                )
            )
        else:
            items.append(
                ComboBookItem(
                    book_id=bid,
                    title="Deleted Book",
                    slug="",
                    cover_image_url=None,
                    is_available=False,
                )
            )
    return items


def _normalize_dt(dt):
    """Ensure datetime is timezone-aware (UTC)."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _doc_to_combo_response(doc: dict) -> ComboResponse:
    books = _resolve_book_previews(doc.get("book_ids", []))
    return ComboResponse(
        combo_id=doc["combo_id"],
        owner_user_id=doc["owner_user_id"],
        title=doc["title"],
        description=doc.get("description"),
        cover_image_url=doc.get("cover_image_url"),
        book_ids=doc.get("book_ids", []),
        book_count=doc.get("book_count", len(doc.get("book_ids", []))),
        books=books,
        access_config=ComboAccessConfig(**doc.get("access_config", {})),
        stats=ComboStats(**doc.get("stats", {})),
        is_published=doc.get("is_published", True),
        is_deleted=doc.get("is_deleted", False),
        created_at=_normalize_dt(doc["created_at"]),
        updated_at=_normalize_dt(doc["updated_at"]),
    )


# ==============================================================================
# PUBLIC ENDPOINTS
# ==============================================================================


@router.get("", response_model=ComboListResponse, summary="Browse public combos")
async def list_combos(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by title"),
):
    """
    Browse all published combos (public, no auth required).
    Returns lightweight list with first 4 book previews.
    """
    query: Dict[str, Any] = {"is_published": True, "is_deleted": False}
    if search:
        query["title"] = {"$regex": search, "$options": "i"}

    total = db.book_combos.count_documents(query)
    skip = (page - 1) * limit
    docs = list(
        db.book_combos.find(query).sort("created_at", -1).skip(skip).limit(limit)
    )

    items = []
    for doc in docs:
        all_book_ids = doc.get("book_ids", [])
        previews = _resolve_book_previews(all_book_ids, limit=4)
        items.append(
            ComboListItem(
                combo_id=doc["combo_id"],
                title=doc["title"],
                description=doc.get("description"),
                cover_image_url=doc.get("cover_image_url"),
                book_count=doc.get("book_count", len(all_book_ids)),
                book_previews=previews,
                access_config=ComboAccessConfig(**doc.get("access_config", {})),
                stats=ComboStats(**doc.get("stats", {})),
                is_published=doc.get("is_published", True),
                created_at=_normalize_dt(doc["created_at"]),
            )
        )

    return ComboListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit,
    )


@router.get(
    "/my-purchases",
    response_model=MyComboPurchasesResponse,
    summary="List my combo purchases",
)
async def list_my_combo_purchases(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    List all combos purchased by the current user, with the list of books
    accessible from each combo purchase.
    """
    user_id = current_user["uid"]
    skip = (page - 1) * limit
    query = {"user_id": user_id}

    total = db.combo_purchases.count_documents(query)
    docs = list(
        db.combo_purchases.find(query).sort("purchased_at", -1).skip(skip).limit(limit)
    )

    items = []
    now = datetime.now(timezone.utc)

    for doc in docs:
        combo_id = doc["combo_id"]
        combo = db.book_combos.find_one({"combo_id": combo_id})

        if not combo:
            combo_title = "Deleted Combo"
            combo_cover = None
            combo_deleted = True
        else:
            combo_title = combo.get("title", "")
            combo_cover = combo.get("cover_image_url")
            combo_deleted = combo.get("is_deleted", False)

        # Access status
        expires_at = _normalize_dt(doc.get("access_expires_at"))
        if combo_deleted:
            access_status = "combo_deleted"
        elif doc["purchase_type"] == ComboPurchaseType.ONE_TIME.value:
            access_status = "active" if (expires_at and expires_at > now) else "expired"
        else:
            access_status = "active"

        # Use book_ids_snapshot stored at purchase time
        snapshot_ids = doc.get("book_ids_snapshot", [])
        books = _resolve_book_previews(snapshot_ids)

        items.append(
            ComboPurchaseItem(
                purchase_id=doc["purchase_id"],
                combo_id=combo_id,
                combo_title=combo_title,
                combo_cover_url=combo_cover,
                combo_is_deleted=combo_deleted,
                purchase_type=ComboPurchaseType(doc["purchase_type"]),
                points_spent=doc.get("points_spent", 0),
                purchased_at=_normalize_dt(doc["purchased_at"]),
                access_expires_at=expires_at,
                access_status=access_status,
                book_count=len(snapshot_ids),
                books=books,
            )
        )

    return MyComboPurchasesResponse(
        purchases=items,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit,
    )


@router.get(
    "/my-published",
    response_model=MyPublishedCombosResponse,
    summary="List combos I created",
)
async def list_my_published_combos(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """List all combos created by the current user (including unpublished)."""
    user_id = current_user["uid"]
    skip = (page - 1) * limit
    query = {"owner_user_id": user_id, "is_deleted": False}

    total = db.book_combos.count_documents(query)
    docs = list(
        db.book_combos.find(query).sort("created_at", -1).skip(skip).limit(limit)
    )

    items = [
        MyPublishedComboItem(
            combo_id=doc["combo_id"],
            title=doc["title"],
            cover_image_url=doc.get("cover_image_url"),
            book_count=doc.get("book_count", len(doc.get("book_ids", []))),
            is_published=doc.get("is_published", True),
            is_deleted=doc.get("is_deleted", False),
            access_config=ComboAccessConfig(**doc.get("access_config", {})),
            stats=ComboStats(**doc.get("stats", {})),
            created_at=_normalize_dt(doc["created_at"]),
            updated_at=_normalize_dt(doc["updated_at"]),
        )
        for doc in docs
    ]

    return MyPublishedCombosResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit,
    )


@router.get("/{combo_id}", response_model=ComboResponse, summary="Get combo detail")
async def get_combo(combo_id: str):
    """
    Get full combo detail including all books inside.
    Public endpoint — no auth required.
    """
    doc = db.book_combos.find_one({"combo_id": combo_id, "is_deleted": False})
    if not doc:
        raise HTTPException(status_code=404, detail="Combo not found")
    if not doc.get("is_published", True):
        raise HTTPException(status_code=404, detail="Combo not found")
    return _doc_to_combo_response(doc)


@router.get(
    "/{combo_id}/access",
    response_model=ComboAccessResponse,
    summary="Check user access to combo",
)
async def check_combo_access(
    combo_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Check whether the current user has active access to a combo."""
    user_id = current_user["uid"]
    now = datetime.now(timezone.utc)

    combo = db.book_combos.find_one({"combo_id": combo_id})
    if not combo:
        raise HTTPException(status_code=404, detail="Combo not found")

    if combo.get("owner_user_id") == user_id:
        return ComboAccessResponse(
            has_access=True, access_type="owner", can_download_pdf=True
        )

    # Check forever access
    forever = db.combo_purchases.find_one(
        {
            "user_id": user_id,
            "combo_id": combo_id,
            "purchase_type": ComboPurchaseType.FOREVER.value,
        }
    )
    if forever:
        pdf_purchase = db.combo_purchases.find_one(
            {
                "user_id": user_id,
                "combo_id": combo_id,
                "purchase_type": ComboPurchaseType.PDF_DOWNLOAD.value,
            }
        )
        return ComboAccessResponse(
            has_access=True,
            access_type="forever",
            can_download_pdf=pdf_purchase is not None,
            purchase_id=forever.get("purchase_id"),
        )

    # Check one_time access
    one_time = db.combo_purchases.find_one(
        {
            "user_id": user_id,
            "combo_id": combo_id,
            "purchase_type": ComboPurchaseType.ONE_TIME.value,
        }
    )
    if one_time:
        expires_at = _normalize_dt(one_time.get("access_expires_at"))
        if expires_at and expires_at > now:
            return ComboAccessResponse(
                has_access=True,
                access_type="one_time",
                expires_at=expires_at,
                can_download_pdf=False,
                purchase_id=one_time.get("purchase_id"),
            )

    return ComboAccessResponse(has_access=False)


# ==============================================================================
# AUTH ENDPOINTS — BUYER
# ==============================================================================


@router.post(
    "/{combo_id}/purchase",
    response_model=PurchaseComboResponse,
    summary="Purchase combo with points",
)
async def purchase_combo(
    combo_id: str,
    request: PurchaseComboRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Purchase a combo using points.
    - `one_time`: 24-hour access to all books in combo
    - `lifetime`: Permanent access to all books in combo
    - `pdf_download`: PDF download access for all books in combo
    """
    try:
        user_id = current_user["uid"]
        purchase_type = request.purchase_type
        now = datetime.now(timezone.utc)

        # Validate combo
        combo = db.book_combos.find_one(
            {"combo_id": combo_id, "is_deleted": False, "is_published": True}
        )
        if not combo:
            raise HTTPException(status_code=404, detail="Combo not found")

        access_config = combo.get("access_config", {})

        # Map purchase type → points cost
        points_map = {
            ComboPurchaseType.ONE_TIME: access_config.get("one_time_view_points", 0),
            ComboPurchaseType.FOREVER: access_config.get("forever_view_points", 0),
            ComboPurchaseType.PDF_DOWNLOAD: access_config.get("download_pdf_points", 0),
        }
        enabled_map = {
            ComboPurchaseType.ONE_TIME: access_config.get("is_one_time_enabled", False),
            ComboPurchaseType.FOREVER: access_config.get("is_forever_enabled", True),
            ComboPurchaseType.PDF_DOWNLOAD: access_config.get(
                "is_download_enabled", False
            ),
        }

        if not enabled_map.get(purchase_type, False):
            raise HTTPException(
                status_code=400,
                detail=f"Purchase type '{purchase_type}' is not enabled for this combo",
            )

        points_cost = points_map.get(purchase_type, 0)
        if points_cost <= 0:
            raise HTTPException(status_code=400, detail="Invalid pricing configuration")

        # Prevent duplicate forever purchase
        if purchase_type == ComboPurchaseType.FOREVER:
            existing = db.combo_purchases.find_one(
                {
                    "user_id": user_id,
                    "combo_id": combo_id,
                    "purchase_type": ComboPurchaseType.FOREVER.value,
                }
            )
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail="You already have forever access to this combo",
                )

        # Check user balance
        sub = db.user_subscriptions.find_one({"user_id": user_id})
        if not sub:
            raise HTTPException(status_code=402, detail="No points wallet found")
        user_balance = sub.get("points_remaining", 0)
        if user_balance < points_cost:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient points. You have {user_balance} points but need {points_cost}",
            )

        # Deduct points
        result = db.user_subscriptions.update_one(
            {"user_id": user_id},
            {
                "$inc": {"points_remaining": -points_cost, "points_used": points_cost},
                "$set": {"updated_at": now},
            },
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to deduct points")

        # Set expiry for one-time
        access_expires_at = None
        if purchase_type == ComboPurchaseType.ONE_TIME:
            access_expires_at = now + timedelta(hours=24)

        # Record purchase with snapshot of book_ids at purchase time
        purchase_id = f"cpurchase_{uuid.uuid4().hex[:16]}"
        book_ids_snapshot = combo.get("book_ids", [])

        purchase_record = {
            "purchase_id": purchase_id,
            "user_id": user_id,
            "combo_id": combo_id,
            "book_ids_snapshot": book_ids_snapshot,
            "purchase_type": purchase_type.value,
            "points_spent": points_cost,
            "cash_paid_vnd": 0,
            "payment_method": "POINTS",
            "order_id": None,
            "access_expires_at": access_expires_at,
            "purchased_at": now,
        }
        db.combo_purchases.insert_one(purchase_record)

        # Update combo stats
        stat_key_map = {
            ComboPurchaseType.ONE_TIME: "one_time_purchases",
            ComboPurchaseType.FOREVER: "forever_purchases",
            ComboPurchaseType.PDF_DOWNLOAD: "pdf_purchases",
        }
        owner_reward = int(points_cost * 0.8)
        system_fee = points_cost - owner_reward

        db.book_combos.update_one(
            {"combo_id": combo_id},
            {
                "$inc": {
                    "stats.total_purchases": 1,
                    f"stats.{stat_key_map[purchase_type]}": 1,
                    "stats.total_revenue_points": points_cost,
                    "stats.owner_reward_points": owner_reward,
                    "stats.system_fee_points": system_fee,
                }
            },
        )

        # Credit owner earnings (80%)
        owner_id = combo.get("owner_user_id")
        if owner_id and owner_id != user_id and owner_reward > 0:
            db.user_subscriptions.update_one(
                {"user_id": owner_id},
                {
                    "$inc": {
                        "points_remaining": owner_reward,
                        "points_earned": owner_reward,
                    },
                    "$set": {"updated_at": now},
                },
            )

        logger.info(
            f"🎁 User {user_id} purchased combo {combo_id} ({purchase_type}) for {points_cost} points"
        )

        return PurchaseComboResponse(
            success=True,
            purchase_id=purchase_id,
            combo_id=combo_id,
            purchase_type=purchase_type,
            points_spent=points_cost,
            remaining_balance=user_balance - points_cost,
            book_ids=book_ids_snapshot,
            access_expires_at=access_expires_at,
            timestamp=now,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to purchase combo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to purchase combo")


# ==============================================================================
# AUTH ENDPOINTS — OWNER / ADMIN (CRUD)
# ==============================================================================


@router.post(
    "", response_model=ComboResponse, status_code=201, summary="Create a new combo"
)
async def create_combo(
    request: CreateComboRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create a new combo. The caller must own ALL books in book_ids,
    or be an admin (user_id == 'admin').
    """
    try:
        user_id = current_user["uid"]
        now = datetime.now(timezone.utc)

        # Validate all books exist and caller is owner (skip check for admin)
        is_admin = current_user.get("role") == "admin"
        for bid in request.book_ids:
            book = db.online_books.find_one({"book_id": bid, "is_deleted": False})
            if not book:
                raise HTTPException(status_code=404, detail=f"Book '{bid}' not found")
            if not is_admin and book.get("user_id") != user_id:
                raise HTTPException(
                    status_code=403,
                    detail=f"You do not own book '{bid}'. You can only create combos from your own books.",
                )

        combo_id = f"combo_{uuid.uuid4().hex[:16]}"
        doc = {
            "combo_id": combo_id,
            "owner_user_id": user_id,
            "title": request.title,
            "description": request.description,
            "cover_image_url": request.cover_image_url,
            "book_ids": request.book_ids,
            "book_count": len(request.book_ids),
            "access_config": request.access_config.dict(),
            "stats": ComboStats().dict(),
            "is_published": True,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
        }
        db.book_combos.insert_one(doc)

        logger.info(
            f"📦 User {user_id} created combo {combo_id} with {len(request.book_ids)} books"
        )
        return _doc_to_combo_response(doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create combo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create combo")


@router.put("/{combo_id}", response_model=ComboResponse, summary="Update a combo")
async def update_combo(
    combo_id: str,
    request: UpdateComboRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Update combo metadata, pricing, or add more books.
    Note: Books CANNOT be removed once someone has purchased the combo.
    """
    try:
        user_id = current_user["uid"]
        is_admin = current_user.get("role") == "admin"

        doc = db.book_combos.find_one({"combo_id": combo_id, "is_deleted": False})
        if not doc:
            raise HTTPException(status_code=404, detail="Combo not found")
        if not is_admin and doc["owner_user_id"] != user_id:
            raise HTTPException(status_code=403, detail="You do not own this combo")

        # Has anyone purchased this combo?
        has_purchases = db.combo_purchases.find_one({"combo_id": combo_id}) is not None

        set_fields: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}

        if request.title is not None:
            set_fields["title"] = request.title
        if request.description is not None:
            set_fields["description"] = request.description
        if request.cover_image_url is not None:
            set_fields["cover_image_url"] = request.cover_image_url
        if request.access_config is not None:
            set_fields["access_config"] = request.access_config.dict()
        if request.is_published is not None:
            set_fields["is_published"] = request.is_published

        # Add books (only adding allowed once purchased)
        if request.add_book_ids:
            existing_ids = set(doc.get("book_ids", []))
            new_ids = [bid for bid in request.add_book_ids if bid not in existing_ids]
            if new_ids:
                for bid in new_ids:
                    book = db.online_books.find_one(
                        {"book_id": bid, "is_deleted": False}
                    )
                    if not book:
                        raise HTTPException(
                            status_code=404, detail=f"Book '{bid}' not found"
                        )
                    if not is_admin and book.get("user_id") != user_id:
                        raise HTTPException(
                            status_code=403, detail=f"You do not own book '{bid}'"
                        )
                updated_ids = list(existing_ids) + new_ids
                set_fields["book_ids"] = updated_ids
                set_fields["book_count"] = len(updated_ids)

        db.book_combos.update_one({"combo_id": combo_id}, {"$set": set_fields})
        updated_doc = db.book_combos.find_one({"combo_id": combo_id})

        logger.info(f"✏️  User {user_id} updated combo {combo_id}")
        return _doc_to_combo_response(updated_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update combo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update combo")


@router.delete("/{combo_id}", status_code=200, summary="Delete (soft) a combo")
async def delete_combo(
    combo_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Soft-delete a combo (is_deleted=True, is_published=False).
    Existing purchasers retain access via their combo_purchases snapshot.
    """
    try:
        user_id = current_user["uid"]
        is_admin = current_user.get("role") == "admin"

        doc = db.book_combos.find_one({"combo_id": combo_id, "is_deleted": False})
        if not doc:
            raise HTTPException(status_code=404, detail="Combo not found")
        if not is_admin and doc["owner_user_id"] != user_id:
            raise HTTPException(status_code=403, detail="You do not own this combo")

        db.book_combos.update_one(
            {"combo_id": combo_id},
            {
                "$set": {
                    "is_deleted": True,
                    "is_published": False,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        logger.info(f"🗑️  User {user_id} deleted combo {combo_id}")
        return {"success": True, "combo_id": combo_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete combo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete combo")
