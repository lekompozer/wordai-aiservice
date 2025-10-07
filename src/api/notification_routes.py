"""
Notification API Routes
InApp Notification System
"""

import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime

from src.middleware.auth import verify_firebase_token
from src.services.notification_manager import NotificationManager
from config.config import get_mongodb

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class NotificationResponse(BaseModel):
    """Notification response model"""

    notification_id: str
    user_id: str
    type: str
    title: str
    message: str
    data: Dict[str, Any]
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_notification_manager() -> NotificationManager:
    """Get NotificationManager instance"""
    db = get_mongodb()
    return NotificationManager(db=db)


# ============================================================================
# NOTIFICATION ENDPOINTS
# ============================================================================


@router.get("/list", response_model=List[NotificationResponse])
async def list_notifications(
    is_read: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get list of user's notifications

    **Query Parameters:**
    - `is_read`: Filter by read status (true/false/null for all)
    - `limit`: Maximum number of results (default: 50)
    - `offset`: Pagination offset (default: 0)

    **Response:**
    ```json
    [
        {
            "notification_id": "notif_abc123",
            "user_id": "firebase_uid",
            "type": "file_shared",
            "title": "File được chia sẻ",
            "message": "John đã chia sẻ file 'document.pdf' với bạn",
            "data": {
                "share_id": "share_xyz",
                "file_id": "file_abc",
                "filename": "document.pdf",
                "owner_name": "John"
            },
            "is_read": false,
            "created_at": "2025-10-07T10:00:00Z",
            "read_at": null
        }
    ]
    ```
    """
    try:
        user_id = user_data.get("uid")
        notification_manager = get_notification_manager()

        notifications = await asyncio.to_thread(
            notification_manager.list_user_notifications,
            user_id=user_id,
            is_read=is_read,
            limit=limit,
            offset=offset,
        )

        result = []
        for notif in notifications:
            result.append(NotificationResponse(**notif))

        logger.info(f"✅ Listed {len(result)} notifications for user {user_id}")
        return result

    except Exception as e:
        logger.error(f"❌ Error listing notifications: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/unread-count", response_model=Dict[str, Any])
async def get_unread_count(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get count of unread notifications

    **Response:**
    ```json
    {
        "count": 5
    }
    ```
    """
    try:
        user_id = user_data.get("uid")
        notification_manager = get_notification_manager()

        count = await asyncio.to_thread(
            notification_manager.get_unread_count, user_id=user_id
        )

        return {"count": count}

    except Exception as e:
        logger.error(f"❌ Error getting unread count: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{notification_id}/read", response_model=Dict[str, Any])
async def mark_notification_as_read(
    notification_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Mark a notification as read

    **Response:**
    ```json
    {
        "success": true,
        "message": "Notification marked as read"
    }
    ```
    """
    try:
        user_id = user_data.get("uid")
        notification_manager = get_notification_manager()

        success = await asyncio.to_thread(
            notification_manager.mark_notification_as_read,
            notification_id=notification_id,
            user_id=user_id,
        )

        if success:
            return {
                "success": True,
                "message": "Notification marked as read",
            }
        else:
            raise HTTPException(status_code=404, detail="Notification not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error marking notification as read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/read-all", response_model=Dict[str, Any])
async def mark_all_as_read(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Mark all notifications as read

    **Response:**
    ```json
    {
        "success": true,
        "count": 5,
        "message": "5 notifications marked as read"
    }
    ```
    """
    try:
        user_id = user_data.get("uid")
        notification_manager = get_notification_manager()

        count = await asyncio.to_thread(
            notification_manager.mark_all_as_read, user_id=user_id
        )

        return {
            "success": True,
            "count": count,
            "message": f"{count} notifications marked as read",
        }

    except Exception as e:
        logger.error(f"❌ Error marking all notifications as read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{notification_id}", response_model=Dict[str, Any])
async def delete_notification(
    notification_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Delete a notification

    **Response:**
    ```json
    {
        "success": true,
        "message": "Notification deleted"
    }
    ```
    """
    try:
        user_id = user_data.get("uid")
        notification_manager = get_notification_manager()

        success = await asyncio.to_thread(
            notification_manager.delete_notification,
            notification_id=notification_id,
            user_id=user_id,
        )

        if success:
            return {
                "success": True,
                "message": "Notification deleted",
            }
        else:
            raise HTTPException(status_code=404, detail="Notification not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/initialize", response_model=Dict[str, Any])
async def initialize_notification_indexes(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Create MongoDB indexes for notifications collection

    **Run this once during deployment.**
    """
    try:
        notification_manager = get_notification_manager()
        success = await asyncio.to_thread(notification_manager.create_indexes)

        if success:
            return {
                "success": True,
                "message": "Notification indexes created successfully",
            }
        else:
            return {"success": False, "message": "Failed to create indexes"}

    except Exception as e:
        logger.error(f"❌ Error creating notification indexes: {e}")
        raise HTTPException(status_code=500, detail=str(e))
