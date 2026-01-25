"""
Pydantic models for StudyHub Discussions & Comments API
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class DiscussionAuthor(BaseModel):
    """Author information for discussions and comments"""

    id: str
    name: str
    avatar: Optional[str] = None


class DiscussionItem(BaseModel):
    """Single discussion item"""

    id: str
    title: str
    content: str
    author: DiscussionAuthor
    replies_count: int = 0
    likes_count: int = 0
    is_liked: bool = False  # By current user
    is_pinned: bool = False
    is_locked: bool = False
    created_at: datetime
    updated_at: datetime


class DiscussionsResponse(BaseModel):
    """Response for list discussions endpoint"""

    discussions: List[DiscussionItem]
    total: int
    skip: int
    limit: int


class CreateDiscussionRequest(BaseModel):
    """Request body for creating a discussion"""

    title: str = Field(
        ..., min_length=5, max_length=200, description="Discussion title"
    )
    content: str = Field(
        ..., min_length=10, max_length=5000, description="Discussion content"
    )


class UpdateDiscussionRequest(BaseModel):
    """Request body for updating a discussion"""

    title: Optional[str] = Field(None, min_length=5, max_length=200)
    content: Optional[str] = Field(None, min_length=10, max_length=5000)


class CommentItem(BaseModel):
    """Single comment item (supports nested replies)"""

    id: str
    content: str
    author: DiscussionAuthor
    likes_count: int = 0
    is_liked: bool = False
    parent_comment_id: Optional[str] = None
    replies: List["CommentItem"] = []  # Nested replies
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime


class CommentsResponse(BaseModel):
    """Response for list comments endpoint"""

    comments: List[CommentItem]
    total: int


class CreateCommentRequest(BaseModel):
    """Request body for creating a comment"""

    content: str = Field(
        ..., min_length=1, max_length=2000, description="Comment content"
    )
    parent_comment_id: Optional[str] = Field(
        None, description="Parent comment ID for nested replies"
    )


class UpdateCommentRequest(BaseModel):
    """Request body for updating a comment"""

    content: str = Field(..., min_length=1, max_length=2000)


class ToggleLikeResponse(BaseModel):
    """Response for like/unlike actions"""

    is_liked: bool
    likes_count: int


class DeleteResponse(BaseModel):
    """Generic delete response"""

    message: str


# Enable forward references for nested CommentItem
CommentItem.model_rebuild()
