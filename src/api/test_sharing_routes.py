"""
Online Test Sharing API Routes - Phase 4
Endpoints for sharing tests, managing invitations, and collaborative features
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, EmailStr

from src.middleware.auth import verify_firebase_token as require_auth
from src.services.test_sharing_service import get_test_sharing_service
from src.services.brevo_email_service import get_brevo_service
from src.services.notification_manager import NotificationManager
from config.config import get_mongodb  # ✅ Use standard config function

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tests", tags=["Online Tests - Phase 4: Sharing"])


# ========== Request/Response Models ==========


class ShareTestRequest(BaseModel):
    """Request to share test with users"""

    emails: Optional[List[EmailStr]] = Field(
        None,
        description="List of recipient email addresses",
        min_items=1,
        max_items=50,
    )
    sharee_emails: Optional[List[EmailStr]] = Field(
        None,
        description="Legacy field name (use 'emails' instead)",
        min_items=1,
        max_items=50,
    )
    deadline: Optional[datetime] = Field(
        None,
        description="Optional deadline for completing test (inherits test's deadline if null)",
    )
    message: Optional[str] = Field(
        None, description="Optional personal message", max_length=500
    )
    send_email: bool = Field(True, description="Send email notification to recipients")

    def get_emails(self) -> List[EmailStr]:
        """Get emails from either field"""
        if self.emails:
            return self.emails
        if self.sharee_emails:
            return self.sharee_emails
        raise ValueError("Either 'emails' or 'sharee_emails' must be provided")


class UpdateDeadlineRequest(BaseModel):
    """Request to update share deadline"""

    deadline: Optional[datetime] = Field(
        None, description="New deadline (null to remove)"
    )


# ========== Phase 4: Test Sharing Endpoints ==========


@router.post("/{test_id}/share")
async def share_test(
    test_id: str,
    request: ShareTestRequest,
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    **[HIGH PRIORITY] Share test with multiple users via email**

    Owner shares test with other users. Recipients receive email invitation
    with unique token to accept/decline.

    **Auth:** Owner only

    **Request Body:**
    ```json
    {
        "emails": ["user1@example.com", "user2@example.com"],
        "deadline": "2025-12-31T23:59:59Z",  // Optional
        "message": "Please complete this test",  // Optional
        "send_email": true
    }
    ```

    **Response:**
    ```json
    {
        "success": true,
        "message": "Test shared with 2 users",
        "shares": [
            {
                "share_id": "uuid",
                "sharee_email": "user1@example.com",
                "invitation_token": "uuid",
                "status": "pending",
                "created_at": "2025-11-03T..."
            }
        ]
    }
    ```

    **Business Logic:**
    1. Validate test exists and user is owner
    2. Remove duplicate emails
    3. Check if already shared (skip duplicates)
    4. Create share records with invitation tokens
    5. Send email invitations (if send_email=true)
    6. Create in-app notifications for registered users
    """
    try:
        user_id = user_data.get("uid")
        sharing_service = get_test_sharing_service()

        # Get emails from either field (backward compatibility)
        emails = request.get_emails()

        logger.info(
            f"📤 User {user_id} sharing test {test_id} with {len(emails)} users"
        )

        # Create shares
        shares = await asyncio.to_thread(
            sharing_service.share_test,
            test_id=test_id,
            sharer_id=user_id,
            sharee_emails=emails,
            deadline=request.deadline,
            message=request.message,
        )

        if not shares:
            return {
                "success": True,
                "message": "No new shares created (all already shared)",
                "shares": [],
            }

        # Send email invitations
        if request.send_email:
            brevo = get_brevo_service()
            db = get_mongodb()  # ✅ Use standard config function

            # Get test info
            test = db.online_tests.find_one({"test_id": test_id})
            if not test:
                raise HTTPException(status_code=404, detail="Test not found")

            # Get sharer info
            sharer = db.users.find_one({"firebase_uid": user_id})
            sharer_name = "Someone"
            if sharer:
                sharer_name = (
                    sharer.get("name")
                    or sharer.get("display_name")
                    or sharer.get("email", "Someone")
                )

            # Send emails
            for share in shares:
                recipient_email = share["sharee_email"]
                recipient_name = recipient_email.split("@")[0]

                # Get recipient user if exists
                recipient = db.users.find_one({"email": recipient_email})
                if recipient:
                    recipient_name = (
                        recipient.get("name")
                        or recipient.get("display_name")
                        or recipient_name
                    )

                    # Create in-app notification
                    try:
                        # ✅ Create NotificationManager instance inline
                        notification_manager = NotificationManager(db=db)
                        await asyncio.to_thread(
                            notification_manager.create_notification,
                            user_id=recipient.get("firebase_uid"),
                            notification_type="online_test_invitation",
                            title=f"Bài thi mới từ {sharer_name}",
                            message=f"Bạn được chia sẻ bài thi: {test['title']}",
                            action_url=f"/tests/{test_id}",
                            metadata={
                                "test_id": test_id,
                                "sharer_name": sharer_name,
                                "share_id": share["share_id"],
                            },
                        )
                        logger.info(
                            f"✅ Created in-app notification for {recipient_email}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"⚠️ Failed to create notification for {recipient_email}: {e}"
                        )

                # Send email
                try:
                    # Direct link to test (no invitation token needed)
                    test_url = "https://wordai.pro/tests"

                    deadline_str = None
                    if request.deadline:
                        deadline_str = request.deadline.strftime("%d/%m/%Y %H:%M")

                    await asyncio.to_thread(
                        brevo.send_test_invitation,
                        to_email=recipient_email,
                        recipient_name=recipient_name,
                        sharer_name=sharer_name,
                        test_title=test["title"],
                        test_id=test_id,
                        num_questions=len(test.get("questions", [])),
                        time_limit_minutes=test.get("time_limit_minutes"),
                        deadline=deadline_str,
                        message=request.message,
                        test_url=test_url,
                    )
                    logger.info(f"✅ Sent invitation email to {recipient_email}")
                except Exception as e:
                    logger.error(f"❌ Failed to send email to {recipient_email}: {e}")

        logger.info(f"✅ Created {len(shares)} test shares")

        return {
            "success": True,
            "message": f"Test shared with {len(shares)} users",
            "shares": shares,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to share test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/invitations")
async def list_my_invitations(
    status: Optional[str] = None,
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    **[HIGH PRIORITY] List test invitations (tests shared with me)**

    Get all test invitations for current user, with test details and sharer info.

    **Auth:** Required

    **Query Params:**
    - `status`: Filter by status (pending/accepted/completed/expired/declined)

    **Response:**
    ```json
    [
        {
            "share_id": "uuid",
            "invitation_token": "uuid",
            "status": "pending",
            "deadline": "2025-12-31T23:59:59Z",
            "message": "Please complete this test",
            "test": {
                "test_id": "test_123",
                "title": "JavaScript Basics",
                "num_questions": 10,
                "time_limit_minutes": 30
            },
            "sharer": {
                "name": "John Doe",
                "email": "john@example.com"
            },
            "created_at": "2025-11-03T...",
            "accepted_at": null,
            "has_completed": false
        }
    ]
    ```

    **Status Meanings:**
    - `pending`: Email sent, not yet accepted
    - `accepted`: User accepted, can take test
    - `completed`: User finished test
    - `expired`: Deadline passed
    - `declined`: User rejected invitation
    """
    try:
        user_id = user_data.get("uid")
        sharing_service = get_test_sharing_service()

        logger.info(f"📋 Listing invitations for user {user_id}, status={status}")

        invitations = await asyncio.to_thread(
            sharing_service.list_my_invitations, user_id=user_id, status=status
        )

        logger.info(f"✅ Found {len(invitations)} invitations")

        return invitations

    except Exception as e:
        logger.error(f"❌ Failed to list invitations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{test_id}/shares")
async def list_test_shares(
    test_id: str, user_data: Dict[str, Any] = Depends(require_auth)
):
    """
    **[MEDIUM PRIORITY] List all shares for a test (owner dashboard)**

    Get list of all users test is shared with, including submission status.

    **Auth:** Owner only

    **Response:**
    ```json
    [
        {
            "share_id": "uuid",
            "sharee_email": "user@example.com",
            "sharee": {
                "user_id": "user_123",
                "name": "Jane Doe",
                "email": "user@example.com"
            },
            "status": "completed",
            "deadline": "2025-12-31T23:59:59Z",
            "message": "Please complete this test",
            "created_at": "2025-11-03T...",
            "accepted_at": "2025-11-05T...",
            "completed_at": "2025-11-06T...",
            "submission": {
                "score": 8.5,
                "is_passed": true,
                "submitted_at": "2025-11-06T..."
            }
        }
    ]
    ```

    **Use Case:** Owner views who has access, who completed, scores
    """
    try:
        user_id = user_data.get("uid")
        sharing_service = get_test_sharing_service()

        logger.info(f"📋 Listing shares for test {test_id}, owner={user_id}")

        shares = await asyncio.to_thread(
            sharing_service.list_test_shares, test_id=test_id, owner_id=user_id
        )

        logger.info(f"✅ Found {len(shares)} shares")

        return shares

    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to list shares: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{test_id}/shares/{share_id}")
async def revoke_share(
    test_id: str, share_id: str, user_data: Dict[str, Any] = Depends(require_auth)
):
    """
    **[MEDIUM PRIORITY] Revoke access to shared test (soft delete)**

    Owner revokes user's access to test. User can no longer take the test.

    **Auth:** Owner only

    **Response:**
    ```json
    {
        "success": true,
        "message": "Share revoked successfully"
    }
    ```

    **Note:** This is a soft delete - changes status to 'declined'
    """
    try:
        user_id = user_data.get("uid")
        sharing_service = get_test_sharing_service()

        logger.info(f"🗑️ User {user_id} revoking share {share_id}")

        success = await asyncio.to_thread(
            sharing_service.revoke_share, share_id=share_id, owner_id=user_id
        )

        if success:
            logger.info(f"✅ Share revoked: {share_id}")
            return {"success": True, "message": "Share revoked successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to revoke share")

    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to revoke share: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{test_id}/shares/{share_id}/deadline")
async def update_share_deadline(
    test_id: str,
    share_id: str,
    request: UpdateDeadlineRequest,
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    **[LOW PRIORITY] Update deadline for a share**

    Owner can change or remove deadline for specific share.

    **Auth:** Owner only

    **Request Body:**
    ```json
    {
        "deadline": "2025-12-31T23:59:59Z"  // or null to remove
    }
    ```

    **Response:**
    ```json
    {
        "success": true,
        "message": "Deadline updated successfully"
    }
    ```
    """
    try:
        user_id = user_data.get("uid")
        sharing_service = get_test_sharing_service()

        logger.info(
            f"📅 User {user_id} updating deadline for share {share_id}: {request.deadline}"
        )

        success = await asyncio.to_thread(
            sharing_service.update_deadline,
            share_id=share_id,
            owner_id=user_id,
            new_deadline=request.deadline,
        )

        if success:
            logger.info(f"✅ Deadline updated for share {share_id}")
            return {"success": True, "message": "Deadline updated successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to update deadline")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to update deadline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shared-with-me")
async def list_shared_tests(
    status: Optional[str] = None,
    user_data: Dict[str, Any] = Depends(require_auth),
):
    """
    **[BONUS] List all tests shared with me (simplified view)**

    Alternative to /invitations - returns just the tests without full invitation details.

    **Auth:** Required

    **Query Params:**
    - `status`: Filter by status (pending/accepted/completed/expired/declined)

    **Response:**
    ```json
    [
        {
            "test_id": "test_123",
            "title": "JavaScript Basics",
            "num_questions": 10,
            "time_limit_minutes": 30,
            "sharer_name": "John Doe",
            "status": "accepted",
            "deadline": "2025-12-31T23:59:59Z",
            "has_completed": false
        }
    ]
    ```

    **Note:** This is a simplified version of /invitations for UI convenience
    """
    try:
        user_id = user_data.get("uid")
        sharing_service = get_test_sharing_service()

        logger.info(f"📚 Listing shared tests for user {user_id}")

        invitations = await asyncio.to_thread(
            sharing_service.list_my_invitations, user_id=user_id, status=status
        )

        # Simplify response
        simplified = [
            {
                "test_id": inv["test"]["test_id"],
                "title": inv["test"]["title"],
                "num_questions": inv["test"]["num_questions"],
                "time_limit_minutes": inv["test"].get("time_limit_minutes"),
                "sharer_name": inv["sharer"]["name"],
                "status": inv["status"],
                "deadline": inv.get("deadline"),
                "has_completed": inv.get("has_completed", False),
                "share_id": inv["share_id"],
                "created_at": inv["created_at"],
            }
            for inv in invitations
        ]

        return simplified

    except Exception as e:
        logger.error(f"❌ Failed to list shared tests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/shared/{test_id}")
async def delete_shared_test(
    test_id: str, user_data: Dict[str, Any] = Depends(require_auth)
):
    """
    **[HIGH PRIORITY] Delete shared test from user's list**

    User removes a test shared with them from their list.
    This is a soft delete (sets status to 'declined').

    **Auth:** Required

    **Response:**
    ```json
    {
        "success": true,
        "message": "Shared test removed successfully"
    }
    ```

    **Note:**
    - User can only delete tests shared WITH them (not tests they own)
    - Owner won't see deleted shares in their share list
    - This cannot be undone - owner must re-share if needed
    """
    try:
        user_id = user_data.get("uid")
        sharing_service = get_test_sharing_service()

        logger.info(f"🗑️ User {user_id} deleting shared test {test_id}")

        success = await asyncio.to_thread(
            sharing_service.delete_shared_test_for_user,
            test_id=test_id,
            user_id=user_id,
        )

        if success:
            logger.info(f"✅ Shared test deleted: test_id={test_id}, user={user_id}")
            return {"success": True, "message": "Shared test removed successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to delete shared test")

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to delete shared test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Helper Endpoint: Check User Access ==========


@router.get("/{test_id}/access")
async def check_test_access(
    test_id: str, user_data: Dict[str, Any] = Depends(require_auth)
):
    """
    **[INTERNAL] Check if user has access to test**

    Used by frontend to determine if user can view/take test.

    **Auth:** Required

    **Response:**
    ```json
    {
        "has_access": true,
        "access_type": "owner",  // or "shared"
        "test": { ... },
        "share": { ... }  // only if access_type = "shared"
    }
    ```

    **Access Types:**
    - `owner`: User created the test
    - `shared`: Test was shared with user (status=accepted)
    """
    try:
        user_id = user_data.get("uid")
        sharing_service = get_test_sharing_service()

        logger.info(f"🔐 Checking access for user {user_id} to test {test_id}")

        access_info = await asyncio.to_thread(
            sharing_service.check_user_access, test_id=test_id, user_id=user_id
        )

        # Convert ObjectIds to strings
        if "test" in access_info and "_id" in access_info["test"]:
            access_info["test"]["_id"] = str(access_info["test"]["_id"])

        logger.info(
            f"✅ Access check: user={user_id}, type={access_info['access_type']}"
        )

        return access_info

    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to check access: {e}")
        raise HTTPException(status_code=500, detail=str(e))
