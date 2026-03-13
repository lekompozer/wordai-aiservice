"""
StudyHub Course Payment Routes
Endpoints for course enrollment payment — Points and SePay (same pattern as books)

Collections:
- studyhub_purchases: records of paid enrollments (point or cash)
- studyhub_cash_orders: pending/completed SePay payment orders

1 Point = 1000 VND
Owner gets 80%, platform 20%
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
import uuid

from src.middleware.firebase_auth import get_current_user
from src.database.db_manager import DBManager
from src.utils.logger import setup_logger
from bson import ObjectId

logger = setup_logger()
router = APIRouter(prefix="/api/studyhub", tags=["StudyHub - Course Payment"])

db_manager = DBManager()
db = db_manager.db


# ==============================================================================
# MODELS
# ==============================================================================


class PurchaseCourseRequest(BaseModel):
    """Purchase course with points"""

    pass  # No extra fields — course_id from path, user from auth


class CreateCoursePaymentOrderRequest(BaseModel):
    """Create SePay payment order for course"""

    pass  # No extra fields — course_id from path, user from auth


class GrantCourseAccessRequest(BaseModel):
    """Grant course access after payment — called by payment-service webhook"""

    order_id: str


# ==============================================================================
# HELPERS
# ==============================================================================


def _get_subject_price(subject_id: str) -> tuple:
    """
    Returns (price_points, is_free) for a subject.
    Raises 404 if not found.
    """
    subject = db.studyhub_subjects.find_one(
        {"_id": ObjectId(subject_id), "deleted_at": None}
    )
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    price_points = subject.get("marketplace_price_points", 0) or 0
    is_free = subject.get("marketplace_is_free", True)
    return subject, price_points, is_free


async def _create_enrollment_after_purchase(
    user_id: str, subject_id: str, subject: dict
):
    """Create enrollment record after successful purchase."""
    now = datetime.now(timezone.utc)

    # Check if already enrolled (shouldn't normally happen, but guard)
    existing = db.studyhub_enrollments.find_one(
        {
            "user_id": user_id,
            "subject_id": ObjectId(subject_id),
            "status": {"$ne": "dropped"},
        }
    )
    if existing:
        return  # Already enrolled, nothing to do

    enrollment_doc = {
        "user_id": user_id,
        "subject_id": ObjectId(subject_id),
        "status": "active",
        "enrolled_at": now,
        "last_accessed_at": now,
        "completed_at": None,
        "created_at": now,
        "updated_at": now,
    }
    db.studyhub_enrollments.insert_one(enrollment_doc)

    # Increment learner count on subject
    db.studyhub_subjects.update_one(
        {"_id": ObjectId(subject_id)},
        {
            "$inc": {"metadata.total_learners": 1},
            "$set": {"updated_at": now},
        },
    )
    logger.info(
        f"✅ Auto-enrolled user {user_id} in subject {subject_id} after purchase"
    )


# ==============================================================================
# ENDPOINTS
# ==============================================================================


@router.post(
    "/subjects/{subject_id}/enroll",
    summary="Enroll in free course",
)
async def enroll_free_course(
    subject_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Enroll in a FREE community course (no payment needed)**

    - Only works for free courses (`marketplace_is_free = true`)
    - Creates `studyhub_enrollments` record
    - No points deducted

    **Returns**:
    ```json
    {
        "success": true,
        "subject_id": "...",
        "subject_title": "Python for Beginners",
        "enrolled_at": "2026-03-13T..."
    }
    ```
    """
    try:
        user_id = current_user["uid"]

        subject, price_points, is_free = _get_subject_price(subject_id)

        if not is_free:
            raise HTTPException(
                status_code=400,
                detail="This course is paid — use the purchase endpoint instead",
            )

        if subject.get("marketplace_status") != "published":
            raise HTTPException(status_code=400, detail="Course is not published")

        # Check already enrolled
        existing = db.studyhub_enrollments.find_one(
            {
                "user_id": user_id,
                "subject_id": ObjectId(subject_id),
                "status": {"$ne": "dropped"},
            }
        )
        if existing:
            return {
                "success": True,
                "subject_id": subject_id,
                "subject_title": subject["title"],
                "enrolled_at": existing["enrolled_at"].isoformat(),
                "message": "Already enrolled",
            }

        await _create_enrollment_after_purchase(user_id, subject_id, subject)
        now = datetime.now(timezone.utc)

        logger.info(f"🎓 User {user_id} enrolled free in subject {subject_id}")

        return {
            "success": True,
            "subject_id": subject_id,
            "subject_title": subject["title"],
            "enrolled_at": now.isoformat(),
            "message": "Enrolled successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to enroll in free course: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to enroll")


