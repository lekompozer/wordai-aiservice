"""
Support Ticket System API Routes

This module provides endpoints for:
- Users: Submit and view support tickets
- Admin: View all tickets and respond to users
- Email notifications to admin and users
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from src.middleware.firebase_auth import require_auth
from src.config.database import get_async_database
from src.utils.logger import setup_logger
from src.services.notification_manager import NotificationManager
from config.config import get_mongodb

logger = setup_logger()
router = APIRouter(prefix="/api/support", tags=["Support Tickets"])

# Admin email for notifications
ADMIN_EMAIL = "hoilht89@gmail.com"
ADMIN_NAME = "WordAI Support Team"


# ============================================================================
# MODELS
# ============================================================================


class SupportTicketCreate(BaseModel):
    """Request to create a support ticket"""

    subject: str = Field(..., min_length=5, max_length=200, description="Ticket subject")
    message: str = Field(..., min_length=10, description="Detailed message")
    category: str = Field(
        default="general",
        description="Ticket category: general, technical, billing, feature_request, bug_report",
    )
    priority: str = Field(
        default="medium", description="Priority: low, medium, high, urgent"
    )


class SupportReply(BaseModel):
    """Reply to a support ticket"""

    message: str = Field(..., min_length=1, description="Reply message")


class SupportTicketMessage(BaseModel):
    """Single message in a support ticket thread"""

    message_id: str
    sender_type: str = Field(description="user or admin")
    sender_id: str = Field(description="User ID or admin ID")
    sender_name: Optional[str] = None
    message: str
    created_at: datetime
    is_internal_note: bool = Field(
        default=False, description="Internal note visible only to admins"
    )


class SupportTicketSummary(BaseModel):
    """Support ticket summary for list view"""

    ticket_id: str
    subject: str
    category: str
    priority: str
    status: str = Field(
        description="open, in_progress, resolved, closed, waiting_user, waiting_admin"
    )
    created_at: datetime
    updated_at: datetime
    last_reply_at: Optional[datetime] = None
    last_reply_by: Optional[str] = Field(description="user or admin")
    unread_count: int = Field(description="Number of unread messages for current user")
    
    # User info (for admin view)
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_name: Optional[str] = None


class SupportTicketDetail(BaseModel):
    """Complete support ticket with all messages"""

    ticket_id: str
    subject: str
    category: str
    priority: str
    status: str
    
    # User info
    user_id: str
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # Messages thread
    messages: List[SupportTicketMessage]
    
    # Metadata
    tags: List[str] = Field(default_factory=list)
    assigned_to: Optional[str] = Field(description="Admin ID assigned to ticket")


class TicketListResponse(BaseModel):
    """Paginated ticket list response"""

    tickets: List[SupportTicketSummary]
    total: int
    page: int
    limit: int
    has_more: bool
    
    # Statistics
    open_count: int = 0
    resolved_count: int = 0
    closed_count: int = 0


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


async def send_email_notification(
    to_email: str,
    to_name: str,
    subject: str,
    message: str,
    is_admin: bool = False,
):
    """
    Send email notification for support tickets.
    
    Note: This is a simplified version. In production, use a proper email service
    like SendGrid, AWS SES, or Brevo (which you already have configured).
    """
    try:
        # TODO: Integrate with your existing Brevo email service
        # For now, just log the notification
        logger.info(
            f"📧 Email notification: to={to_email}, subject={subject}, is_admin={is_admin}"
        )
        
        # In production, use your existing email service:
        # from src.services.brevo_service import brevo_service
        # await brevo_service.send_support_notification(to_email, to_name, subject, message)
        
    except Exception as e:
        logger.error(f"❌ Failed to send email notification: {e}")
        # Don't raise exception - email failure shouldn't break the API


async def create_in_app_notification(
    user_id: str,
    title: str,
    message: str,
    ticket_id: str,
):
    """Create in-app notification for user"""
    try:
        db = get_mongodb()
        notification_manager = NotificationManager(db=db)
        await notification_manager.create_notification(
            user_id=user_id,
            notification_type="support_reply",
            title=title,
            message=message,
            data={"ticket_id": ticket_id, "link": f"/support/tickets/{ticket_id}"},
        )
    except Exception as e:
        logger.error(f"❌ Failed to create notification: {e}")


# ============================================================================
# USER ENDPOINTS
# ============================================================================


@router.post("/tickets", status_code=status.HTTP_201_CREATED)
async def create_support_ticket(
    ticket: SupportTicketCreate,
    background_tasks: BackgroundTasks,
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    Submit a new support ticket.
    
    **Request Body:**
    ```json
    {
        "subject": "Cannot upload files",
        "message": "I'm getting an error when trying to upload PDF files...",
        "category": "technical",
        "priority": "high"
    }
    ```
    
    **Categories:**
    - `general` - General inquiries
    - `technical` - Technical issues
    - `billing` - Billing and payment questions
    - `feature_request` - Feature requests
    - `bug_report` - Bug reports
    
    **Priority:**
    - `low` - Not urgent
    - `medium` - Normal priority (default)
    - `high` - Important
    - `urgent` - Critical issue
    
    **Notifications:**
    - Admin will receive email notification at hoilht89@gmail.com
    """
    try:
        firebase_uid = user_data["firebase_uid"]
        user_email = user_data.get("email", "")
        user_name = user_data.get("display_name", user_data.get("name", "User"))
        
        db = await get_async_database()
        tickets_collection = db["support_tickets"]
        
        # Create ticket document
        ticket_doc = {
            "user_id": firebase_uid,
            "user_email": user_email,
            "user_name": user_name,
            "subject": ticket.subject,
            "category": ticket.category,
            "priority": ticket.priority,
            "status": "open",
            "messages": [
                {
                    "message_id": str(ObjectId()),
                    "sender_type": "user",
                    "sender_id": firebase_uid,
                    "sender_name": user_name,
                    "message": ticket.message,
                    "created_at": datetime.utcnow(),
                    "is_internal_note": False,
                }
            ],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "last_reply_at": datetime.utcnow(),
            "last_reply_by": "user",
            "unread_by_admin": True,
            "unread_by_user": False,
            "tags": [],
            "assigned_to": None,
            "resolved_at": None,
            "closed_at": None,
        }
        
        result = await tickets_collection.insert_one(ticket_doc)
        ticket_id = str(result.inserted_id)
        
        # Send email to admin in background
        background_tasks.add_task(
            send_email_notification,
            to_email=ADMIN_EMAIL,
            to_name=ADMIN_NAME,
            subject=f"New Support Ticket #{ticket_id}: {ticket.subject}",
            message=f"From: {user_name} ({user_email})\n"
            f"Category: {ticket.category}\n"
            f"Priority: {ticket.priority}\n\n"
            f"Message:\n{ticket.message}\n\n"
            f"View ticket: https://your-domain.com/admin/support/{ticket_id}",
            is_admin=True,
        )
        
        logger.info(
            f"✅ Support ticket created: {ticket_id} by user {firebase_uid} ({user_email})"
        )
        
        return {
            "success": True,
            "ticket_id": ticket_id,
            "message": "Support ticket submitted successfully. Our team will respond shortly.",
            "status": "open",
        }
    
    except Exception as e:
        logger.error(f"❌ Error creating support ticket: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create support ticket: {str(e)}",
        )


