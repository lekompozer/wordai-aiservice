"""
Online Book Marketplace API Routes
Handles marketplace operations: published books, earnings, purchases, and access control.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timezone, timedelta
import re
import unicodedata

# Authentication
from src.middleware.firebase_auth import get_current_user

# Models
from src.models.book_models import (
    # My Published Books
    MyPublishedBookResponse,
    MyPublishedBooksListResponse,
    TransferEarningsRequest,
    TransferEarningsResponse,
    EarningsSummaryResponse,
    # Book Purchases
    PurchaseType,
    PurchaseBookRequest,
    PurchaseBookResponse,
    BookAccessResponse,
    MyPurchaseItem,
    MyPurchasesResponse,
)

# Services
from src.services.book_manager import UserBookManager

# Database
from src.database.db_manager import DBManager

# Constants
from src.constants.book_categories import PARENT_CATEGORIES, CHILD_CATEGORIES

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/books", tags=["Online Books Marketplace"])

# Initialize DB connection
db_manager = DBManager()
db = db_manager.db

# Initialize managers with DB
book_manager = UserBookManager(db)


@router.get("/my-published", response_model=MyPublishedBooksListResponse)
async def list_my_published_books(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    search: Optional[str] = Query(None, description="Search by title or description"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sort_by: str = Query(
        "published_at", description="Sort by: published_at | revenue | views | rating"
    ),
    sort_order: str = Query("desc", description="Sort order: asc | desc"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **List my published books with earnings stats**

    Get all books I've published to community marketplace with detailed stats:
    - Revenue (total, owner share, system fee)
    - Purchases (one-time, forever, PDF downloads)
    - Engagement (views, readers, ratings)

    **Authentication:** Required

    **Query Parameters:**
    - `skip`: Pagination offset (default: 0)
    - `limit`: Results per page (default: 20, max: 100)
    - `search`: Search by title or description (case-insensitive)
    - `category`: Filter by category
    - `sort_by`: Sort field (published_at | revenue | views | rating)
    - `sort_order`: Sort direction (asc | desc)

    **Returns:**
    - 200: List of my published books with stats
    """
    try:
        user_id = current_user["uid"]

        # Build query for published books (including trashed ones per DELETE_PROTECTION_FLOW)
        query = {
            "user_id": user_id,
            # NOTE: No is_deleted filter! Trashed published books still show here
            "community_config.is_public": True,
        }

        # Search by title or description
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
            ]

        # Filter by category (support both parent ID and child category name)
        if category:
            # Check if category is a parent ID
            parent_match = next(
                (p for p in PARENT_CATEGORIES if p["id"] == category), None
            )
            if parent_match:
                # Get all child categories under this parent
                child_names = [
                    child["name"]
                    for child in CHILD_CATEGORIES
                    if child["parent"] == category
                ]
                if child_names:
                    query["community_config.category"] = {"$in": child_names}
                else:
                    # No children, match nothing
                    query["community_config.category"] = {"$in": []}
            else:
                # Assume it's a child category name, match exact
                query["community_config.category"] = category

        # Determine sort field
        sort_field_map = {
            "published_at": "community_config.published_at",
            "revenue": "stats.total_revenue_points",
            "views": "community_config.total_views",
            "rating": "community_config.average_rating",
        }
        sort_field = sort_field_map.get(sort_by, "community_config.published_at")
        sort_direction = -1 if sort_order == "desc" else 1

        # Count total
        total = db.online_books.count_documents(query)

        # Get books
        books_cursor = (
            db.online_books.find(query)
            .sort(sort_field, sort_direction)
            .skip(skip)
            .limit(limit)
        )

        books = []
        for book in books_cursor:
            # Get community config
            community_config = book.get("community_config", {})
            access_config = book.get("access_config", {})
            stats = book.get("stats", {})

            # Calculate stats
            total_revenue = stats.get("total_revenue_points", 0)
            owner_reward = stats.get("owner_reward_points", 0)
            system_fee = stats.get("system_fee_points", 0)

            # Get author info (first author or user)
            authors = book.get("authors", [])
            author_name = None
            if authors:
                # TODO: Query author name from authors collection
                author_name = authors[0]  # For now, use author_id

            books.append(
                MyPublishedBookResponse(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    description=book.get("description"),
                    author_name=author_name,
                    authors=authors,
                    category=community_config.get("category"),
                    tags=community_config.get("tags", []),
                    difficulty_level=community_config.get("difficulty_level"),
                    cover_image_url=community_config.get("cover_image_url")
                    or book.get("cover_image_url"),
                    access_config=access_config if access_config else None,
                    stats={
                        "total_one_time_purchases": stats.get("one_time_purchases", 0),
                        "total_forever_purchases": stats.get("forever_purchases", 0),
                        "total_pdf_downloads": stats.get("pdf_downloads", 0),
                        "total_purchases": community_config.get("total_purchases", 0),
                        "total_revenue_points": total_revenue,
                        "owner_reward_points": owner_reward,
                        "system_fee_points": system_fee,
                        "pending_transfer_points": owner_reward,  # All earnings pending for now
                        "total_views": community_config.get("total_views", 0),
                        "total_readers": community_config.get("total_purchases", 0),
                        "average_rating": community_config.get("average_rating", 0.0),
                        "rating_count": community_config.get("rating_count", 0),
                    },
                    is_deleted=book.get("is_deleted", False),  # DELETE_PROTECTION_FLOW
                    published_at=community_config.get("published_at"),
                    updated_at=book.get("updated_at"),
                )
            )

        logger.info(
            f"📊 User {user_id} listed {len(books)}/{total} published books "
            f"(search={search}, category={category}, sort={sort_by})"
        )

        return MyPublishedBooksListResponse(
            books=books,
            total=total,
            pagination={"skip": skip, "limit": limit},
        )

    except Exception as e:
        logger.error(f"❌ Failed to list my published books: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list my published books",
        )


