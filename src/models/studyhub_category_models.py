"""
StudyHub Category & Course System Models

Models for:
- Categories (10 fixed)
- Category Subjects (user can create)
- Courses (user publishes subject)
- Enrollments & Progress
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from bson import ObjectId


# ============================================================================
# Enums
# ============================================================================


class CategoryID(str, Enum):
    """Fixed 10 categories"""

    IT = "it"
    BUSINESS = "business"
    FINANCE = "finance"
    CERTIFICATES = "certificates"
    LANGUAGES = "languages"
    PERSONAL_DEV = "personal-dev"
    LIFESTYLE = "lifestyle"
    ACADEMICS = "academics"
    SCIENCE = "science"
    SKILL = "skill"


class CourseLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class PriceType(str, Enum):
    FREE = "free"
    PAID = "paid"


class CourseStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class CourseVisibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class SortOption(str, Enum):
    POPULAR = "popular"
    NEWEST = "newest"
    HIGHEST_RATED = "highest-rated"
    TRENDING = "trending"
    NAME = "name"


# ============================================================================
# Category Models
# ============================================================================


class Category(BaseModel):
    """Fixed category (seeded in DB)"""

    category_id: CategoryID
    name_en: str
    name_vi: str
    icon: str
    description_en: str
    description_vi: str
    order_index: int
    is_active: bool = True


class CategoryStats(BaseModel):
    """Category statistics"""

    subject_count: int = 0
    course_count: int = 0
    total_learners: int = 0
    total_enrollments: int = 0
    average_rating: float = 0.0
    total_content_hours: int = 0


class CategoryWithStats(Category):
    """Category with statistics"""

    stats: CategoryStats


class CategoryResponse(BaseModel):
    """Category list response"""

    categories: List[CategoryWithStats]


# ============================================================================
# Category Subject Models
# ============================================================================


class CategorySubject(BaseModel):
    """Subject within a category"""

    id: Optional[str] = Field(None, alias="_id")
    category_id: CategoryID
    subject_name_en: str
    subject_name_vi: str
    description_en: Optional[str] = None
    description_vi: Optional[str] = None
    slug: str
    created_by: str  # "admin" or "user"
    creator_id: Optional[str] = None  # Firebase UID if created_by="user"
    approved: bool = False
    is_active: bool = True
    course_count: int = 0
    total_learners: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


class CreateCategorySubjectRequest(BaseModel):
    """Request to create category subject"""

    subject_name_en: str = Field(..., min_length=3, max_length=200)
    subject_name_vi: str = Field(..., min_length=3, max_length=200)
    description_en: Optional[str] = Field(None, max_length=1000)
    description_vi: Optional[str] = Field(None, max_length=1000)


class CategorySubjectResponse(BaseModel):
    """Single subject response"""

    subject: CategorySubject


class CategorySubjectListResponse(BaseModel):
    """Subject list response"""

    subjects: List[CategorySubject]
    total: int
    page: int
    limit: int
    total_pages: int


# ============================================================================
# Course Models
# ============================================================================


class CourseInstructor(BaseModel):
    """Course instructor info"""

    user_id: str
    display_name: str
    email: Optional[str] = None
    profile_image: Optional[str] = None


class CourseModule(BaseModel):
    """Course module summary"""

    module_id: str
    title: str
    content_count: int
    order_index: int


class CourseStats(BaseModel):
    """Course statistics"""

    enrollment_count: int = 0
    completion_count: int = 0
    completion_rate: float = 0.0
    average_rating: float = 0.0
    rating_count: int = 0
    view_count: int = 0


class Course(BaseModel):
    """Course (published subject)"""

    id: Optional[str] = Field(None, alias="_id")

    # Category & Subject
    category_id: CategoryID
    category_subject_id: str

    # Source
    source_subject_id: str
    user_id: str

    # Course Info
    title: str
    description: str
    cover_image_url: Optional[str] = None
    language: str = "vi"
    level: CourseLevel

    # Pricing
    price_type: PriceType
    price_points: int = 0
    original_price_points: int = 0
    discount_percentage: int = 0

    # Content
    module_count: int = 0
    total_content_count: int = 0
    estimated_duration_hours: int = 0

    # Stats
    stats: CourseStats = Field(default_factory=CourseStats)

    # Status
    status: CourseStatus = CourseStatus.DRAFT
    visibility: CourseVisibility = CourseVisibility.PRIVATE
    published_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None

    # Metadata
    tags: List[str] = []
    what_you_will_learn: List[str] = []
    requirements: List[str] = []
    target_audience: List[str] = []

    # Sync
    last_synced_at: Optional[datetime] = None
    sync_status: Optional[str] = None  # "up-to-date", "outdated"
    sync_available: bool = False

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


class PublishCourseRequest(BaseModel):
    """Request to publish subject as course"""

    category_id: CategoryID
    category_subject_id: Optional[str] = None  # None = create new

    # If creating new subject
    new_subject_name_en: Optional[str] = Field(None, min_length=3, max_length=200)
    new_subject_name_vi: Optional[str] = Field(None, min_length=3, max_length=200)
    new_subject_description_en: Optional[str] = Field(None, max_length=1000)
    new_subject_description_vi: Optional[str] = Field(None, max_length=1000)

    # Course details
    title: str = Field(..., min_length=10, max_length=200)
    description: str = Field(..., min_length=50, max_length=5000)
    cover_image_url: Optional[str] = None
    level: CourseLevel = CourseLevel.BEGINNER
    language: str = "vi"

    # Pricing
    price_type: PriceType = PriceType.FREE
    price_points: int = Field(0, ge=0)

    # Metadata
    tags: List[str] = Field(default_factory=list)
    what_you_will_learn: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)
    target_audience: List[str] = Field(default_factory=list)

    @validator("price_points")
    def validate_price(cls, v, values):
        if values.get("price_type") == PriceType.FREE and v > 0:
            raise ValueError("Free courses cannot have price > 0")
        if values.get("price_type") == PriceType.PAID and v <= 0:
            raise ValueError("Paid courses must have price > 0")
        return v

    @validator("new_subject_name_en", "new_subject_name_vi")
    def validate_new_subject_names(cls, v, values):
        if values.get("category_subject_id") is None and not v:
            raise ValueError("Must provide subject names when creating new subject")
        return v


class UpdateCourseRequest(BaseModel):
    """Request to update course"""

    title: Optional[str] = Field(None, min_length=10, max_length=200)
    description: Optional[str] = Field(None, min_length=50, max_length=5000)
    cover_image_url: Optional[str] = None
    level: Optional[CourseLevel] = None
    language: Optional[str] = None
    price_type: Optional[PriceType] = None
    price_points: Optional[int] = Field(None, ge=0)
    tags: Optional[List[str]] = None
    what_you_will_learn: Optional[List[str]] = None
    requirements: Optional[List[str]] = None
    target_audience: Optional[List[str]] = None


class CourseDetailResponse(BaseModel):
    """Course detail response"""

    course: Course
    category: Category
    category_subject: CategorySubject
    instructor: CourseInstructor
    modules: List[CourseModule]

    # User context
    is_enrolled: bool = False
    can_enroll: bool = True
    enrollment_id: Optional[str] = None


class CourseListResponse(BaseModel):
    """Course list response"""

    courses: List[Course]
    total: int
    page: int
    limit: int
    total_pages: int


# ============================================================================
# Enrollment Models
# ============================================================================


class CourseProgress(BaseModel):
    """Course progress"""

    completed_modules: List[str] = []
    current_module_id: Optional[str] = None
    progress_percentage: float = 0.0
    total_modules: int = 0


class CourseEnrollment(BaseModel):
    """Course enrollment record"""

    id: Optional[str] = Field(None, alias="_id")
    course_id: str
    user_id: str

    # Progress
    completed_modules: List[str] = []
    current_module_id: Optional[str] = None
    progress_percentage: float = 0.0

    # Completion
    completed: bool = False
    completed_at: Optional[datetime] = None
    certificate_issued: bool = False
    certificate_id: Optional[str] = None

    # Activity
    enrolled_at: datetime
    last_accessed_at: datetime
    total_time_spent_minutes: int = 0

    # Rating
    rating: Optional[int] = Field(None, ge=1, le=5)
    review: Optional[str] = None
    rated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


class EnrollCourseRequest(BaseModel):
    """Request to enroll in course"""

    pass  # No additional data needed


class EnrollCourseResponse(BaseModel):
    """Enrollment response"""

    enrollment_id: str
    course_id: str
    enrolled_at: datetime
    message: str = "Successfully enrolled in course"


class CourseWithProgress(Course):
    """Course with user's progress"""

    progress: Optional[CourseProgress] = None
    enrollment: Optional[CourseEnrollment] = None


