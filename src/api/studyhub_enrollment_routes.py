"""
StudyHub Enrollment & Progress Routes
10 APIs for enrollment and learning progress
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional

from src.services.studyhub_enrollment_manager import StudyHubEnrollmentManager
from src.models.studyhub_models import (
    EnrollmentResponse,
    MyEnrollmentsResponse,
    SubjectProgressResponse,
    MarkCompleteRequest,
    SavePositionRequest,
    SubjectLearnersResponse,
    DashboardOverviewResponse,
    RecentActivityResponse,
)
from src.middleware.firebase_auth import get_current_user

router = APIRouter(prefix="/api/studyhub", tags=["StudyHub Enrollment & Progress"])

manager = StudyHubEnrollmentManager()


# ==================== ENROLLMENT APIs ====================


@router.post(
    "/subjects/{subject_id}/enroll",
    response_model=EnrollmentResponse,
    summary="Enroll in subject (API-17)",
)
async def enroll_in_subject(
    subject_id: str, current_user: dict = Depends(get_current_user)
):
    """
    **Enroll in a subject**

    - Requires subject to be published
    - Creates enrollment with active status
    - Initializes progress tracking
    - Updates subject learner count
    """
    user_id = current_user["uid"]
    return await manager.enroll_subject(user_id, subject_id)


@router.delete(
    "/subjects/{subject_id}/enroll",
    summary="Unenroll from subject (API-18)",
)
async def unenroll_from_subject(
    subject_id: str, current_user: dict = Depends(get_current_user)
):
    """
    **Unenroll from a subject**

    - Marks enrollment as dropped
    - Preserves progress data
    - Updates subject learner count
    """
    user_id = current_user["uid"]
    return await manager.unenroll_subject(user_id, subject_id)


@router.get(
    "/enrollments",
    response_model=MyEnrollmentsResponse,
    summary="Get my enrollments (API-19)",
)
async def get_my_enrollments(
    status: Optional[str] = Query(
        None, description="Filter by status: active/completed/dropped"
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    **Get user's enrollments**

    - Returns all enrollments with progress
    - Optional filter by status
    - Sorted by enrolled_at DESC
    """
    user_id = current_user["uid"]
    return await manager.get_my_enrollments(user_id, status)


# ==================== PROGRESS APIs ====================


@router.get(
    "/subjects/{subject_id}/progress",
    response_model=SubjectProgressResponse,
    summary="Get subject progress (API-20)",
)
async def get_subject_progress(
    subject_id: str, current_user: dict = Depends(get_current_user)
):
    """
    **Get learning progress for subject**

    - Returns detailed progress breakdown
    - Module-level and content-level status
    - Overall completion percentage
    - Last learning position
    """
    user_id = current_user["uid"]
    return await manager.get_subject_progress(user_id, subject_id)


@router.post(
    "/progress/mark-complete",
    summary="Mark as complete (API-21)",
)
async def mark_complete(
    request: MarkCompleteRequest, current_user: dict = Depends(get_current_user)
):
    """
    **Mark content or module as complete**

    - If content_id provided: mark single content
    - If only module_id: mark all contents in module
    - Updates progress percentage
    - Auto-completes subject when 100% done
    """
    user_id = current_user["uid"]
    return await manager.mark_complete(
        user_id, request.subject_id, request.module_id, request.content_id
    )


@router.post(
    "/progress/mark-incomplete",
    summary="Mark as incomplete (API-22)",
)
async def mark_incomplete(
    request: MarkCompleteRequest, current_user: dict = Depends(get_current_user)
):
    """
    **Mark content or module as incomplete**

    - Removes completion status
    - Updates progress percentage
    - Reverts subject to active if was completed
    """
    user_id = current_user["uid"]
    return await manager.mark_incomplete(
        user_id, request.subject_id, request.module_id, request.content_id
    )


@router.put(
    "/progress/last-position",
    summary="Save learning position (API-23)",
)
async def save_last_position(
    request: SavePositionRequest, current_user: dict = Depends(get_current_user)
):
    """
    **Save last learning position**

    - Saves current module + content position
    - Updates last_accessed_at timestamp
    - Used for "Continue Learning" feature
    """
    user_id = current_user["uid"]
    return await manager.save_last_position(
        user_id, request.subject_id, request.module_id, request.content_id
    )


# ==================== LEARNER MANAGEMENT ====================


@router.get(
    "/subjects/{subject_id}/learners",
    response_model=SubjectLearnersResponse,
    summary="Get subject learners (API-24)",
)
async def get_subject_learners(
    subject_id: str, current_user: dict = Depends(get_current_user)
):
    """
    **Get subject learners (owner only)**

    - Only subject owner can access
    - Returns learner list with progress
    - Includes user info (name, avatar)
    - Sorted by enrolled_at DESC
    """
    owner_id = current_user["uid"]
    return await manager.get_subject_learners(owner_id, subject_id)


# ==================== DASHBOARD APIs ====================


@router.get(
    "/dashboard/overview",
    response_model=DashboardOverviewResponse,
    summary="Dashboard overview (API-25)",
)
async def get_dashboard_overview(current_user: dict = Depends(get_current_user)):
    """
    **Get dashboard overview**

    - Active subjects count
    - Completed subjects count
    - Total learning hours
    - Recent subjects preview
    """
    user_id = current_user["uid"]
    return await manager.get_dashboard_overview(user_id)


@router.get(
    "/dashboard/recent-activity",
    response_model=RecentActivityResponse,
    summary="Recent activity (API-26)",
)
async def get_recent_activity(
    limit: int = Query(20, ge=1, le=100, description="Number of activities"),
    current_user: dict = Depends(get_current_user),
):
    """
    **Get recent learning activity**

    - Timeline of completed contents
    - Shows subject, module, content info
    - Sorted by timestamp DESC
    - Default limit: 20
    """
    user_id = current_user["uid"]
    return await manager.get_recent_activity(user_id, limit)