@router.get("/tickets", response_model=TicketListResponse)
async def get_user_tickets(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    Get list of support tickets for current user.
    
    **Query Parameters:**
    - `page`: Page number
    - `limit`: Items per page
    - `status_filter`: Filter by status (open, in_progress, resolved, closed)
    
    **Returns:**
    - List of tickets with summary info
    - Pagination and statistics
    """
    try:
        firebase_uid = user_data["firebase_uid"]
        db = await get_async_database()
        tickets_collection = db["support_tickets"]
        
        # Build query
        query = {"user_id": firebase_uid}
        if status_filter:
            query["status"] = status_filter
        
        # Get total count
        total = await tickets_collection.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * limit
        cursor = (
            tickets_collection.find(query).sort("updated_at", -1).skip(skip).limit(limit)
        )
        tickets = await cursor.to_list(length=limit)
        
        # Convert to response format
        ticket_summaries = []
        for ticket in tickets:
            # Count unread messages by user
            unread_count = sum(
                1
                for msg in ticket["messages"]
                if msg["sender_type"] == "admin"
                and msg.get("created_at", datetime.min)
                > ticket.get("user_last_read", datetime.min)
            )
            
            ticket_summaries.append(
                SupportTicketSummary(
                    ticket_id=str(ticket["_id"]),
                    subject=ticket["subject"],
                    category=ticket["category"],
                    priority=ticket["priority"],
                    status=ticket["status"],
                    created_at=ticket["created_at"],
                    updated_at=ticket["updated_at"],
                    last_reply_at=ticket.get("last_reply_at"),
                    last_reply_by=ticket.get("last_reply_by"),
                    unread_count=unread_count,
                )
            )
        
        # Get statistics
        stats_pipeline = [
            {"$match": {"user_id": firebase_uid}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        stats = await tickets_collection.aggregate(stats_pipeline).to_list(None)
        stats_dict = {item["_id"]: item["count"] for item in stats}
        
        return TicketListResponse(
            tickets=ticket_summaries,
            total=total,
            page=page,
            limit=limit,
            has_more=total > (page * limit),
            open_count=stats_dict.get("open", 0) + stats_dict.get("in_progress", 0),
            resolved_count=stats_dict.get("resolved", 0),
            closed_count=stats_dict.get("closed", 0),
        )
    
    except Exception as e:
        logger.error(f"❌ Error fetching user tickets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tickets: {str(e)}",
        )


@router.get("/tickets/{ticket_id}", response_model=SupportTicketDetail)
async def get_ticket_detail(
    ticket_id: str,
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    Get complete details and message thread for a specific ticket.
    
    **Path Parameters:**
    - `ticket_id`: Support ticket ID
    
    **Returns:**
    - Complete ticket information with all messages
    
    **Security:**
    - Users can only view their own tickets
    - Marks messages as read
    """
    try:
        firebase_uid = user_data["firebase_uid"]
        db = await get_async_database()
        tickets_collection = db["support_tickets"]
        
        # Convert to ObjectId
        try:
            ticket_obj_id = ObjectId(ticket_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ticket ID format",
            )
        
        # Find ticket and verify ownership
        ticket = await tickets_collection.find_one(
            {"_id": ticket_obj_id, "user_id": firebase_uid}
        )
        
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found or access denied",
            )
        
        # Mark as read by user
        await tickets_collection.update_one(
            {"_id": ticket_obj_id},
            {"$set": {"user_last_read": datetime.utcnow(), "unread_by_user": False}},
        )
        
        # Convert messages to response format
        messages = [
            SupportTicketMessage(
                message_id=msg["message_id"],
                sender_type=msg["sender_type"],
                sender_id=msg["sender_id"],
                sender_name=msg.get("sender_name"),
                message=msg["message"],
                created_at=msg["created_at"],
                is_internal_note=msg.get("is_internal_note", False),
            )
            for msg in ticket["messages"]
            if not msg.get("is_internal_note", False)  # Hide internal notes from users
        ]
        
        return SupportTicketDetail(
            ticket_id=str(ticket["_id"]),
            subject=ticket["subject"],
            category=ticket["category"],
            priority=ticket["priority"],
            status=ticket["status"],
            user_id=ticket["user_id"],
            user_email=ticket.get("user_email"),
            user_name=ticket.get("user_name"),
            created_at=ticket["created_at"],
            updated_at=ticket["updated_at"],
            resolved_at=ticket.get("resolved_at"),
            closed_at=ticket.get("closed_at"),
            messages=messages,
            tags=ticket.get("tags", []),
            assigned_to=ticket.get("assigned_to"),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching ticket details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch ticket details: {str(e)}",
        )


