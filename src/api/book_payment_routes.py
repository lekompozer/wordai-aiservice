"""
Book Payment Routes - SePay Integration
API endpoints for book purchases via SePay (same flow as subscriptions)
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any
from datetime import datetime, timedelta
import uuid

from src.models.book_payment_models import (
    CreatePaymentOrderRequest,
    OrderStatusResponse,
    GrantAccessRequest,
    GrantAccessResponse,
    CashOrderListResponse,
    CashOrderItem,
    OrderStatus,
    PurchaseType,
)
from src.middleware.firebase_auth import get_current_user
from src.database.db_manager import DBManager
from src.utils.logger import setup_logger

logger = setup_logger()
router = APIRouter(prefix="/api/v1/books", tags=["book-payment"])

# Database manager
db_manager = DBManager()
db = db_manager.db


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


async def get_book_price_vnd(book_id: str, purchase_type: PurchaseType) -> int:
    """
    Get book price in VND from access_config
    Convert points to VND: 1 point = 1000 VND
    """
    book = db.online_books.find_one({"book_id": book_id, "is_deleted": False})
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Book not found"
        )

    access_config = book.get("access_config", {})
    if not access_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Book does not have pricing configured",
        )

    # Get price in points
    price_points = 0
    if purchase_type == PurchaseType.ONE_TIME:
        price_points = access_config.get("one_time_view_points", 0)
    elif purchase_type == PurchaseType.FOREVER:
        price_points = access_config.get("forever_view_points", 0)
    elif purchase_type == PurchaseType.PDF_DOWNLOAD:
        price_points = access_config.get("download_pdf_points", 0)

    if price_points <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Purchase type '{purchase_type}' is not enabled for this book",
        )

    # Convert to VND (1 point = 1000 VND)
    price_vnd = price_points * 1000

    return price_vnd


# ==============================================================================
# API ENDPOINTS
# ==============================================================================


@router.post(
    "/{book_id}/create-payment-order",
    summary="Create payment order (for SePay checkout)",
)
async def create_book_payment_order(
    book_id: str,
    request: CreatePaymentOrderRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Create payment order for book purchase**

    Creates order record and returns order_id.
    Frontend then calls payment-service to create SePay checkout.

    **Flow:**
    1. Create book_cash_orders record (status: pending)
    2. Return order_id to frontend
    3. Frontend calls payment-service with order_id to create SePay checkout
    4. User redirected to SePay → pays
    5. SePay webhook → grant-access endpoint
    """
    try:
        user_id = current_user["uid"]
        user_email = current_user.get("email", "")
        user_name = current_user.get("name", user_email.split("@")[0])

        logger.info(
            f"💳 Creating book payment order - User: {user_id}, Book: {book_id}, Type: {request.purchase_type}"
        )

        # 1. Get book and validate
        book = db.online_books.find_one({"book_id": book_id, "is_deleted": False})
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Book not found"
            )

        # Check if book is published
        if not book.get("community_config", {}).get("is_public", False):
            if book.get("user_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Book is not published",
                )

        # 2. Get price in VND
        price_vnd = await get_book_price_vnd(book_id, request.purchase_type)

        # 3. Generate unique order ID (format: BOOK-{timestamp}-{user_short})
        timestamp = int(datetime.utcnow().timestamp())
        user_short = user_id[:8]
        order_id = f"BOOK-{timestamp}-{user_short}"

        # 4. Create book_cash_orders record
        order_doc = {
            "order_id": order_id,
            "user_id": user_id,
            "book_id": book_id,
            "purchase_type": request.purchase_type.value,
            "price_vnd": price_vnd,
            "currency": "VND",
            "payment_method": "SEPAY_BANK_TRANSFER",
            "payment_provider": "SEPAY",
            "status": OrderStatus.PENDING.value,
            "transaction_id": None,
            "paid_at": None,
            "access_granted": False,
            "book_purchase_id": None,
            "user_email": user_email,
            "user_name": user_name,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=24),  # 24h expiry
        }

        db.book_cash_orders.insert_one(order_doc)

        logger.info(f"✅ Book order created: {order_id} - Amount: {price_vnd:,} VND")

        # 5. Return order info
        # Frontend will use order_id to create SePay checkout via payment-service
        return {
            "success": True,
            "order_id": order_id,
            "book_id": book_id,
            "book_title": book["title"],
            "purchase_type": request.purchase_type.value,
            "price_vnd": price_vnd,
            "currency": "VND",
            "payment_method": "SEPAY_BANK_TRANSFER",
            "message": "Order created. Call payment-service to create SePay checkout.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating book payment order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create order: {str(e)}",
        )


