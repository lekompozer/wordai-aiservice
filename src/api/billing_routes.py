"""
Billing History API Routes

This module provides endpoints for users to view their payment/billing history.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from bson import ObjectId

from src.middleware.firebase_auth import require_auth
from src.config.database import get_async_database
from src.utils.logger import setup_logger

logger = setup_logger()
router = APIRouter(prefix="/api/billing", tags=["Billing & Payment History"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================


class BillingHistoryItem(BaseModel):
    """Single billing/payment history record"""

    payment_id: str = Field(description="Unique payment ID")
    order_invoice_number: str = Field(description="Invoice number (WA-xxx)")
    
    # Payment details
    amount: int = Field(description="Amount in VND")
    currency: str = Field(default="VND")
    
    # Subscription purchased
    plan: str = Field(description="Plan purchased: premium, pro, vip")
    duration: str = Field(description="Duration: 3_months, 12_months")
    
    # Payment status
    status: str = Field(
        description="Payment status: pending, completed, failed, cancelled, refunded"
    )
    payment_method: Optional[str] = Field(
        description="Payment method: BANK_TRANSFER, VISA, MOMO, etc."
    )
    
    # Dates
    created_at: datetime = Field(description="Order creation date")
    paid_at: Optional[datetime] = Field(description="Payment completion date")
    cancelled_at: Optional[datetime] = Field(description="Cancellation date")
    refunded_at: Optional[datetime] = Field(description="Refund date")
    
    # Additional info
    notes: Optional[str] = Field(description="Additional notes")
    manually_processed: bool = Field(
        default=False, description="Whether processed manually by admin"
    )


class BillingHistoryResponse(BaseModel):
    """Paginated billing history response"""

    payments: List[BillingHistoryItem]
    total: int = Field(description="Total number of payments")
    page: int
    limit: int
    has_more: bool
    
    # Summary statistics
    total_spent: int = Field(description="Total amount spent (VND)")
    completed_payments: int = Field(description="Number of completed payments")
    pending_payments: int = Field(description="Number of pending payments")


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("/history", response_model=BillingHistoryResponse)
async def get_billing_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(
        None,
        description="Filter by status: pending, completed, failed, cancelled, refunded",
    ),
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    Get billing/payment history for current user with pagination.
    
    Returns all payment records including:
    - Completed payments
    - Pending payments (awaiting confirmation)
    - Failed/cancelled payments
    - Refunded payments
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Items per page (default: 20, max: 100)
    - `status_filter`: Filter by payment status
    
    **Returns:**
    - List of payment records with full details
    - Pagination information
    - Summary statistics
    
    **Example Response:**
    ```json
    {
        "payments": [
            {
                "payment_id": "pay_123",
                "order_invoice_number": "WA-1730123456-abc",
                "amount": 279000,
                "currency": "VND",
                "plan": "premium",
                "duration": "3_months",
                "status": "completed",
                "payment_method": "BANK_TRANSFER",
                "created_at": "2025-11-05T09:30:00Z",
                "paid_at": "2025-11-05T09:45:00Z",
                "notes": null,
                "manually_processed": false
            }
        ],
        "total": 5,
        "page": 1,
        "limit": 20,
        "has_more": false,
        "total_spent": 1395000,
        "completed_payments": 4,
        "pending_payments": 1
    }
    ```
    """
    try:
        firebase_uid = user_data["firebase_uid"]
        db = await get_async_database()
        payments_collection = db["payments"]
        
        # Build query
        query = {"user_id": firebase_uid}
        if status_filter:
            query["status"] = status_filter
        
        # Get total count
        total = await payments_collection.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * limit
        cursor = payments_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        payments = await cursor.to_list(length=limit)
        
        # Convert to response format
        payment_items = []
        for payment in payments:
            payment_items.append(
                BillingHistoryItem(
                    payment_id=str(payment.get("_id")),
                    order_invoice_number=payment["order_invoice_number"],
                    amount=payment["amount"],
                    currency=payment.get("currency", "VND"),
                    plan=payment["plan"],
                    duration=payment["duration"],
                    status=payment["status"],
                    payment_method=payment.get("payment_method"),
                    created_at=payment["created_at"],
                    paid_at=payment.get("paid_at"),
                    cancelled_at=payment.get("cancelled_at"),
                    refunded_at=payment.get("refunded_at"),
                    notes=payment.get("notes"),
                    manually_processed=payment.get("manually_processed", False),
                )
            )
        
        # Calculate summary statistics
        # Total spent (only completed payments)
        completed_pipeline = [
            {"$match": {"user_id": firebase_uid, "status": "completed"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        ]
        completed_result = await payments_collection.aggregate(completed_pipeline).to_list(1)
        total_spent = completed_result[0]["total"] if completed_result else 0
        completed_count = completed_result[0]["count"] if completed_result else 0
        
        # Count pending payments
        pending_count = await payments_collection.count_documents(
            {"user_id": firebase_uid, "status": "pending"}
        )
        
        return BillingHistoryResponse(
            payments=payment_items,
            total=total,
            page=page,
            limit=limit,
            has_more=total > (page * limit),
            total_spent=total_spent,
            completed_payments=completed_count,
            pending_payments=pending_count,
        )
    
    except Exception as e:
        logger.error(f"❌ Error fetching billing history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch billing history: {str(e)}",
        )


@router.get("/history/{payment_id}")
async def get_payment_details(
    payment_id: str,
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    Get detailed information for a specific payment.
    
    **Path Parameters:**
    - `payment_id`: Payment ID
    
    **Returns:**
    - Complete payment record with all details
    
    **Security:**
    - Users can only view their own payments
    """
    try:
        firebase_uid = user_data["firebase_uid"]
        db = await get_async_database()
        payments_collection = db["payments"]
        
        # Convert to ObjectId if needed
        try:
            payment_obj_id = ObjectId(payment_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment ID format",
            )
        
        # Find payment and verify ownership
        payment = await payments_collection.find_one(
            {"_id": payment_obj_id, "user_id": firebase_uid}
        )
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found or access denied",
            )
        
        # Return full payment details
        return {
            "payment_id": str(payment["_id"]),
            "order_invoice_number": payment["order_invoice_number"],
            "amount": payment["amount"],
            "currency": payment.get("currency", "VND"),
            "plan": payment["plan"],
            "duration": payment["duration"],
            "status": payment["status"],
            "payment_method": payment.get("payment_method"),
            "created_at": payment["created_at"],
            "paid_at": payment.get("paid_at"),
            "cancelled_at": payment.get("cancelled_at"),
            "refunded_at": payment.get("refunded_at"),
            "expires_at": payment.get("expires_at"),
            "notes": payment.get("notes"),
            "manually_processed": payment.get("manually_processed", False),
            "payment_reference": payment.get("payment_reference"),
            "subscription_id": payment.get("subscription_id"),
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching payment details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch payment details: {str(e)}",
        )
