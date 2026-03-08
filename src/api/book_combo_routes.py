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
    ComboBookFullItem,
    BookAccessConfigSnapshot,
    ComboFullResponse,
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
    CreateComboPaymentOrderRequest,
    ComboOrderStatusResponse,
    ComboOrderStatus,
    GrantComboAccessRequest,
    GrantComboAccessResponse,
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


def _resolve_book_full_details(book_ids: List[str]) -> List[ComboBookFullItem]:
    """Fetch rich book info for all books in a combo (for modal detail view)."""
    items = []
    for bid in book_ids:
        book = db.online_books.find_one(
            {"book_id": bid},
            {
                "book_id": 1,
                "title": 1,
                "slug": 1,
                "description": 1,
                "cover_image_url": 1,
                "community_config": 1,
                "access_config": 1,
                "is_deleted": 1,
            },
        )
        if book:
            cc = book.get("community_config", {})
            cover = cc.get("cover_image_url") or book.get("cover_image_url")
            is_public = cc.get("is_public", False)
            is_deleted = book.get("is_deleted", False)

            # Build book's own access_config snapshot
            raw_ac = book.get("access_config") or {}
            book_ac = (
                BookAccessConfigSnapshot(
                    one_time_view_points=raw_ac.get("one_time_view_points", 0),
                    forever_view_points=raw_ac.get("forever_view_points", 0),
                    download_pdf_points=raw_ac.get("download_pdf_points"),
                    is_one_time_enabled=raw_ac.get("is_one_time_enabled", False),
                    is_forever_enabled=raw_ac.get("is_forever_enabled", True),
                    is_download_enabled=raw_ac.get("is_download_enabled", False),
                )
                if raw_ac
                else None
            )

            items.append(
                ComboBookFullItem(
                    book_id=book["book_id"],
                    title=book.get("title", "Untitled"),
                    slug=book.get("slug", ""),
                    cover_image_url=cover,
                    description=book.get("description") or cc.get("description"),
                    author_name=cc.get("author_name"),
                    category=cc.get("category"),
                    chapter_count=cc.get("chapter_count", 0),
                    view_count=cc.get("total_views", 0),
                    average_rating=float(cc.get("average_rating", 0.0)),
                    total_purchases=cc.get("total_purchases", 0),
                    book_access_config=book_ac,
                    is_available=(is_public and not is_deleted),
                )
            )
        else:
            items.append(
                ComboBookFullItem(
                    book_id=bid,
                    title="Deleted Book",
                    slug="",
                    is_available=False,
                )
            )
    return items


def _doc_to_combo_full_response(doc: dict) -> ComboFullResponse:
    """Build ComboFullResponse with rich per-book info (for modal)."""
    books = _resolve_book_full_details(doc.get("book_ids", []))
    return ComboFullResponse(
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


def _doc_to_combo_response(doc: dict) -> ComboResponse:
    """Build lightweight ComboResponse (used by create/update endpoints)."""
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
    sort: Optional[str] = Query(
        None, description="Sort order: popular (by total_purchases), newest (default)"
    ),
):
    """
    Browse all published combos (public, no auth required).
    Returns lightweight list with first 4 book previews.
    - ?sort=popular — sort by total_purchases desc
    - ?sort=newest (default) — sort by created_at desc
    """
    query: Dict[str, Any] = {"is_published": True, "is_deleted": False}
    if search:
        query["title"] = {"$regex": search, "$options": "i"}

    total = db.book_combos.count_documents(query)
    skip = (page - 1) * limit

    sort_field = "stats.total_purchases" if sort == "popular" else "created_at"
    docs = list(db.book_combos.find(query).sort(sort_field, -1).skip(skip).limit(limit))

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


# ==============================================================================
# SEPAY COMBO PAYMENT — static routes MUST be before /{combo_id}
# ==============================================================================


