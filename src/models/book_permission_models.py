"""
Pydantic Models for Guide Permissions
Phase 1: User access control for private guides
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AccessLevel(str, Enum):
    """Access levels for guide permissions"""

    VIEWER = "viewer"
    EDITOR = "editor"  # Future feature


class PermissionCreate(BaseModel):
    """Request to grant permission to a user"""

    user_id: str = Field(..., description="Firebase UID of user to grant access")
    access_level: AccessLevel = Field(default=AccessLevel.VIEWER)
    expires_at: Optional[datetime] = Field(None, description="Optional expiration date")


class PermissionInvite(BaseModel):
    """Request to invite user by email"""

    email: EmailStr = Field(..., description="Email to send invitation")
    access_level: AccessLevel = Field(default=AccessLevel.VIEWER)
    expires_at: Optional[datetime] = None
    message: Optional[str] = Field(None, max_length=500, description="Personal message")


class PermissionResponse(BaseModel):
    """Response model for permission"""

    permission_id: str
    book_id: str
    user_id: str
    granted_by: str
    access_level: AccessLevel
    invited_email: Optional[str] = None
    invitation_accepted: bool = False
    invited_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PermissionListItem(BaseModel):
    """Simplified permission info for listing"""

    permission_id: str
    user_id: str
    access_level: AccessLevel
    invited_email: Optional[str] = None
    invitation_accepted: bool
    created_at: datetime
    expires_at: Optional[datetime] = None


class PermissionListResponse(BaseModel):
    """Response for permission listing"""

    permissions: List[PermissionListItem]
    total: int


class InvitationAccept(BaseModel):
    """Request to accept invitation"""

    invitation_token: str = Field(..., description="Invitation token from email")
