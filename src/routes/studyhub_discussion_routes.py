"""
FastAPI routes for StudyHub Discussions & Comments
Provides 6 endpoints for community discussions on subjects
"""

from fastapi import APIRouter, Query, Depends, HTTPException
from typing import Optional

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.models.studyhub_discussion_models import (
    DiscussionsResponse,
    DiscussionItem,
    CreateDiscussionRequest,
    CommentsResponse,
    CommentItem,
    CreateCommentRequest,
    ToggleLikeResponse,
    DeleteResponse,
)
from src.services.studyhub_discussion_manager import StudyHubDiscussionManager


router = APIRouter(
    prefix="/api/marketplace/community-subjects", tags=["StudyHub - Discussions"]
)

db_manager = DBManager()
db = db_manager.db


@router.get("/{community_subject_id}/discussions", response_model=DiscussionsResponse)
async def get_subject_discussions(
    community_subject_id: str,
    sort_by: str = Query("latest", regex="^(latest|popular|most_replies)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """
    **API-45: Get Discussions for Community Subject**

    Get list of discussions for a specific community subject.

    - **Public endpoint** (auth optional - shows is_liked if authenticated)
    - **community_subject_id**: Community subject slug (e.g., "python-programming")
    - **sort_by**: Sort order (latest/popular/most_replies)
    - **skip**: Pagination offset
    - **limit**: Items per page (1-100)

    **Response**: List of discussions with author info, reply/like counts
    """
    manager = StudyHubDiscussionManager(db)

    user_id = current_user["uid"] if current_user else None

    result = await manager.get_subject_discussions(
        community_subject_id=community_subject_id,
        sort_by=sort_by,
        skip=skip,
        limit=limit,
        current_user_id=user_id,
    )

    return result


@router.post("/{community_subject_id}/discussions", response_model=DiscussionItem)
async def create_discussion(
    community_subject_id: str,
    request: CreateDiscussionRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    **API-46: Create Discussion**

    Create a new discussion for a community subject.

    - **Requires authentication**
    - **community_subject_id**: Community subject slug
    - **title**: Discussion title (5-200 chars)
    - **content**: Discussion content (10-5000 chars)

    **Response**: Created discussion with author info
    """
    manager = StudyHubDiscussionManager(db)

    result = await manager.create_discussion(
        community_subject_id=community_subject_id,
        title=request.title,
        content=request.content,
        user_id=current_user["uid"],
    )

    return result


@router.get("/discussions/{discussion_id}/comments", response_model=CommentsResponse)
async def get_discussion_comments(
    discussion_id: str, current_user: Optional[dict] = Depends(get_current_user)
):
    """
    **API-47: Get Comments for Discussion**

    Get all comments for a specific discussion (with nested replies).

    - **Public endpoint** (auth optional - shows is_liked if authenticated)
    - **discussion_id**: Discussion ObjectId

    **Response**: Hierarchical list of comments with nested replies
    """
    manager = StudyHubDiscussionManager(db)

    user_id = current_user["uid"] if current_user else None

    result = await manager.get_discussion_comments(
        discussion_id=discussion_id, current_user_id=user_id
    )

    return result


@router.post("/discussions/{discussion_id}/comments", response_model=CommentItem)
async def add_comment(
    discussion_id: str,
    request: CreateCommentRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    **API-48: Add Comment to Discussion**

    Add a comment or reply to a discussion.

    - **Requires authentication**
    - **discussion_id**: Discussion ObjectId
    - **content**: Comment content (1-2000 chars)
    - **parent_comment_id**: Optional - For nested replies

    **Response**: Created comment with author info

    **Note**: Increments discussion.replies_count
    """
    manager = StudyHubDiscussionManager(db)

    result = await manager.add_comment(
        discussion_id=discussion_id,
        content=request.content,
        user_id=current_user["uid"],
        parent_comment_id=request.parent_comment_id,
    )

    return result


@router.post("/discussions/{discussion_id}/like", response_model=ToggleLikeResponse)
async def toggle_discussion_like(
    discussion_id: str, current_user: dict = Depends(get_current_user)
):
    """
    **API-49: Toggle Like on Discussion**

    Like or unlike a discussion (toggle behavior).

    - **Requires authentication**
    - **discussion_id**: Discussion ObjectId

    **Response**:
    - **is_liked**: New like status (true = liked, false = unliked)
    - **likes_count**: Updated total likes count
    """
    manager = StudyHubDiscussionManager(db)

    result = await manager.toggle_discussion_like(
        discussion_id=discussion_id, user_id=current_user["uid"]
    )

    return result


@router.post("/comments/{comment_id}/like", response_model=ToggleLikeResponse)
async def toggle_comment_like(
    comment_id: str, current_user: dict = Depends(get_current_user)
):
    """
    **API-49b: Toggle Like on Comment**

    Like or unlike a comment (toggle behavior).

    - **Requires authentication**
    - **comment_id**: Comment ObjectId

    **Response**:
    - **is_liked**: New like status
    - **likes_count**: Updated total likes count
    """
    manager = StudyHubDiscussionManager(db)

    result = await manager.toggle_comment_like(
        comment_id=comment_id, user_id=current_user["uid"]
    )

    return result


@router.delete("/comments/{comment_id}", response_model=DeleteResponse)
async def delete_comment(
    comment_id: str, current_user: dict = Depends(get_current_user)
):
    """
    **API-50: Delete Comment**

    Delete a comment (soft delete - marks as deleted).

    - **Requires authentication** (must be comment author)
    - **comment_id**: Comment ObjectId

    **Response**: Success message

    **Note**:
    - Soft delete - keeps record for reply hierarchy
    - Decrements discussion.replies_count
    - Content changed to "[Comment deleted]"
    """
    manager = StudyHubDiscussionManager(db)

    # TODO: Add admin check if needed
    # is_admin = current_user.get("role") == "admin"

    result = await manager.delete_comment(
        comment_id=comment_id, user_id=current_user["uid"], is_admin=False
    )

    return result


@router.delete("/discussions/{discussion_id}", response_model=DeleteResponse)
async def delete_discussion(
    discussion_id: str, current_user: dict = Depends(get_current_user)
):
    """
    **API-50b: Delete Discussion**

    Delete a discussion and all its comments (hard delete).

    - **Requires authentication** (must be discussion author)
    - **discussion_id**: Discussion ObjectId

    **Response**: Success message

    **Note**: Hard delete - removes discussion and all comments permanently
    """
    manager = StudyHubDiscussionManager(db)

    result = await manager.delete_discussion(
        discussion_id=discussion_id, user_id=current_user["uid"], is_admin=False
    )

    return result