@router.get(
    "/orders/{order_id}",
    response_model=OrderStatusResponse,
    summary="Get order status",
)
async def get_order_status(
    order_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Check order status**

    Poll this endpoint to check if payment has been confirmed.
    """
    try:
        user_id = current_user["uid"]

        # Get order
        order = db.book_cash_orders.find_one({"order_id": order_id})
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
            )

        # Verify ownership
        if order["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this order",
            )

        # Check if expired
        if order["status"] == OrderStatus.PENDING.value:
            if datetime.utcnow() > order["expires_at"]:
                db.book_cash_orders.update_one(
                    {"order_id": order_id},
                    {
                        "$set": {
                            "status": OrderStatus.EXPIRED.value,
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
                order["status"] = OrderStatus.EXPIRED.value

        return OrderStatusResponse(
            order_id=order["order_id"],
            book_id=order["book_id"],
            purchase_type=PurchaseType(order["purchase_type"]),
            status=OrderStatus(order["status"]),
            price_vnd=order["price_vnd"],
            transaction_id=order.get("transaction_id"),
            paid_at=order.get("paid_at"),
            access_granted=order["access_granted"],
            book_purchase_id=order.get("book_purchase_id"),
            created_at=order["created_at"],
            updated_at=order["updated_at"],
            expires_at=order["expires_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting order status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get order status: {str(e)}",
        )


@router.post(
    "/grant-access-from-order",
    response_model=GrantAccessResponse,
    summary="Grant access from completed order (Internal - called by webhook)",
)
async def grant_access_from_order(request: GrantAccessRequest):
    """
    **Grant book access after payment confirmation**

    **INTERNAL ENDPOINT** - Called by payment service webhook after SePay confirms payment.

    **Flow:**
    1. Verify order is completed
    2. Create book_purchases record
    3. Update book stats (revenue, purchases)
    4. Credit owner earnings (80%)
    5. Mark order as access granted
    """
    try:
        order_id = request.order_id

        logger.info(f"🔓 Granting access for book order: {order_id}")

        # 1. Get order
        order = db.book_cash_orders.find_one({"order_id": order_id})
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
            )

        # 2. Verify order is completed
        if order["status"] != OrderStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order status is '{order['status']}', expected 'completed'",
            )

        # 3. Check if access already granted
        if order["access_granted"]:
            logger.info(f"⚠️  Access already granted for order {order_id}")
            return GrantAccessResponse(
                success=True,
                message="Access already granted",
                order_id=order_id,
                purchase_id=order.get("book_purchase_id"),
                user_id=order["user_id"],
                book_id=order["book_id"],
            )

        # 4. Create book_purchases record (same as point purchase)
        purchase_id = f"purchase_{uuid.uuid4().hex[:16]}"

        access_expires_at = None
        if order["purchase_type"] == PurchaseType.ONE_TIME.value:
            access_expires_at = datetime.utcnow() + timedelta(hours=24)

        purchase_record = {
            "purchase_id": purchase_id,
            "user_id": order["user_id"],
            "book_id": order["book_id"],
            "purchase_type": order["purchase_type"],
            "points_spent": 0,  # Cash purchase, not points
            "cash_paid_vnd": order["price_vnd"],  # NEW: Track cash amount
            "payment_method": "SEPAY_BANK_TRANSFER",
            "order_id": order_id,  # Link to cash order
            "access_expires_at": access_expires_at,
            "purchased_at": order.get("paid_at", datetime.utcnow()),
        }

        db.book_purchases.insert_one(purchase_record)
        logger.info(f"✅ Created book_purchases record: {purchase_id}")

        # 5. Update book stats
        # Convert VND to points equivalent for stats tracking (1000 VND = 1 point)
        points_equivalent = order["price_vnd"] // 1000
        owner_reward = int(points_equivalent * 0.8)
        system_fee = points_equivalent - owner_reward

        stats_update = {
            "$inc": {
                "stats.total_revenue_points": points_equivalent,
                "stats.owner_reward_points": owner_reward,
                "stats.system_fee_points": system_fee,
                "stats.cash_revenue_vnd": order["price_vnd"],  # Track cash separately
                "community_config.total_purchases": 1,
            }
        }

        # Increment specific purchase type counters
        if order["purchase_type"] == PurchaseType.ONE_TIME.value:
            stats_update["$inc"]["stats.one_time_purchases"] = 1
            stats_update["$inc"]["stats.one_time_revenue"] = points_equivalent
        elif order["purchase_type"] == PurchaseType.FOREVER.value:
            stats_update["$inc"]["stats.forever_purchases"] = 1
            stats_update["$inc"]["stats.forever_revenue"] = points_equivalent
        elif order["purchase_type"] == PurchaseType.PDF_DOWNLOAD.value:
            stats_update["$inc"]["stats.pdf_downloads"] = 1
            stats_update["$inc"]["stats.pdf_revenue"] = points_equivalent

        db.online_books.update_one({"book_id": order["book_id"]}, stats_update)
        logger.info(
            f"✅ Updated book stats: +{points_equivalent} points ({order['price_vnd']:,} VND)"
        )

        # 6. Credit owner earnings
        book = db.online_books.find_one({"book_id": order["book_id"]})
        if book:
            owner_id = book["user_id"]

            if owner_id != order["user_id"]:  # Don't credit if buying own book
                cash_earnings_vnd = int(order["price_vnd"] * 0.8)

                db.user_subscriptions.update_one(
                    {"user_id": owner_id},
                    {
                        "$inc": {
                            "earnings_points": owner_reward,
                            "cash_earnings_vnd": cash_earnings_vnd,
                        },
                        "$set": {"updated_at": datetime.utcnow()},
                    },
                    upsert=False,
                )

                logger.info(
                    f"💰 Credited owner {owner_id}: {owner_reward} points + {cash_earnings_vnd:,} VND (80%)"
                )

        # 7. Mark order as access granted
        db.book_cash_orders.update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "access_granted": True,
                    "book_purchase_id": purchase_id,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        logger.info(f"🎉 Access granted successfully for order {order_id}")

        return GrantAccessResponse(
            success=True,
            message="Access granted successfully",
            order_id=order_id,
            purchase_id=purchase_id,
            user_id=order["user_id"],
            book_id=order["book_id"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error granting access: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to grant access: {str(e)}",
        )


@router.get(
    "/me/cash-orders",
    response_model=CashOrderListResponse,
    summary="List my payment orders",
)
async def list_my_cash_orders(
    page: int = 1,
    limit: int = 20,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **List my book payment orders**

    Get all payment orders created by the current user.
    """
    try:
        user_id = current_user["uid"]

        # Validate pagination
        if limit > 100:
            limit = 100
        skip = (page - 1) * limit

        # Count total
        total = db.book_cash_orders.count_documents({"user_id": user_id})

        # Get orders
        orders_cursor = (
            db.book_cash_orders.find({"user_id": user_id})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        orders = []
        for order in orders_cursor:
            # Get book title
            book = db.online_books.find_one({"book_id": order["book_id"]})
            book_title = book["title"] if book else "Unknown Book"

            orders.append(
                CashOrderItem(
                    order_id=order["order_id"],
                    book_id=order["book_id"],
                    book_title=book_title,
                    purchase_type=PurchaseType(order["purchase_type"]),
                    price_vnd=order["price_vnd"],
                    status=OrderStatus(order["status"]),
                    access_granted=order["access_granted"],
                    created_at=order["created_at"],
                    expires_at=order["expires_at"],
                )
            )

        return CashOrderListResponse(total=total, orders=orders, page=page, limit=limit)

    except Exception as e:
        logger.error(f"❌ Error listing cash orders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list orders: {str(e)}",
        )
