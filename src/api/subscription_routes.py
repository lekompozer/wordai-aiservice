"""
Subscription and Points Management API Routes

This module provides endpoints for users to check their subscription status,
points balance, usage statistics, and transaction history.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.middleware.firebase_auth import require_auth
from src.services.subscription_service import get_subscription_service
from src.services.points_service import get_points_service
from src.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(prefix="/api/subscription", tags=["Subscription & Points"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================


class SubscriptionInfoResponse(BaseModel):
    """Complete subscription and points information"""

    # Plan Information
    plan: str = Field(description="Subscription plan: free, premium, pro, vip")
    status: str = Field(description="Subscription status: active, expired, cancelled")

    # Points Balance
    points_total: int = Field(description="Total points ever received")
    points_remaining: int = Field(description="Current available points")
    points_used: int = Field(description="Total points spent")

    # Usage Limits & Current Usage
    daily_chat_limit: int = Field(description="Daily free chat limit (Deepseek)")
    daily_chat_count: int = Field(description="Chats used today")
    daily_chat_remaining: int = Field(description="Free chats remaining today")

    storage_limit_mb: float = Field(description="Total storage limit in MB")
    storage_used_mb: float = Field(description="Storage currently used in MB")
    storage_remaining_mb: float = Field(description="Storage remaining in MB")

    documents_limit: int = Field(description="Maximum number of documents")
    documents_count: int = Field(description="Current number of documents")
    documents_remaining: int = Field(description="Documents remaining")

    upload_files_limit: int = Field(description="Maximum number of uploaded files")
    upload_files_count: int = Field(description="Current number of files")
    upload_files_remaining: int = Field(description="Files remaining")

    # Subscription Dates
    start_date: datetime = Field(description="Subscription start date")
    end_date: Optional[datetime] = Field(
        description="Subscription end date (None for free plan)"
    )
    auto_renew: bool = Field(description="Whether subscription auto-renews")

    # Metadata
    last_reset_date: datetime = Field(description="Last daily counter reset date")
    updated_at: datetime = Field(description="Last update timestamp")


class PointsTransactionResponse(BaseModel):
    """Points transaction history item"""

    transaction_id: str
    transaction_type: str = Field(
        description="spend, earn, grant, refund, bonus, purchase"
    )
    points: int = Field(
        description="Points amount (positive for earn, negative for spend)"
    )
    service: Optional[str] = Field(description="Service that used points")
    description: str = Field(description="Transaction description")
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class PointsHistoryResponse(BaseModel):
    """Paginated points transaction history"""

    transactions: list[PointsTransactionResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class UsageSummaryResponse(BaseModel):
    """Quick usage summary for dashboard"""

    points_remaining: int
    daily_chats_remaining: int
    storage_percentage: float = Field(description="Storage used as percentage (0-100)")
    documents_percentage: float = Field(
        description="Documents used as percentage (0-100)"
    )
    plan: str
    is_premium: bool = Field(description="Whether user has any paid plan")


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("/info", response_model=SubscriptionInfoResponse)
async def get_subscription_info(
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    Get complete subscription and points information for current user.

    This endpoint returns all information needed for the frontend to display:
    - Points balance (total, remaining, used)
    - Usage limits and current usage (storage, documents, files, chats)
    - Subscription plan and status
    - Subscription dates

    **Returns:**
    - Complete subscription information with points and usage statistics

    **Example Response:**
    ```json
    {
        "plan": "free",
        "status": "active",
        "points_total": 10,
        "points_remaining": 8,
        "points_used": 2,
        "daily_chat_limit": 10,
        "daily_chat_count": 3,
        "daily_chat_remaining": 7,
        "storage_limit_mb": 50,
        "storage_used_mb": 12.5,
        "storage_remaining_mb": 37.5,
        ...
    }
    ```
    """
    try:
        firebase_uid = user_data["firebase_uid"]
        subscription_service = get_subscription_service()

        # Get or create subscription
        subscription = await subscription_service.get_or_create_subscription(
            firebase_uid
        )

        # Calculate remaining values
        storage_remaining = max(
            0, subscription.storage_limit_mb - subscription.storage_used_mb
        )
        documents_remaining = max(
            0, subscription.documents_limit - subscription.documents_count
        )
        upload_files_remaining = max(
            0, subscription.upload_files_limit - subscription.upload_files_count
        )
        daily_chat_remaining = max(
            0, subscription.daily_chat_limit - subscription.daily_chat_count
        )

        return SubscriptionInfoResponse(
            # Plan info
            plan=subscription.plan,
            status=subscription.status,
            # Points
            points_total=subscription.points_total,
            points_remaining=subscription.points_remaining,
            points_used=subscription.points_total - subscription.points_remaining,
            # Daily chats
            daily_chat_limit=subscription.daily_chat_limit,
            daily_chat_count=subscription.daily_chat_count,
            daily_chat_remaining=daily_chat_remaining,
            # Storage
            storage_limit_mb=subscription.storage_limit_mb,
            storage_used_mb=subscription.storage_used_mb,
            storage_remaining_mb=storage_remaining,
            # Documents
            documents_limit=subscription.documents_limit,
            documents_count=subscription.documents_count,
            documents_remaining=documents_remaining,
            # Files
            upload_files_limit=subscription.upload_files_limit,
            upload_files_count=subscription.upload_files_count,
            upload_files_remaining=upload_files_remaining,
            # Dates
            start_date=subscription.start_date,
            end_date=subscription.end_date,
            auto_renew=subscription.auto_renew,
            last_reset_date=subscription.last_reset_date,
            updated_at=subscription.updated_at,
        )

    except Exception as e:
        logger.error(f"❌ Error fetching subscription info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscription info: {str(e)}",
        )


