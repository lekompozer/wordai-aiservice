"""
StudyHub Category & Course API Routes

Endpoints for:
- Categories
- Category Subjects
- Courses (publish, manage, enroll)
- Community Homepage
- Search
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List
from datetime import datetime

from src.services.studyhub_category_service import StudyHubCategoryService
from src.services.firebase_auth import verify_firebase_token
from src.models.studyhub_category_models import (
    CategoryID,
    CourseLevel,
    PriceType,
    CourseStatus,
    SortOption,
    CategoryResponse,
    CategoryDetailResponse,
    CategoryStatsResponse,
    CategorySubjectListResponse,
    CategorySubjectResponse,
    CreateCategorySubjectRequest,
    PublishCourseRequest,
    UpdateCourseRequest,
    CourseDetailResponse,
    CourseListResponse,
    EnrollCourseResponse,
    EnrolledCoursesResponse,
    UpdateProgressRequest,
    RateCourseRequest,
    TopCoursesResponse,
    TrendingCoursesResponse,
    SearchCoursesRequest,
    CourseFilters,
)


router = APIRouter(prefix="/api/studyhub", tags=["StudyHub Categories & Courses"])


# ============================================================================
# Category Endpoints
# ============================================================================


@router.get("/categories", response_model=CategoryResponse)
async def get_categories():
    """
    Get all categories with statistics

    Returns categories sorted by order_index with:
    - Subject count
    - Course count
    - Total learners
    - Average rating
    """
    service = StudyHubCategoryService()
    categories = service.get_all_categories()

    return {"categories": categories}


@router.get("/categories/{category_id}", response_model=CategoryDetailResponse)
async def get_category_detail(category_id: CategoryID):
    """
    Get category details with statistics and top subjects

    Returns:
    - Category info
    - Statistics (subjects, courses, learners, rating)
    - Top 10 subjects by learners
    """
    service = StudyHubCategoryService()
    result = service.get_category_detail(category_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    return result


@router.get("/categories/{category_id}/stats", response_model=CategoryStatsResponse)
async def get_category_stats(category_id: CategoryID):
    """
    Get category statistics with top instructors

    Returns:
    - Category statistics
    - Top 10 instructors by total learners
    """
    service = StudyHubCategoryService()
    stats = service._get_category_stats(category_id)
    top_instructors = service.get_category_top_instructors(category_id)

    return {
        "category_id": category_id,
        "stats": stats,
        "top_instructors": top_instructors,
    }


# ============================================================================
# Category Subject Endpoints
# ============================================================================


@router.get(
    "/categories/{category_id}/subjects", response_model=CategorySubjectListResponse
)
async def get_category_subjects(
    category_id: CategoryID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("popular", regex="^(popular|newest|name)$"),
):
    """
    Get subjects in a category

    Sort options:
    - popular: By total learners (DESC)
    - newest: By created date (DESC)
    - name: By name (ASC)
    """
    service = StudyHubCategoryService()
    subjects, total = service.get_category_subjects(
        category_id=category_id, page=page, limit=limit, sort=sort
    )

    total_pages = (total + limit - 1) // limit

    return {
        "subjects": subjects,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }


@router.post(
    "/categories/{category_id}/subjects", response_model=CategorySubjectResponse
)
async def create_category_subject(
    category_id: CategoryID,
    request: CreateCategorySubjectRequest,
    user_data: dict = Depends(verify_firebase_token),
):
    """
    Create new subject in category

    - User-created subjects need admin approval
    - Slug generated from English name
    - Must be unique within category
    """
    service = StudyHubCategoryService()

    try:
        subject = service.create_category_subject(
            category_id=category_id,
            subject_name_en=request.subject_name_en,
            subject_name_vi=request.subject_name_vi,
            description_en=request.description_en,
            description_vi=request.description_vi,
            created_by="user",
            creator_id=user_data["uid"],
        )

        return {"subject": subject}

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/category-subjects/search", response_model=CategorySubjectListResponse)
async def search_category_subjects(
    q: str = Query(..., min_length=2, max_length=200),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Search subjects across all categories

    Searches in:
    - subject_name_en
    - subject_name_vi
    - description_en
    - description_vi
    """
    service = StudyHubCategoryService()
    subjects, total = service.search_category_subjects(query=q, page=page, limit=limit)

    total_pages = (total + limit - 1) // limit

    return {
        "subjects": subjects,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }


# ============================================================================
# Course Publishing & Management
# ============================================================================