@router.get(
    "/orders/{order_id}",
    response_model=ComboOrderStatusResponse,
    summary="Get combo payment order status",
)
async def get_combo_order_status(
    order_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Poll payment order status for SePay combo checkout.
    Frontend calls this to detect when payment is confirmed.
    """
    user_id = current_user["uid"]
    order = db.combo_cash_orders.find_one({"order_id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Auto-expire pending orders
    now = datetime.now(timezone.utc)
    expires_at = _normalize_dt(order["expires_at"])
    if (
        order["status"] == ComboOrderStatus.PENDING.value
        and expires_at
        and expires_at < now
    ):
        db.combo_cash_orders.update_one(
            {"order_id": order_id},
            {"$set": {"status": ComboOrderStatus.EXPIRED.value, "updated_at": now}},
        )
        order["status"] = ComboOrderStatus.EXPIRED.value

    return ComboOrderStatusResponse(
        order_id=order["order_id"],
        combo_id=order["combo_id"],
        combo_title=order.get("combo_title", ""),
        purchase_type=ComboPurchaseType(order["purchase_type"]),
        status=ComboOrderStatus(order["status"]),
        price_vnd=order["price_vnd"],
        transaction_id=order.get("transaction_id"),
        paid_at=_normalize_dt(order.get("paid_at")),
        access_granted=order.get("access_granted", False),
        purchase_id=order.get("combo_purchase_id"),
        created_at=_normalize_dt(order["created_at"]),
        expires_at=_normalize_dt(order["expires_at"]),
    )


@router.post(
    "/grant-access-from-order",
    response_model=GrantComboAccessResponse,
    summary="Grant combo access from completed SePay order (internal webhook)",
)
async def grant_combo_access_from_order(request: GrantComboAccessRequest):
    """
    **INTERNAL ENDPOINT** called by payment-service webhook after SePay confirms payment.
    Grants combo access exactly like a points purchase.
    """
    try:
        order_id = request.order_id
        logger.info(f"🔓 Granting combo access for order: {order_id}")

        order = db.combo_cash_orders.find_one({"order_id": order_id})
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        if order["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Order status is '{order['status']}', expected 'completed'",
            )

        if order.get("access_granted"):
            logger.info(f"⚠️  Access already granted for combo order {order_id}")
            return GrantComboAccessResponse(
                success=True,
                message="Access already granted",
                order_id=order_id,
                purchase_id=order.get("combo_purchase_id"),
                user_id=order["user_id"],
                combo_id=order["combo_id"],
            )

        combo_id = order["combo_id"]
        user_id = order["user_id"]
        purchase_type_val = order["purchase_type"]
        now = datetime.now(timezone.utc)

        combo = db.book_combos.find_one({"combo_id": combo_id})
        if not combo:
            raise HTTPException(status_code=404, detail="Combo not found")

        # Create combo_purchases record (same structure as points purchase)
        purchase_id = f"cpurchase_{uuid.uuid4().hex[:16]}"
        access_expires_at = None
        if purchase_type_val == ComboPurchaseType.ONE_TIME.value:
            access_expires_at = now + timedelta(hours=24)

        book_ids_snapshot = combo.get("book_ids", [])
        purchase_record = {
            "purchase_id": purchase_id,
            "user_id": user_id,
            "combo_id": combo_id,
            "book_ids_snapshot": book_ids_snapshot,
            "purchase_type": purchase_type_val,
            "points_spent": 0,
            "cash_paid_vnd": order["price_vnd"],
            "payment_method": "SEPAY_BANK_TRANSFER",
            "order_id": order_id,
            "access_expires_at": access_expires_at,
            "purchased_at": order.get("paid_at", now),
        }
        db.combo_purchases.insert_one(purchase_record)

        # Update combo stats
        points_equivalent = order["price_vnd"] // 1000
        owner_reward = int(points_equivalent * 0.8)
        system_fee = points_equivalent - owner_reward

        pt = ComboPurchaseType(purchase_type_val)
        stat_key_map = {
            ComboPurchaseType.ONE_TIME: "one_time_purchases",
            ComboPurchaseType.FOREVER: "forever_purchases",
            ComboPurchaseType.PDF_DOWNLOAD: "pdf_purchases",
        }
        db.book_combos.update_one(
            {"combo_id": combo_id},
            {
                "$inc": {
                    "stats.total_purchases": 1,
                    f"stats.{stat_key_map[pt]}": 1,
                    "stats.total_revenue_points": points_equivalent,
                    "stats.owner_reward_points": owner_reward,
                    "stats.system_fee_points": system_fee,
                }
            },
        )

        # Credit owner 80%
        owner_id = combo.get("owner_user_id")
        if owner_id and owner_id != user_id and owner_reward > 0:
            cash_earnings_vnd = int(order["price_vnd"] * 0.8)
            db.user_subscriptions.update_one(
                {"user_id": owner_id},
                {
                    "$inc": {
                        "points_remaining": owner_reward,
                        "points_earned": owner_reward,
                        "cash_earnings_vnd": cash_earnings_vnd,
                    },
                    "$set": {"updated_at": now},
                },
            )

        # Mark order as access_granted
        db.combo_cash_orders.update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "access_granted": True,
                    "combo_purchase_id": purchase_id,
                    "updated_at": now,
                }
            },
        )

        logger.info(f"🎉 Combo access granted: {purchase_id} for order {order_id}")
        return GrantComboAccessResponse(
            success=True,
            message="Access granted successfully",
            order_id=order_id,
            purchase_id=purchase_id,
            user_id=user_id,
            combo_id=combo_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to grant combo access: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to grant combo access")


@router.get("/{combo_id}", response_model=ComboFullResponse, summary="Get combo detail")
async def get_combo(combo_id: str):
    """
    Get full combo detail including all books with rich info (description, pricing, stats).
    Public endpoint — no auth required.
    Used by the combo modal UI.
    """
    doc = db.book_combos.find_one({"combo_id": combo_id, "is_deleted": False})
    if not doc:
        raise HTTPException(status_code=404, detail="Combo not found")
    if not doc.get("is_published", True):
        raise HTTPException(status_code=404, detail="Combo not found")
    return _doc_to_combo_full_response(doc)


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

        # Map purchase type → points cost (use `or 0` to handle None stored when not set)
        points_map = {
            ComboPurchaseType.ONE_TIME: access_config.get("one_time_view_points") or 0,
            ComboPurchaseType.FOREVER: access_config.get("forever_view_points") or 0,
            ComboPurchaseType.PDF_DOWNLOAD: access_config.get("download_pdf_points")
            or 0,
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


@router.post(
    "/{combo_id}/create-payment-order",
    summary="Create SePay payment order for combo purchase",
)
async def create_combo_payment_order(
    combo_id: str,
    request: CreateComboPaymentOrderRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Create a SePay bank-transfer payment order for a combo.**

    Flow:
    1. Creates `combo_cash_orders` record (status: pending)
    2. Returns `order_id` + `price_vnd`
    3. Frontend calls payment-service with `order_id` to open SePay QR
    4. User pays → SePay webhook → `/combos/grant-access-from-order`
    5. Frontend polls `GET /combos/orders/{order_id}` for confirmation
    """
    try:
        user_id = current_user["uid"]
        user_email = current_user.get("email", "")
        user_name = current_user.get("name", user_email.split("@")[0])

        combo = db.book_combos.find_one(
            {"combo_id": combo_id, "is_deleted": False, "is_published": True}
        )
        if not combo:
            raise HTTPException(status_code=404, detail="Combo not found")

        purchase_type = request.purchase_type
        access_config = combo.get("access_config", {})

        points_map = {
            ComboPurchaseType.ONE_TIME: access_config.get("one_time_view_points") or 0,
            ComboPurchaseType.FOREVER: access_config.get("forever_view_points") or 0,
            ComboPurchaseType.PDF_DOWNLOAD: access_config.get("download_pdf_points")
            or 0,
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

        price_vnd = points_cost * 1000  # 1 point = 1000 VND

        # Generate order ID
        timestamp = int(datetime.now(timezone.utc).timestamp())
        user_short = user_id[:8]
        order_id = f"COMBO-{timestamp}-{user_short}"

        now = datetime.now(timezone.utc)
        order_doc = {
            "order_id": order_id,
            "user_id": user_id,
            "user_email": user_email,
            "user_name": user_name,
            "combo_id": combo_id,
            "combo_title": combo.get("title", ""),
            "purchase_type": purchase_type.value,
            "price_vnd": price_vnd,
            "currency": "VND",
            "payment_method": "SEPAY_BANK_TRANSFER",
            "payment_provider": "SEPAY",
            "status": ComboOrderStatus.PENDING.value,
            "transaction_id": None,
            "paid_at": None,
            "access_granted": False,
            "combo_purchase_id": None,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + timedelta(hours=24),
        }
        db.combo_cash_orders.insert_one(order_doc)

        logger.info(f"💳 Combo order created: {order_id} — {price_vnd:,} VND")

        return {
            "success": True,
            "order_id": order_id,
            "combo_id": combo_id,
            "combo_title": combo.get("title", ""),
            "purchase_type": purchase_type.value,
            "price_vnd": price_vnd,
            "currency": "VND",
            "payment_method": "SEPAY_BANK_TRANSFER",
            "message": "Order created. Call payment-service to open SePay checkout.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create combo payment order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create payment order")


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