@router.get("/usage-summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    Get quick usage summary for dashboard display.

    Returns simplified usage information perfect for displaying
    in a dashboard header or sidebar.

    **Returns:**
    - Points remaining
    - Daily chats remaining
    - Storage usage percentage
    - Documents usage percentage
    - Plan name
    - Premium status

    **Example Response:**
    ```json
    {
        "points_remaining": 8,
        "daily_chats_remaining": 7,
        "storage_percentage": 25.0,
        "documents_percentage": 30.0,
        "plan": "free",
        "is_premium": false
    }
    ```
    """
    try:
        firebase_uid = user_data["firebase_uid"]
        subscription_service = get_subscription_service()

        subscription = await subscription_service.get_or_create_subscription(
            firebase_uid
        )

        # Calculate percentages
        storage_percentage = (
            (subscription.storage_used_mb / subscription.storage_limit_mb * 100)
            if subscription.storage_limit_mb > 0
            else 0
        )
        documents_percentage = (
            (subscription.documents_count / subscription.documents_limit * 100)
            if subscription.documents_limit > 0
            else 0
        )

        daily_chats_remaining = max(
            0, subscription.daily_chat_limit - subscription.daily_chat_count
        )

        return UsageSummaryResponse(
            points_remaining=subscription.points_remaining,
            daily_chats_remaining=daily_chats_remaining,
            storage_percentage=round(storage_percentage, 1),
            documents_percentage=round(documents_percentage, 1),
            plan=subscription.plan,
            is_premium=subscription.plan != "free",
        )

    except Exception as e:
        logger.error(f"❌ Error fetching usage summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch usage summary: {str(e)}",
        )


@router.get("/points/history", response_model=PointsHistoryResponse)
async def get_points_history(
    page: int = 1,
    limit: int = 20,
    transaction_type: Optional[str] = None,
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    Get points transaction history with pagination.

    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Items per page (default: 20, max: 100)
    - `transaction_type`: Filter by type (spend, earn, grant, refund, bonus, purchase)

    **Returns:**
    - List of transactions with pagination info

    **Example Response:**
    ```json
    {
        "transactions": [
            {
                "transaction_id": "txn_123",
                "transaction_type": "spend",
                "points": -2,
                "service": "ai_chat",
                "description": "Chat with Claude (Premium model)",
                "created_at": "2025-11-06T10:30:00Z"
            }
        ],
        "total": 15,
        "page": 1,
        "limit": 20,
        "has_more": false
    }
    ```
    """
    try:
        firebase_uid = user_data["firebase_uid"]
        points_service = get_points_service()

        # Validate limit
        limit = min(limit, 100)  # Max 100 items per page

        # Get transaction history
        history = await points_service.get_transaction_history(
            user_id=firebase_uid,
            transaction_type=transaction_type,
            page=page,
            limit=limit,
        )

        # Convert to response format
        transactions = [
            PointsTransactionResponse(
                transaction_id=str(txn.get("_id", "")),
                transaction_type=txn["transaction_type"],
                points=txn["points"],
                service=txn.get("service"),
                description=txn["description"],
                created_at=txn["created_at"],
                metadata=txn.get("metadata"),
            )
            for txn in history["transactions"]
        ]

        return PointsHistoryResponse(
            transactions=transactions,
            total=history["total"],
            page=page,
            limit=limit,
            has_more=history["total"] > (page * limit),
        )

    except Exception as e:
        logger.error(f"❌ Error fetching points history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch points history: {str(e)}",
        )


@router.get("/points/balance")
async def get_points_balance(
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    Get simple points balance (quick endpoint for real-time updates).

    **Returns:**
    - points_remaining: Current available points
    - points_total: Total points ever received

    **Example Response:**
    ```json
    {
        "points_remaining": 8,
        "points_total": 10,
        "points_used": 2
    }
    ```
    """
    try:
        firebase_uid = user_data["firebase_uid"]
        subscription_service = get_subscription_service()

        subscription = await subscription_service.get_or_create_subscription(
            firebase_uid
        )

        return {
            "points_remaining": subscription.points_remaining,
            "points_total": subscription.points_total,
            "points_used": subscription.points_total - subscription.points_remaining,
        }

    except Exception as e:
        logger.error(f"❌ Error fetching points balance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch points balance: {str(e)}",
        )