@router.get("/earnings", response_model=EarningsSummaryResponse)
async def get_earnings_summary(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Get earnings summary for all published books**

    Returns aggregated earnings data across all books published by current user:
    - Total revenue, owner reward, platform fee
    - Breakdown by access type (one-time, forever, PDF)
    - Top earning book

    **Authentication:** Required

    **Returns:**
    - 200: Earnings summary with breakdown
    """
    try:
        user_id = current_user["uid"]

        # Query all published books
        query = {
            "user_id": user_id,
            "is_deleted": False,
            "community_config.is_public": True,
        }

        published_books = list(db.online_books.find(query))

        # Calculate totals
        total_books = len(published_books)
        total_revenue = 0
        owner_reward = 0
        platform_fee = 0

        # Breakdown (TODO: implement actual tracking)
        one_time_revenue = 0
        forever_revenue = 0
        pdf_revenue = 0

        # Find top earning book
        top_book = None
        max_revenue = 0

        for book in published_books:
            stats = book.get("stats", {})
            book_revenue = stats.get("total_revenue_points", 0)
            book_owner_reward = stats.get("owner_reward_points", 0)
            book_system_fee = stats.get("system_fee_points", 0)

            total_revenue += book_revenue
            owner_reward += book_owner_reward
            platform_fee += book_system_fee

            # Aggregate revenue breakdown by purchase type
            one_time_revenue += stats.get("one_time_revenue", 0)
            forever_revenue += stats.get("forever_revenue", 0)
            pdf_revenue += stats.get("pdf_revenue", 0)

            # Track top earning book
            if book_revenue > max_revenue:
                max_revenue = book_revenue
                top_book = {
                    "book_id": book["book_id"],
                    "title": book["title"],
                    "revenue": book_revenue,
                }

        logger.info(
            f"📊 User {user_id} earnings summary: {total_books} books, "
            f"{total_revenue} total revenue, {owner_reward} owner reward"
        )

        return EarningsSummaryResponse(
            total_books_published=total_books,
            total_revenue=total_revenue,
            owner_reward=owner_reward,
            platform_fee=platform_fee,
            breakdown={
                "one_time_revenue": one_time_revenue,
                "forever_revenue": forever_revenue,
                "pdf_revenue": pdf_revenue,
            },
            top_earning_book=top_book,
        )

    except Exception as e:
        logger.error(f"❌ Failed to get earnings summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get earnings summary",
        )


@router.post("/earnings/transfer", response_model=TransferEarningsResponse)
async def transfer_book_earnings(
    request: TransferEarningsRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Transfer book earnings to user wallet**

    Transfer owner's reward points from book revenue to user's main wallet.

    **Authentication:** Required

    **Request Body:**
    - `book_id`: Book ID to transfer earnings from
    - `amount_points`: Amount to transfer (optional, default: all pending)

    **Returns:**
    - 200: Transfer successful with transaction details
    - 403: Not book owner
    - 404: Book not found
    - 400: Insufficient balance
    """
    try:
        user_id = current_user["uid"]
        book_id = request.book_id

        # Get book
        book = book_manager.get_book(book_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # Check ownership
        if book["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only book owner can transfer earnings",
            )

        # Get current stats
        stats = book.get("stats", {})
        owner_reward_points = stats.get("owner_reward_points", 0)

        # Determine transfer amount
        transfer_amount = request.amount_points or owner_reward_points

        if transfer_amount > owner_reward_points:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient balance. Available: {owner_reward_points} points",
            )

        if transfer_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No earnings to transfer",
            )

        # TODO: Implement actual wallet transfer
        # For now, just return mock response
        import uuid
        from datetime import datetime

        transaction_id = f"tx_{uuid.uuid4().hex[:16]}"

        # Update book stats (reduce owner_reward_points)
        db.online_books.update_one(
            {"book_id": book_id},
            {"$inc": {"stats.owner_reward_points": -transfer_amount}},
        )

        # Get user's current wallet balance (mock for now)
        # TODO: Integrate with actual wallet service
        new_wallet_balance = 10000 + transfer_amount  # Mock balance

        logger.info(
            f"💰 User {user_id} transferred {transfer_amount} points from book {book_id}"
        )

        return TransferEarningsResponse(
            book_id=book_id,
            transferred_points=transfer_amount,
            new_wallet_balance=new_wallet_balance,
            transaction_id=transaction_id,
            timestamp=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to transfer earnings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to transfer earnings",
        )