@router.post(
    "/subjects/{subject_id}/purchase",
    summary="Purchase course with Points",
)
async def purchase_course_with_points(
    subject_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Purchase a paid course using Points (1 point = 1000 VND)**

    - Deducts points from user's subscription balance
    - Creates `studyhub_purchases` record
    - Auto-enrolls user in the course
    - Credits 80% earnings to course owner

    **Permission**: Authenticated users

    **Returns**:
    ```json
    {
        "success": true,
        "purchase_id": "purchase_abc123",
        "subject_id": "...",
        "points_spent": 50,
        "remaining_balance": 150
    }
    ```
    """
    try:
        user_id = current_user["uid"]

        subject, price_points, is_free = _get_subject_price(subject_id)

        # Must be a paid course
        if is_free or price_points <= 0:
            raise HTTPException(
                status_code=400,
                detail="This course is free — use the enroll endpoint instead",
            )

        # Subject must be published
        if subject.get("status") != "published":
            raise HTTPException(status_code=400, detail="Course is not published")

        # Check if already purchased
        existing_purchase = db.studyhub_purchases.find_one(
            {
                "user_id": user_id,
                "subject_id": ObjectId(subject_id),
                "status": "active",
            }
        )
        if existing_purchase:
            raise HTTPException(status_code=409, detail="Already purchased this course")

        # Get user balance
        subscription = db.user_subscriptions.find_one({"user_id": user_id})
        if not subscription:
            raise HTTPException(status_code=404, detail="User subscription not found")

        user_balance = subscription.get("points_remaining", 0)
        if user_balance < price_points:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient balance. Required: {price_points} points, Available: {user_balance}",
            )

        # Revenue split: 80% owner, 20% platform
        owner_reward = int(price_points * 0.8)
        system_fee = price_points - owner_reward

        # Deduct points from buyer
        result = db.user_subscriptions.update_one(
            {"user_id": user_id},
            {
                "$inc": {
                    "points_remaining": -price_points,
                    "points_used": price_points,
                },
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to deduct points")

        # Create purchase record
        purchase_id = f"purchase_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)

        purchase_doc = {
            "purchase_id": purchase_id,
            "user_id": user_id,
            "subject_id": ObjectId(subject_id),
            "points_spent": price_points,
            "payment_method": "POINTS",
            "status": "active",
            "purchased_at": now,
            "created_at": now,
        }
        db.studyhub_purchases.insert_one(purchase_doc)

        # Update subject stats
        db.studyhub_subjects.update_one(
            {"_id": ObjectId(subject_id)},
            {
                "$inc": {
                    "marketplace_total_revenue_points": price_points,
                    "marketplace_owner_reward_points": owner_reward,
                    "marketplace_system_fee_points": system_fee,
                    "marketplace_total_purchases": 1,
                },
                "$set": {"updated_at": now},
            },
        )

        # Credit 80% earnings to owner
        owner_id = subject.get("owner_id")
        if owner_id and owner_id != user_id:
            credit_result = db.user_subscriptions.update_one(
                {"user_id": owner_id},
                {
                    "$inc": {"earnings_points": owner_reward},
                    "$set": {"updated_at": now},
                },
                upsert=False,
            )
            if credit_result.modified_count > 0:
                logger.info(
                    f"💰 Credited {owner_reward} earnings points to course owner {owner_id}"
                )

        # Auto-enroll user
        await _create_enrollment_after_purchase(user_id, subject_id, subject)

        remaining_balance = user_balance - price_points
        logger.info(
            f"🎓 User {user_id} purchased course {subject_id} for {price_points} points"
        )

        return {
            "success": True,
            "purchase_id": purchase_id,
            "subject_id": subject_id,
            "subject_title": subject["title"],
            "points_spent": price_points,
            "remaining_balance": remaining_balance,
            "purchased_at": now.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to purchase course: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to purchase course")


@router.post(
    "/subjects/{subject_id}/create-payment-order",
    summary="Create SePay payment order for course",
)
async def create_course_payment_order(
    subject_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Create a SePay bank transfer payment order for course enrollment**

    Flow:
    1. Create `studyhub_cash_orders` record (status: pending)
    2. Return `order_id` to frontend
    3. Frontend calls payment-service with `order_id` to create SePay checkout
    4. User pays → SePay webhook → `grant-access-from-order` endpoint
    5. Auto-enroll user

    **Returns**:
    ```json
    {
        "order_id": "COURSE-1234567890-abc12345",
        "price_vnd": 50000,
        "subject_title": "Python for Beginners"
    }
    ```
    """
    try:
        user_id = current_user["uid"]
        user_email = current_user.get("email", "")
        user_name = current_user.get(
            "name", user_email.split("@")[0] if user_email else "user"
        )

        subject, price_points, is_free = _get_subject_price(subject_id)

        if is_free or price_points <= 0:
            raise HTTPException(
                status_code=400,
                detail="This course is free — use the enroll endpoint instead",
            )

        if subject.get("status") != "published":
            raise HTTPException(status_code=400, detail="Course is not published")

        # Check if already purchased
        existing_purchase = db.studyhub_purchases.find_one(
            {
                "user_id": user_id,
                "subject_id": ObjectId(subject_id),
                "status": "active",
            }
        )
        if existing_purchase:
            raise HTTPException(status_code=409, detail="Already purchased this course")

        # Convert points to VND (1 point = 1000 VND)
        price_vnd = price_points * 1000

        # Generate order ID
        timestamp = int(datetime.utcnow().timestamp())
        user_short = user_id[:8]
        order_id = f"COURSE-{timestamp}-{user_short}"

        now = datetime.utcnow()
        order_doc = {
            "order_id": order_id,
            "user_id": user_id,
            "subject_id": str(subject_id),
            "subject_title": subject["title"],
            "price_vnd": price_vnd,
            "price_points": price_points,
            "currency": "VND",
            "payment_method": "SEPAY_BANK_TRANSFER",
            "payment_provider": "SEPAY",
            "status": "pending",
            "transaction_id": None,
            "paid_at": None,
            "access_granted": False,
            "purchase_id": None,
            "user_email": user_email,
            "user_name": user_name,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + timedelta(hours=24),
        }
        db.studyhub_cash_orders.insert_one(order_doc)

        logger.info(f"💳 Course order created: {order_id} — {price_vnd:,} VND")

        return {
            "success": True,
            "order_id": order_id,
            "subject_id": subject_id,
            "subject_title": subject["title"],
            "price_vnd": price_vnd,
            "price_points": price_points,
            "currency": "VND",
            "payment_method": "SEPAY_BANK_TRANSFER",
            "expires_at": (now + timedelta(hours=24)).isoformat(),
            "message": "Order created. Call payment-service to create SePay checkout.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating course payment order: {e}")
        raise HTTPException(status_code=500, detail="Failed to create order")


@router.get(
    "/orders/{order_id}",
    summary="Get course payment order status",
)
async def get_course_order_status(
    order_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Poll this endpoint to check if payment has been confirmed."""
    user_id = current_user["uid"]

    order = db.studyhub_cash_orders.find_one({"order_id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this order")

    # Auto-expire pending orders
    if order["status"] == "pending":
        if datetime.utcnow() > order["expires_at"]:
            db.studyhub_cash_orders.update_one(
                {"order_id": order_id},
                {"$set": {"status": "expired", "updated_at": datetime.utcnow()}},
            )
            order["status"] = "expired"

    return {
        "order_id": order["order_id"],
        "subject_id": order["subject_id"],
        "subject_title": order["subject_title"],
        "status": order["status"],
        "price_vnd": order["price_vnd"],
        "transaction_id": order.get("transaction_id"),
        "paid_at": order.get("paid_at"),
        "access_granted": order["access_granted"],
        "created_at": order["created_at"],
        "expires_at": order["expires_at"],
    }


@router.post(
    "/grant-access-from-order",
    summary="Grant course access after SePay payment — Internal webhook",
)
async def grant_course_access_from_order(request: GrantCourseAccessRequest):
    """
    **INTERNAL ENDPOINT** — Called by payment-service webhook after SePay confirms payment.

    Flow:
    1. Verify order is completed
    2. Create `studyhub_purchases` record
    3. Update subject stats
    4. Credit 80% earnings to owner
    5. Auto-enroll user
    6. Mark order as access_granted
    """
    try:
        order_id = request.order_id
        logger.info(f"🔓 Granting course access for order: {order_id}")

        order = db.studyhub_cash_orders.find_one({"order_id": order_id})
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        if order["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Order status is '{order['status']}', expected 'completed'",
            )

        if order["access_granted"]:
            logger.info(f"⚠️ Access already granted for order {order_id}")
            return {
                "success": True,
                "message": "Access already granted",
                "order_id": order_id,
                "purchase_id": order.get("purchase_id"),
            }

        subject_id = order["subject_id"]
        user_id = order["user_id"]

        # Check if already purchased (idempotent)
        existing = db.studyhub_purchases.find_one(
            {
                "user_id": user_id,
                "subject_id": ObjectId(subject_id),
                "status": "active",
            }
        )

        purchase_id = (
            existing["purchase_id"] if existing else f"purchase_{uuid.uuid4().hex[:16]}"
        )
        now = datetime.now(timezone.utc)

        if not existing:
            # Create purchase record
            db.studyhub_purchases.insert_one(
                {
                    "purchase_id": purchase_id,
                    "user_id": user_id,
                    "subject_id": ObjectId(subject_id),
                    "points_spent": 0,
                    "cash_paid_vnd": order["price_vnd"],
                    "payment_method": "SEPAY_BANK_TRANSFER",
                    "order_id": order_id,
                    "status": "active",
                    "purchased_at": order.get("paid_at", now),
                    "created_at": now,
                }
            )

            # Update subject stats
            price_points_equiv = order["price_vnd"] // 1000
            owner_reward = int(price_points_equiv * 0.8)
            system_fee = price_points_equiv - owner_reward

            db.studyhub_subjects.update_one(
                {"_id": ObjectId(subject_id)},
                {
                    "$inc": {
                        "marketplace_total_revenue_points": price_points_equiv,
                        "marketplace_owner_reward_points": owner_reward,
                        "marketplace_system_fee_points": system_fee,
                        "marketplace_cash_revenue_vnd": order["price_vnd"],
                        "marketplace_total_purchases": 1,
                    },
                    "$set": {"updated_at": now},
                },
            )

            # Credit owner earnings
            subject = db.studyhub_subjects.find_one({"_id": ObjectId(subject_id)})
            if subject:
                owner_id = subject.get("owner_id")
                if owner_id and owner_id != user_id:
                    cash_earnings_vnd = int(order["price_vnd"] * 0.8)
                    db.user_subscriptions.update_one(
                        {"user_id": owner_id},
                        {
                            "$inc": {
                                "earnings_points": owner_reward,
                                "cash_earnings_vnd": cash_earnings_vnd,
                            },
                            "$set": {"updated_at": now},
                        },
                        upsert=False,
                    )
                    logger.info(
                        f"💰 Credited owner {owner_id}: {owner_reward} points + {cash_earnings_vnd:,} VND"
                    )

                # Auto-enroll user
                await _create_enrollment_after_purchase(user_id, subject_id, subject)

        # Mark order access_granted
        db.studyhub_cash_orders.update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "access_granted": True,
                    "purchase_id": purchase_id,
                    "updated_at": now,
                }
            },
        )

        logger.info(f"🎉 Course access granted for order {order_id}, user {user_id}")

        return {
            "success": True,
            "message": "Course access granted successfully",
            "order_id": order_id,
            "purchase_id": purchase_id,
            "user_id": user_id,
            "subject_id": subject_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error granting course access: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to grant course access")


@router.get(
    "/subjects/{subject_id}/purchase-status",
    summary="Check if current user has purchased the course",
)
async def check_course_purchase_status(
    subject_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Returns whether the authenticated user has purchased (paid for) this course."""
    user_id = current_user["uid"]

    subject, price_points, is_free = _get_subject_price(subject_id)

    if is_free or price_points <= 0:
        return {
            "has_access": True,
            "is_free": True,
            "price_points": 0,
            "price_vnd": 0,
        }

    purchase = db.studyhub_purchases.find_one(
        {
            "user_id": user_id,
            "subject_id": ObjectId(subject_id),
            "status": "active",
        }
    )

    return {
        "has_access": purchase is not None,
        "is_free": False,
        "price_points": price_points,
        "price_vnd": price_points * 1000,
        "purchased_at": purchase["purchased_at"].isoformat() if purchase else None,
    }