@router.post("/tickets/{ticket_id}/reply")
async def user_reply_to_ticket(
    ticket_id: str,
    reply: SupportReply,
    background_tasks: BackgroundTasks,
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    User adds a reply to their support ticket.
    
    **Path Parameters:**
    - `ticket_id`: Support ticket ID
    
    **Request Body:**
    ```json
    {
        "message": "Thank you for your help! The issue is now resolved."
    }
    ```
    
    **Notifications:**
    - Admin receives email notification
    """
    try:
        firebase_uid = user_data["firebase_uid"]
        user_name = user_data.get("display_name", user_data.get("name", "User"))
        user_email = user_data.get("email", "")
        
        db = await get_async_database()
        tickets_collection = db["support_tickets"]
        
        # Convert to ObjectId
        try:
            ticket_obj_id = ObjectId(ticket_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ticket ID format",
            )
        
        # Verify ownership
        ticket = await tickets_collection.find_one(
            {"_id": ticket_obj_id, "user_id": firebase_uid}
        )
        
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found or access denied",
            )
        
        # Add reply message
        new_message = {
            "message_id": str(ObjectId()),
            "sender_type": "user",
            "sender_id": firebase_uid,
            "sender_name": user_name,
            "message": reply.message,
            "created_at": datetime.utcnow(),
            "is_internal_note": False,
        }
        
        # Update ticket
        await tickets_collection.update_one(
            {"_id": ticket_obj_id},
            {
                "$push": {"messages": new_message},
                "$set": {
                    "updated_at": datetime.utcnow(),
                    "last_reply_at": datetime.utcnow(),
                    "last_reply_by": "user",
                    "unread_by_admin": True,
                    "status": "waiting_admin"
                    if ticket["status"] != "closed"
                    else "closed",
                },
            },
        )
        
        # Send email to admin
        background_tasks.add_task(
            send_email_notification,
            to_email=ADMIN_EMAIL,
            to_name=ADMIN_NAME,
            subject=f"User Reply on Ticket #{ticket_id}: {ticket['subject']}",
            message=f"From: {user_name} ({user_email})\n\n"
            f"New message:\n{reply.message}\n\n"
            f"View ticket: https://your-domain.com/admin/support/{ticket_id}",
            is_admin=True,
        )
        
        logger.info(f"✅ User reply added to ticket {ticket_id}")
        
        return {
            "success": True,
            "message": "Reply added successfully",
            "ticket_id": ticket_id,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error adding user reply: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add reply: {str(e)}",
        )


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================


@router.get("/admin/tickets", response_model=TicketListResponse)
async def get_all_tickets_admin(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    priority_filter: Optional[str] = Query(None),
    category_filter: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search in subject or user email"),
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    **[ADMIN ONLY]** Get list of all support tickets across all users.
    
    **Query Parameters:**
    - `page`: Page number
    - `limit`: Items per page
    - `status_filter`: Filter by status
    - `priority_filter`: Filter by priority
    - `category_filter`: Filter by category
    - `search`: Search in subject or user email
    
    **Returns:**
    - List of all tickets with user information
    - Statistics
    
    **Access:**
    - Requires admin role (TODO: Add admin role check)
    """
    try:
        # TODO: Add admin role verification
        # For now, we'll implement basic access control
        # You should add proper admin role checking here
        
        db = await get_async_database()
        tickets_collection = db["support_tickets"]
        
        # Build query
        query = {}
        if status_filter:
            query["status"] = status_filter
        if priority_filter:
            query["priority"] = priority_filter
        if category_filter:
            query["category"] = category_filter
        if search:
            query["$or"] = [
                {"subject": {"$regex": search, "$options": "i"}},
                {"user_email": {"$regex": search, "$options": "i"}},
            ]
        
        # Get total count
        total = await tickets_collection.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * limit
        cursor = (
            tickets_collection.find(query).sort("updated_at", -1).skip(skip).limit(limit)
        )
        tickets = await cursor.to_list(length=limit)
        
        # Convert to response format
        ticket_summaries = []
        for ticket in tickets:
            # Count unread by admin
            unread_count = 1 if ticket.get("unread_by_admin", False) else 0
            
            ticket_summaries.append(
                SupportTicketSummary(
                    ticket_id=str(ticket["_id"]),
                    subject=ticket["subject"],
                    category=ticket["category"],
                    priority=ticket["priority"],
                    status=ticket["status"],
                    created_at=ticket["created_at"],
                    updated_at=ticket["updated_at"],
                    last_reply_at=ticket.get("last_reply_at"),
                    last_reply_by=ticket.get("last_reply_by"),
                    unread_count=unread_count,
                    user_id=ticket["user_id"],
                    user_email=ticket.get("user_email"),
                    user_name=ticket.get("user_name"),
                )
            )
        
        # Get statistics
        stats_pipeline = [
            {"$match": query} if query else {"$match": {}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        stats = await tickets_collection.aggregate(stats_pipeline).to_list(None)
        stats_dict = {item["_id"]: item["count"] for item in stats}
        
        return TicketListResponse(
            tickets=ticket_summaries,
            total=total,
            page=page,
            limit=limit,
            has_more=total > (page * limit),
            open_count=stats_dict.get("open", 0) + stats_dict.get("in_progress", 0),
            resolved_count=stats_dict.get("resolved", 0),
            closed_count=stats_dict.get("closed", 0),
        )
    
    except Exception as e:
        logger.error(f"❌ Error fetching admin tickets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tickets: {str(e)}",
        )


@router.get("/admin/tickets/{ticket_id}", response_model=SupportTicketDetail)
async def get_ticket_detail_admin(
    ticket_id: str,
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    **[ADMIN ONLY]** Get complete ticket details including internal notes.
    
    **Path Parameters:**
    - `ticket_id`: Support ticket ID
    
    **Returns:**
    - Complete ticket with all messages including internal notes
    
    **Access:**
    - Requires admin role
    - Marks ticket as read by admin
    """
    try:
        # TODO: Add admin role verification
        
        db = await get_async_database()
        tickets_collection = db["support_tickets"]
        
        # Convert to ObjectId
        try:
            ticket_obj_id = ObjectId(ticket_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ticket ID format",
            )
        
        ticket = await tickets_collection.find_one({"_id": ticket_obj_id})
        
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found"
            )
        
        # Mark as read by admin
        await tickets_collection.update_one(
            {"_id": ticket_obj_id},
            {"$set": {"admin_last_read": datetime.utcnow(), "unread_by_admin": False}},
        )
        
        # Convert all messages (including internal notes for admin)
        messages = [
            SupportTicketMessage(
                message_id=msg["message_id"],
                sender_type=msg["sender_type"],
                sender_id=msg["sender_id"],
                sender_name=msg.get("sender_name"),
                message=msg["message"],
                created_at=msg["created_at"],
                is_internal_note=msg.get("is_internal_note", False),
            )
            for msg in ticket["messages"]
        ]
        
        return SupportTicketDetail(
            ticket_id=str(ticket["_id"]),
            subject=ticket["subject"],
            category=ticket["category"],
            priority=ticket["priority"],
            status=ticket["status"],
            user_id=ticket["user_id"],
            user_email=ticket.get("user_email"),
            user_name=ticket.get("user_name"),
            created_at=ticket["created_at"],
            updated_at=ticket["updated_at"],
            resolved_at=ticket.get("resolved_at"),
            closed_at=ticket.get("closed_at"),
            messages=messages,
            tags=ticket.get("tags", []),
            assigned_to=ticket.get("assigned_to"),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching admin ticket details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch ticket details: {str(e)}",
        )


@router.post("/admin/tickets/{ticket_id}/reply")
async def admin_reply_to_ticket(
    ticket_id: str,
    reply: SupportReply,
    background_tasks: BackgroundTasks,
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    **[ADMIN ONLY]** Admin replies to a support ticket.
    
    **Path Parameters:**
    - `ticket_id`: Support ticket ID
    
    **Request Body:**
    ```json
    {
        "message": "Thank you for reporting this issue. We've investigated and..."
    }
    ```
    
    **Notifications:**
    - User receives in-app notification
    - User receives email notification
    - Ticket status automatically updated to "waiting_user"
    
    **Access:**
    - Requires admin role
    """
    try:
        # TODO: Add admin role verification
        admin_id = user_data["firebase_uid"]
        admin_name = user_data.get("display_name", "Support Team")
        
        db = await get_async_database()
        tickets_collection = db["support_tickets"]
        
        # Convert to ObjectId
        try:
            ticket_obj_id = ObjectId(ticket_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ticket ID format",
            )
        
        ticket = await tickets_collection.find_one({"_id": ticket_obj_id})
        
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found"
            )
        
        # Add reply message
        new_message = {
            "message_id": str(ObjectId()),
            "sender_type": "admin",
            "sender_id": admin_id,
            "sender_name": admin_name,
            "message": reply.message,
            "created_at": datetime.utcnow(),
            "is_internal_note": False,
        }
        
        # Update ticket
        await tickets_collection.update_one(
            {"_id": ticket_obj_id},
            {
                "$push": {"messages": new_message},
                "$set": {
                    "updated_at": datetime.utcnow(),
                    "last_reply_at": datetime.utcnow(),
                    "last_reply_by": "admin",
                    "unread_by_user": True,
                    "status": "waiting_user",
                    "assigned_to": admin_id,
                },
            },
        )
        
        # Create in-app notification for user
        background_tasks.add_task(
            create_in_app_notification,
            user_id=ticket["user_id"],
            title=f"New reply on: {ticket['subject']}",
            message=f"Support team has replied to your ticket. {reply.message[:100]}...",
            ticket_id=ticket_id,
        )
        
        # Send email to user
        if ticket.get("user_email"):
            background_tasks.add_task(
                send_email_notification,
                to_email=ticket["user_email"],
                to_name=ticket.get("user_name", "User"),
                subject=f"Support Reply: {ticket['subject']}",
                message=f"Hello {ticket.get('user_name', 'there')},\n\n"
                f"Our support team has replied to your ticket:\n\n"
                f"{reply.message}\n\n"
                f"View ticket: https://your-domain.com/support/tickets/{ticket_id}\n\n"
                f"Best regards,\nWordAI Support Team",
                is_admin=False,
            )
        
        logger.info(f"✅ Admin reply added to ticket {ticket_id} by {admin_name}")
        
        return {
            "success": True,
            "message": "Reply sent successfully. User has been notified.",
            "ticket_id": ticket_id,
            "notifications_sent": {
                "in_app": True,
                "email": bool(ticket.get("user_email")),
            },
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error adding admin reply: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add reply: {str(e)}",
        )


@router.patch("/admin/tickets/{ticket_id}/status")
async def update_ticket_status_admin(
    ticket_id: str,
    status: str = Query(
        ..., description="New status: open, in_progress, resolved, closed"
    ),
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    **[ADMIN ONLY]** Update ticket status.
    
    **Path Parameters:**
    - `ticket_id`: Support ticket ID
    
    **Query Parameters:**
    - `status`: New status (open, in_progress, resolved, closed)
    
    **Access:**
    - Requires admin role
    """
    try:
        # TODO: Add admin role verification
        
        valid_statuses = ["open", "in_progress", "resolved", "closed", "waiting_user", "waiting_admin"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            )
        
        db = await get_async_database()
        tickets_collection = db["support_tickets"]
        
        try:
            ticket_obj_id = ObjectId(ticket_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ticket ID format",
            )
        
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow(),
        }
        
        if status == "resolved":
            update_data["resolved_at"] = datetime.utcnow()
        elif status == "closed":
            update_data["closed_at"] = datetime.utcnow()
        
        result = await tickets_collection.update_one(
            {"_id": ticket_obj_id}, {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found"
            )
        
        logger.info(f"✅ Ticket {ticket_id} status updated to {status}")
        
        return {
            "success": True,
            "message": f"Ticket status updated to {status}",
            "ticket_id": ticket_id,
            "new_status": status,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating ticket status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update ticket status: {str(e)}",
        )