@router.get("/my-purchases", response_model=MyPurchasesResponse)
@router.get("/purchases/history", response_model=MyPurchasesResponse)
async def list_my_purchases(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    purchase_type: Optional[PurchaseType] = Query(
        None, description="Filter by purchase type"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **List all books I've purchased**

    Returns list of purchased books with access status, even if book is deleted.
    Per DELETE_PROTECTION_FLOW: trashed books with purchases remain accessible.

    **Authentication:** Required

    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Items per page (default: 20, max: 100)
    - `purchase_type`: Filter by type (one_time, forever, pdf_download)

    **Returns:**
    - 200: List of my purchases with book info and access status

    **Access Status:**
    - `active`: Currently accessible
    - `expired`: One-time purchase expired
    - `book_deleted_unpublished`: Book unpublished from Community (no access)
    """
    try:
        user_id = current_user["uid"]
        skip = (page - 1) * limit

        # Build query
        query = {"user_id": user_id}
        if purchase_type:
            query["purchase_type"] = purchase_type.value

        # Count total
        total = db.book_purchases.count_documents(query)

        # Get purchases
        purchases_cursor = (
            db.book_purchases.find(query)
            .sort("purchased_at", -1)
            .skip(skip)
            .limit(limit)
        )

        items = []
        now = datetime.now(timezone.utc)

        for purchase in purchases_cursor:
            book_id = purchase["book_id"]

            # Get book info (even if deleted!)
            book = db.online_books.find_one({"book_id": book_id})

            if not book:
                # Book permanently deleted
                access_status = "book_deleted_unpublished"
                book_title = "Deleted Book"
                book_slug = ""
                book_cover = None
                book_is_deleted = True
            else:
                # Check access status
                book_is_deleted = book.get("is_deleted", False)
                is_published = book.get("community_config", {}).get("is_public", False)

                if not is_published:
                    # Book unpublished - no access
                    access_status = "book_deleted_unpublished"
                elif purchase["purchase_type"] == PurchaseType.ONE_TIME.value:
                    # Check expiry
                    expires_at = purchase.get("access_expires_at")
                    if expires_at and expires_at > now:
                        access_status = "active"
                    else:
                        access_status = "expired"
                else:
                    # Forever or PDF - always active if published
                    access_status = "active"

                book_title = book["title"]
                book_slug = book["slug"]
                book_cover = book.get("community_config", {}).get(
                    "cover_image_url"
                ) or book.get("cover_image_url")

            items.append(
                MyPurchaseItem(
                    purchase_id=purchase["purchase_id"],
                    book_id=book_id,
                    book_title=book_title,
                    book_slug=book_slug,
                    book_cover_url=book_cover,
                    book_is_deleted=book_is_deleted,
                    purchase_type=PurchaseType(purchase["purchase_type"]),
                    points_spent=purchase["points_spent"],
                    purchased_at=purchase["purchased_at"],
                    access_expires_at=purchase.get("access_expires_at"),
                    access_status=access_status,
                )
            )

        total_pages = (total + limit - 1) // limit

        logger.info(
            f"📚 User {user_id} listed {len(items)}/{total} purchases (page {page})"
        )

        return MyPurchasesResponse(
            purchases=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"❌ Failed to list my purchases: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list my purchases",
        )


@router.post("/{book_id}/purchase", response_model=PurchaseBookResponse)
async def purchase_book(
    book_id: str,
    request: PurchaseBookRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Purchase book access with points**

    Buy one-time, forever, or PDF download access to a book.

    **Authentication:** Required

    **Path Parameters:**
    - `book_id`: Book ID to purchase

    **Request Body:**
    - `purchase_type`: "one_time" | "forever" | "pdf_download"

    **Returns:**
    - 200: Purchase successful with access details
    - 400: Insufficient balance or invalid purchase type
    - 404: Book not found
    - 409: Already purchased (for forever access)
    """
    try:
        user_id = current_user["uid"]
        purchase_type = request.purchase_type

        # Get book
        book = db.online_books.find_one({"book_id": book_id, "is_deleted": False})
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # Check if book is published and has point-based access
        visibility = book.get("visibility")
        if visibility != "point_based":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Book is not available for purchase",
            )

        # Get access config
        access_config = book.get("access_config", {})
        if not access_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Book access config not found",
            )

        # Determine points cost
        points_map = {
            PurchaseType.ONE_TIME: access_config.get("one_time_view_points", 0),
            PurchaseType.FOREVER: access_config.get("forever_view_points", 0),
            PurchaseType.PDF_DOWNLOAD: access_config.get("download_pdf_points", 0),
        }

        points_cost = points_map.get(purchase_type, 0)
        if points_cost <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Purchase type '{purchase_type}' not enabled for this book",
            )

        # Check if user already has forever access
        if purchase_type == PurchaseType.FOREVER:
            existing_purchase = db.book_purchases.find_one(
                {
                    "user_id": user_id,
                    "book_id": book_id,
                    "purchase_type": PurchaseType.FOREVER.value,
                }
            )
            if existing_purchase:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="You already have forever access to this book",
                )

        # Check user's subscription and balance (from user_subscriptions collection)
        subscription = db.user_subscriptions.find_one({"user_id": user_id})
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User subscription not found",
            )

        user_balance = subscription.get("points_remaining", 0)

        if user_balance < points_cost:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient balance. Required: {points_cost} points, Available: {user_balance}",
            )

        # Calculate revenue split (80% owner, 20% platform)
        total_revenue = points_cost
        owner_reward = int(points_cost * 0.8)
        system_fee = points_cost - owner_reward

        # Deduct points from buyer's subscription
        from datetime import datetime, timedelta, timezone

        result = db.user_subscriptions.update_one(
            {"user_id": user_id},
            {
                "$inc": {
                    "points_remaining": -points_cost,
                    "points_used": points_cost,
                },
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to deduct points",
            )

        # Create purchase record
        import uuid

        purchase_id = f"purchase_{uuid.uuid4().hex[:16]}"
        purchase_time = datetime.utcnow()

        # Set expiry for one-time purchases (24 hours)
        access_expires_at = None
        if purchase_type == PurchaseType.ONE_TIME:
            access_expires_at = purchase_time + timedelta(hours=24)

        purchase_record = {
            "purchase_id": purchase_id,
            "user_id": user_id,
            "book_id": book_id,
            "purchase_type": purchase_type.value,
            "points_spent": points_cost,
            "payment_method": "POINTS",
            "access_expires_at": access_expires_at,
            "purchased_at": purchase_time,
        }

        db.book_purchases.insert_one(purchase_record)

        # Update book stats with purchase type breakdown
        stats_update = {
            "$inc": {
                "stats.total_revenue_points": total_revenue,
                "stats.owner_reward_points": owner_reward,
                "stats.system_fee_points": system_fee,
                "community_config.total_purchases": 1,
            }
        }

        # Increment specific purchase type counters
        if purchase_type == PurchaseType.ONE_TIME:
            stats_update["$inc"]["stats.one_time_purchases"] = 1
            stats_update["$inc"]["stats.one_time_revenue"] = total_revenue
        elif purchase_type == PurchaseType.FOREVER:
            stats_update["$inc"]["stats.forever_purchases"] = 1
            stats_update["$inc"]["stats.forever_revenue"] = total_revenue
        elif purchase_type == PurchaseType.PDF_DOWNLOAD:
            stats_update["$inc"]["stats.pdf_downloads"] = 1
            stats_update["$inc"]["stats.pdf_revenue"] = total_revenue

        db.online_books.update_one({"book_id": book_id}, stats_update)

        # Credit owner's earnings (80% revenue split - can be withdrawn to cash)
        owner_id = book.get("user_id")
        if owner_id and owner_id != user_id:  # Don't credit if buying own book
            owner_earnings_result = db.user_subscriptions.update_one(
                {"user_id": owner_id},
                {
                    "$inc": {"earnings_points": owner_reward},
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                },
                upsert=False,  # Don't create if doesn't exist
            )

            if owner_earnings_result.modified_count > 0:
                logger.info(
                    f"💰 Credited {owner_reward} earnings points to book owner {owner_id} "
                    f"(80% of {points_cost} points purchase)"
                )
            else:
                logger.warning(
                    f"⚠️ Failed to credit earnings to owner {owner_id} - subscription not found"
                )

        logger.info(
            f"📚 User {user_id} purchased {purchase_type} access to book {book_id} for {points_cost} points"
        )

        return PurchaseBookResponse(
            success=True,
            purchase_id=purchase_id,
            book_id=book_id,
            purchase_type=purchase_type,
            points_spent=points_cost,
            remaining_balance=user_balance - points_cost,
            access_expires_at=access_expires_at,
            timestamp=purchase_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to purchase book: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to purchase book",
        )


@router.get("/{book_id}/access", response_model=BookAccessResponse)
async def check_book_access(
    book_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Check user's access to a book**

    Returns whether user has access, access type, expiry, and download permissions.

    **Authentication:** Required

    **Path Parameters:**
    - `book_id`: Book ID to check access

    **Returns:**
    - 200: Access status details
    - 404: Book not found
    """
    try:
        user_id = current_user["uid"]
        from datetime import datetime, timezone

        # Get book (DELETE_PROTECTION_FLOW: Check purchases even if book deleted)
        book = db.online_books.find_one({"book_id": book_id})
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # Check if book is unpublished (no access for buyers)
        is_published = book.get("community_config", {}).get("is_public", False)
        if not is_published and book.get("user_id") != user_id:
            # Book unpublished and user not owner
            return BookAccessResponse(
                has_access=False,
                access_type=None,
                expires_at=None,
                can_download_pdf=False,
                is_owner=False,
                purchase_details=None,
            )

        # Check if user is owner
        is_owner = book.get("user_id") == user_id
        if is_owner:
            return BookAccessResponse(
                has_access=True,
                access_type="owner",
                expires_at=None,
                can_download_pdf=True,
                is_owner=True,
                purchase_details=None,
            )

        # Check book visibility
        visibility = book.get("visibility")

        # Public books - free access
        if visibility == "public":
            return BookAccessResponse(
                has_access=True,
                access_type="public",
                expires_at=None,
                can_download_pdf=False,  # Need to purchase PDF separately
                is_owner=False,
                purchase_details=None,
            )

        # Point-based books - check purchases
        if visibility == "point_based":
            # Check for forever access
            forever_purchase = db.book_purchases.find_one(
                {
                    "user_id": user_id,
                    "book_id": book_id,
                    "purchase_type": PurchaseType.FOREVER.value,
                }
            )

            if forever_purchase:
                # Check if user also has PDF access
                pdf_purchase = db.book_purchases.find_one(
                    {
                        "user_id": user_id,
                        "book_id": book_id,
                        "purchase_type": PurchaseType.PDF_DOWNLOAD.value,
                    }
                )

                return BookAccessResponse(
                    has_access=True,
                    access_type="forever",
                    expires_at=None,
                    can_download_pdf=pdf_purchase is not None,
                    is_owner=False,
                    purchase_details={
                        "purchase_id": forever_purchase.get("purchase_id"),
                        "purchased_at": forever_purchase.get("purchased_at"),
                        "points_spent": forever_purchase.get("points_spent"),
                    },
                )

            # Check for active one-time access
            one_time_purchase = db.book_purchases.find_one(
                {
                    "user_id": user_id,
                    "book_id": book_id,
                    "purchase_type": PurchaseType.ONE_TIME.value,
                }
            )

            if one_time_purchase:
                expires_at = one_time_purchase.get("access_expires_at")
                now = datetime.now(timezone.utc)

                # Check if not expired
                if expires_at and expires_at > now:
                    return BookAccessResponse(
                        has_access=True,
                        access_type="one_time",
                        expires_at=expires_at,
                        can_download_pdf=False,
                        is_owner=False,
                        purchase_details={
                            "purchase_id": one_time_purchase.get("purchase_id"),
                            "purchased_at": one_time_purchase.get("purchased_at"),
                            "points_spent": one_time_purchase.get("points_spent"),
                        },
                    )

        # No access
        return BookAccessResponse(
            has_access=False,
            access_type=None,
            expires_at=None,
            can_download_pdf=False,
            is_owner=False,
            purchase_details=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to check book access: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check book access",
        )