class EnrolledCoursesResponse(BaseModel):
    """User's enrolled courses"""

    courses: List[CourseWithProgress]
    total: int
    page: int
    limit: int


class UpdateProgressRequest(BaseModel):
    """Update course progress"""

    module_id: str
    completed: bool = True


class RateCourseRequest(BaseModel):
    """Rate a course"""

    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = Field(None, max_length=2000)


# ============================================================================
# Search & Filter Models
# ============================================================================


class CourseFilters(BaseModel):
    """Course filters"""

    category_id: Optional[CategoryID] = None
    category_subject_id: Optional[str] = None
    level: Optional[CourseLevel] = None
    price_type: Optional[PriceType] = None
    language: Optional[str] = None
    min_rating: Optional[float] = Field(None, ge=0, le=5)
    free_only: bool = False


class SearchCoursesRequest(BaseModel):
    """Search courses request"""

    q: str = Field(..., min_length=2, max_length=200)
    filters: Optional[CourseFilters] = None
    sort: SortOption = SortOption.POPULAR
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)


# ============================================================================
# Community Homepage Models
# ============================================================================


class TopCoursesResponse(BaseModel):
    """Top courses response"""

    courses: List[Course]
    total: int


class TrendingCoursesResponse(BaseModel):
    """Trending courses response"""

    courses: List[Course]
    total: int


class CategoryDetailResponse(BaseModel):
    """Category detail with top subjects"""

    category: Category
    stats: CategoryStats
    top_subjects: List[CategorySubject]


class TopInstructor(BaseModel):
    """Top instructor in category"""

    user_id: str
    display_name: str
    profile_image: Optional[str] = None
    course_count: int
    total_learners: int
    average_rating: float


class CategoryStatsResponse(BaseModel):
    """Category statistics response"""

    category_id: CategoryID
    stats: CategoryStats
    top_instructors: List[TopInstructor]