@router.post("/subjects/{subject_id}/publish-course")
async def publish_subject_as_course(
    subject_id: str,
    request: PublishCourseRequest,
    user_data: dict = Depends(verify_firebase_token),
):
    """
    Publish user's subject as a course

    Process:
    1. Validates user owns the subject
    2. Creates/validates category subject
    3. Creates course (status: pending)
    4. Copies modules from source subject
    5. Submits for admin approval

    Requirements:
    - Must own the source subject
    - Cannot publish same subject twice
    - If creating new category subject, needs approval
    """
    service = StudyHubCategoryService()

    try:
        course = service.publish_subject_as_course(
            subject_id=subject_id, user_id=user_data["uid"], request_data=request.dict()
        )

        return {
            "course_id": str(course["_id"]),
            "status": course["status"],
            "message": "Course submitted for approval",
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/courses/{course_id}", response_model=CourseDetailResponse)
async def get_course_detail(
    course_id: str, user_data: Optional[dict] = Depends(verify_firebase_token)
):
    """
    Get course details

    Returns:
    - Course info
    - Category & category subject
    - Instructor details
    - Module list
    - Enrollment status (if authenticated)
    - Can enroll status
    """
    service = StudyHubCategoryService()
    user_id = user_data["uid"] if user_data else None

    result = service.get_course_detail(course_id, user_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    return result


@router.get("/courses", response_model=CourseListResponse)
async def get_courses(
    category_id: Optional[CategoryID] = None,
    category_subject_id: Optional[str] = None,
    level: Optional[CourseLevel] = None,
    price_type: Optional[PriceType] = None,
    language: Optional[str] = None,
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    free_only: bool = False,
    sort: SortOption = SortOption.POPULAR,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    List courses with filters and sorting

    Filters:
    - category_id: Filter by category
    - category_subject_id: Filter by subject
    - level: beginner/intermediate/advanced
    - price_type: free/paid
    - language: Course language (vi/en)
    - min_rating: Minimum average rating
    - free_only: Show only free courses

    Sort options:
    - popular: By enrollment count (DESC)
    - newest: By publish date (DESC)
    - highest-rated: By average rating (DESC)
    - trending: By recent activity (DESC)
    """
    service = StudyHubCategoryService()

    filters = {
        "category_id": category_id,
        "category_subject_id": category_subject_id,
        "level": level,
        "price_type": price_type,
        "language": language,
        "min_rating": min_rating,
        "free_only": free_only,
    }

    courses, total = service.get_courses(
        filters=filters, sort=sort, page=page, limit=limit
    )

    total_pages = (total + limit - 1) // limit

    return {
        "courses": courses,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }


@router.get("/categories/{category_id}/courses", response_model=CourseListResponse)
async def get_category_courses(
    category_id: CategoryID,
    level: Optional[CourseLevel] = None,
    price_type: Optional[PriceType] = None,
    language: Optional[str] = None,
    sort: SortOption = SortOption.POPULAR,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get courses in a specific category

    Same as /courses but auto-filtered by category
    """
    service = StudyHubCategoryService()

    filters = {
        "category_id": category_id,
        "level": level,
        "price_type": price_type,
        "language": language,
    }

    courses, total = service.get_courses(
        filters=filters, sort=sort, page=page, limit=limit
    )

    total_pages = (total + limit - 1) // limit

    return {
        "courses": courses,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }


@router.get("/my-courses", response_model=CourseListResponse)
async def get_my_published_courses(
    status: Optional[CourseStatus] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user_data: dict = Depends(verify_firebase_token),
):
    """
    Get user's published courses

    Filter by status:
    - draft: Not yet submitted
    - pending: Awaiting approval
    - approved: Live courses
    - rejected: Rejected by admin
    - archived: Archived by user
    """
    service = StudyHubCategoryService()

    courses, total = service.get_user_courses(
        user_id=user_data["uid"], status=status, page=page, limit=limit
    )

    total_pages = (total + limit - 1) // limit

    return {
        "courses": courses,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }


@router.put("/courses/{course_id}")
async def update_course(
    course_id: str,
    request: UpdateCourseRequest,
    user_data: dict = Depends(verify_firebase_token),
):
    """
    Update course

    - Only course owner can update
    - If course is approved, goes back to pending status
    - Requires re-approval if was approved
    """
    service = StudyHubCategoryService()

    try:
        updates = request.dict(exclude_unset=True)
        course = service.update_course(
            course_id=course_id, user_id=user_data["uid"], updates=updates
        )

        return {
            "course_id": str(course["_id"]),
            "status": course["status"],
            "message": "Course updated successfully",
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/courses/{course_id}")
async def archive_course(
    course_id: str, user_data: dict = Depends(verify_firebase_token)
):
    """
    Archive course

    - Only course owner can archive
    - Sets status to archived
    - Sets visibility to private
    - Enrolled users keep access
    """
    service = StudyHubCategoryService()

    success = service.archive_course(course_id, user_data["uid"])

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found or you don't have permission",
        )

    return {"message": "Course archived successfully"}


# ============================================================================
# Course Enrollment & Progress
# ============================================================================


@router.post("/courses/{course_id}/enroll", response_model=EnrollCourseResponse)
async def enroll_in_course(
    course_id: str, user_data: dict = Depends(verify_firebase_token)
):
    """
    Enroll in a course

    Requirements:
    - Course must be approved and public
    - Cannot enroll twice
    """
    service = StudyHubCategoryService()

    try:
        enrollment = service.enroll_in_course(
            course_id=course_id, user_id=user_data["uid"]
        )

        return {
            "enrollment_id": str(enrollment["_id"]),
            "course_id": course_id,
            "enrolled_at": enrollment["enrolled_at"],
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/community/enrolled-courses", response_model=EnrolledCoursesResponse)
async def get_enrolled_courses(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user_data: dict = Depends(verify_firebase_token),
):
    """
    Get user's enrolled courses with progress

    Returns:
    - Course details
    - Progress: completed modules, percentage, last accessed
    - Enrollment info

    Sorted by last accessed (DESC)
    """
    service = StudyHubCategoryService()

    courses, total = service.get_user_enrollments(
        user_id=user_data["uid"], page=page, limit=limit
    )

    return {"courses": courses, "total": total, "page": page, "limit": limit}


@router.put("/enrollments/{enrollment_id}/progress")
async def update_course_progress(
    enrollment_id: str,
    request: UpdateProgressRequest,
    user_data: dict = Depends(verify_firebase_token),
):
    """
    Update course progress

    Marks a module as completed/not completed
    - Auto-calculates progress percentage
    - Updates last accessed time
    - Marks course as completed when 100%
    """
    service = StudyHubCategoryService()

    try:
        enrollment = service.update_progress(
            enrollment_id=enrollment_id,
            user_id=user_data["uid"],
            module_id=request.module_id,
            completed=request.completed,
        )

        return {
            "enrollment_id": str(enrollment["_id"]),
            "progress_percentage": enrollment["progress_percentage"],
            "completed": enrollment["completed"],
            "message": "Progress updated successfully",
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/enrollments/{enrollment_id}/rate")
async def rate_course(
    enrollment_id: str,
    request: RateCourseRequest,
    user_data: dict = Depends(verify_firebase_token),
):
    """
    Rate a course

    - Must be enrolled
    - Rating 1-5 stars
    - Optional review text
    - Updates course average rating
    """
    service = StudyHubCategoryService()

    try:
        enrollment = service.rate_course(
            enrollment_id=enrollment_id,
            user_id=user_data["uid"],
            rating=request.rating,
            review=request.review,
        )

        return {
            "enrollment_id": str(enrollment["_id"]),
            "rating": enrollment["rating"],
            "message": "Rating submitted successfully",
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# Community Homepage
# ============================================================================


@router.get("/community/top-courses", response_model=TopCoursesResponse)
async def get_top_courses(limit: int = Query(8, ge=1, le=50)):
    """
    Get top courses across all categories

    Sorted by enrollment count (DESC)
    """
    service = StudyHubCategoryService()
    courses = service.get_top_courses(limit=limit)

    return {"courses": courses, "total": len(courses)}


@router.get("/community/trending-courses", response_model=TrendingCoursesResponse)
async def get_trending_courses(limit: int = Query(8, ge=1, le=50)):
    """
    Get trending courses

    Criteria:
    - Published in last 30 days
    - High enrollment and view count

    Sorted by activity score (DESC)
    """
    service = StudyHubCategoryService()
    courses = service.get_trending_courses(limit=limit)

    return {"courses": courses, "total": len(courses)}


@router.get("/community/search", response_model=CourseListResponse)
async def search_courses(
    q: str = Query(..., min_length=2, max_length=200),
    category_id: Optional[CategoryID] = None,
    level: Optional[CourseLevel] = None,
    price_type: Optional[PriceType] = None,
    language: Optional[str] = None,
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    sort: SortOption = SortOption.POPULAR,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Search courses

    Searches in:
    - Title
    - Description
    - Tags

    Can combine with filters:
    - category_id
    - level
    - price_type
    - language
    - min_rating
    """
    service = StudyHubCategoryService()

    filters = {
        "category_id": category_id,
        "level": level,
        "price_type": price_type,
        "language": language,
        "min_rating": min_rating,
    }

    courses, total = service.search_courses(
        query=q, filters=filters, sort=sort, page=page, limit=limit
    )

    total_pages = (total + limit - 1) // limit

    return {
        "courses": courses,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }
