"""
StudyHub Pydantic Models
Complete models for StudyHub learning platform
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from bson import ObjectId


class SubjectStatus(str, Enum):
    """Subject status options"""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SubjectVisibility(str, Enum):
    """Subject visibility options"""

    PUBLIC = "public"
    PRIVATE = "private"


class ContentType(str, Enum):
    """Module content types"""

    DOCUMENT = "document"
    LINK = "link"
    VIDEO = "video"
    FILE = "file"
    BOOK = "book"
    TEST = "test"
    SLIDES = "slides"


class EnrollmentStatus(str, Enum):
    """Enrollment status"""

    ACTIVE = "active"
    COMPLETED = "completed"
    DROPPED = "dropped"


class LearningStatus(str, Enum):
    """Learning progress status"""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


# ==================== SUBJECT MODELS ====================


class SubjectMetadata(BaseModel):
    """Subject metadata"""

    total_modules: int = 0
    total_learners: int = 0
    avg_rating: float = 0.0
    tags: List[str] = Field(default_factory=list)


class SubjectCreate(BaseModel):
    """Request to create a new subject"""

    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    visibility: SubjectVisibility = SubjectVisibility.PRIVATE

    class Config:
        use_enum_values = True


class SubjectUpdate(BaseModel):
    """Request to update subject"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    visibility: Optional[SubjectVisibility] = None

    class Config:
        use_enum_values = True


class SubjectResponse(BaseModel):
    """Subject response"""

    id: str = Field(..., alias="_id")
    owner_id: str
    title: str
    description: Optional[str]
    cover_image_url: Optional[str]
    status: SubjectStatus
    visibility: SubjectVisibility
    metadata: SubjectMetadata
    created_at: datetime
    updated_at: datetime

    # Additional fields
    is_enrolled: bool = False  # If current user is enrolled
    is_owner: bool = False  # If current user is owner

    class Config:
        populate_by_name = True
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class SubjectListResponse(BaseModel):
    """Paginated subject list"""

    subjects: List[SubjectResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class SubjectStatsResponse(BaseModel):
    """Subject statistics (owner only)"""

    subject_id: str
    total_learners: int
    active_learners: int
    completed_learners: int
    dropped_learners: int
    completion_rate: float
    avg_progress: float
    enrollments_over_time: List[Dict[str, Any]]  # Chart data


# ==================== MODULE MODELS ====================


class ModuleCreate(BaseModel):
    """Request to create module"""

    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)


class ModuleUpdate(BaseModel):
    """Request to update module"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)


class ModuleReorderRequest(BaseModel):
    """Request to reorder module"""

    new_order_index: int = Field(..., ge=0)


class ModuleResponse(BaseModel):
    """Module response"""

    id: str = Field(..., alias="_id")
    subject_id: str
    title: str
    description: Optional[str]
    order_index: int
    content_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}


# ==================== MODULE CONTENT MODELS ====================


class ContentData(BaseModel):
    """Content-specific data"""

    # For document
    document_id: Optional[str] = None
    document_url: Optional[str] = None

    # For link
    link_url: Optional[str] = None

    # For video
    video_url: Optional[str] = None
    duration_seconds: Optional[int] = None

    # For book (Phase 2)
    book_id: Optional[str] = None
    selected_chapters: Optional[List[str]] = None

    # For test (Phase 2)
    test_id: Optional[str] = None
    passing_score: Optional[int] = None

    # For slides (Phase 2)
    slide_id: Optional[str] = None

    # For file
    file_id: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None


class ModuleContentCreate(BaseModel):
    """Request to create module content"""

    content_type: ContentType
    title: str = Field(..., min_length=1, max_length=200)
    data: Optional[ContentData] = None
    is_required: bool = False

    # Legacy/convenience fields (auto-converted to data)
    content_url: Optional[str] = None
    content_text: Optional[str] = None
    document_url: Optional[str] = None
    link_url: Optional[str] = None
    video_url: Optional[str] = None

    @validator("data", always=True)
    def build_data(cls, v, values):
        """Auto-build data from convenience fields if data not provided"""
        if v is not None:
            return v

        # Build data from convenience fields
        data_dict = {}

        # Map convenience fields to data fields
        if values.get("content_url"):
            if values.get("content_type") == ContentType.DOCUMENT:
                data_dict["document_url"] = values["content_url"]
            elif values.get("content_type") == ContentType.LINK:
                data_dict["link_url"] = values["content_url"]
            elif values.get("content_type") == ContentType.VIDEO:
                data_dict["video_url"] = values["content_url"]

        if values.get("document_url"):
            data_dict["document_url"] = values["document_url"]
        if values.get("link_url"):
            data_dict["link_url"] = values["link_url"]
        if values.get("video_url"):
            data_dict["video_url"] = values["video_url"]

        return ContentData(**data_dict) if data_dict else ContentData()

    class Config:
        use_enum_values = True


class ModuleContentUpdate(BaseModel):
    """Request to update module content"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    data: Optional[ContentData] = None
    is_required: Optional[bool] = None


class ModuleContentResponse(BaseModel):
    """Module content response"""

    id: str = Field(..., alias="_id")
    module_id: str
    content_type: ContentType
    title: str
    order_index: int
    data: ContentData
    is_required: bool
    created_at: datetime

    # Populated data (Phase 2)
    reference_data: Optional[Dict[str, Any]] = None  # Book/Test/Slide metadata

    class Config:
        populate_by_name = True
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class ContentReorderRequest(BaseModel):
    """Request to reorder contents"""

    content_ids: List[str] = Field(..., min_items=1)


# ==================== ENROLLMENT & PROGRESS MODELS ====================


class EnrollRequest(BaseModel):
    """Enroll in subject"""

    pass  # No body needed, subject_id from path


class EnrollmentResponse(BaseModel):
    """Enrollment response"""

    id: str = Field(..., alias="_id")
    user_id: str
    subject_id: str
    subject_title: str
    status: EnrollmentStatus
    enrolled_at: datetime
    last_accessed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_percentage: float = 0.0

    class Config:
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class MyEnrollmentsResponse(BaseModel):
    """User's enrollments"""

    enrollments: List[EnrollmentResponse]
    total: int


class ProgressDetailItem(BaseModel):
    """Progress item for module/content"""

    id: str
    title: str
    type: str  # "module" or "content"
    status: LearningStatus
    completed_at: Optional[datetime] = None
    total_tests: Optional[int] = None  # For modules only
    total_files: Optional[int] = None  # For modules only

    class Config:
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class SubjectProgressResponse(BaseModel):
    """Subject learning progress"""

    subject_id: str
    subject_title: str
    subject_description: Optional[str] = None
    owner_name: str
    category: Optional[str] = None
    cover_image_url: Optional[str] = None
    avg_rating: float
    total_learners: int
    enrollment_status: EnrollmentStatus
    overall_progress: float  # 0.0 to 1.0
    total_modules: int
    completed_modules: int
    total_contents: int
    completed_contents: int
    total_tests: int
    total_files: int
    last_position: Optional[Dict[str, str]] = None  # {module_id, content_id}
    modules_progress: List[ProgressDetailItem]
    enrolled_at: datetime
    last_accessed_at: Optional[datetime] = None

    class Config:
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class MarkCompleteRequest(BaseModel):
    """Mark content/module as complete"""

    subject_id: str
    module_id: Optional[str] = None
    content_id: Optional[str] = None


class SavePositionRequest(BaseModel):
    """Save learning position"""

    subject_id: str
    module_id: str
    content_id: str


class SubjectLearnerItem(BaseModel):
    """Learner info for subject owner"""

    user_id: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    enrolled_at: datetime
    last_accessed_at: Optional[datetime] = None
    progress_percentage: float
    status: EnrollmentStatus

    class Config:
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class SubjectLearnersResponse(BaseModel):
    """Subject learners list (owner only)"""

    learners: List[SubjectLearnerItem]
    total: int
    subject_id: str


# ==================== DASHBOARD & ACTIVITY MODELS ====================


class DashboardStats(BaseModel):
    """Dashboard statistics"""

    total_enrollments: int
    active_enrollments: int
    completed_subjects: int
    total_time_spent_hours: float
    subjects_in_progress: int


class DashboardOverviewResponse(BaseModel):
    """Dashboard overview"""

    stats: DashboardStats
    recent_subjects: List[EnrollmentResponse]


class ActivityItem(BaseModel):
    """Activity item"""

    activity_type: str  # "enrolled", "completed_module", "completed_subject"
    subject_id: str
    subject_title: str
    module_id: Optional[str] = None
    module_title: Optional[str] = None
    timestamp: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class RecentActivityResponse(BaseModel):
    """Recent activity feed"""

    activities: List[ActivityItem]
    total: int


# ==================== MARKETPLACE MODELS ====================


class OwnerInfo(BaseModel):
    """Subject owner/creator info"""

    user_id: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class SubjectStats(BaseModel):
    """Subject statistics for marketplace"""

    total_modules: int = 0
    total_learners: int = 0
    total_views: int = 0
    average_rating: float = 0.0
    completion_rate: float = 0.0


class MarketplaceSubjectItem(BaseModel):
    """Marketplace subject item"""

    id: str
    title: str
    description: Optional[str]
    cover_image_url: Optional[str]
    owner: OwnerInfo
    category: Optional[str]
    tags: List[str] = Field(default_factory=list)
    level: Optional[str]  # beginner/intermediate/advanced
    stats: SubjectStats
    last_updated_at: datetime
    created_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class MarketplaceSubjectsResponse(BaseModel):
    """Marketplace subjects list response"""

    subjects: List[MarketplaceSubjectItem]
    total: int
    skip: int
    limit: int


class SubjectPreview(BaseModel):
    """Subject preview for creator profile"""

    id: str
    title: str
    cover_image_url: Optional[str]
    stats: SubjectStats

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class CreatorStats(BaseModel):
    """Creator statistics"""

    total_subjects: int = 0
    total_students: int = 0
    total_reads: int = 0
    average_rating: float = 0.0
    total_reviews: int = 0


class FeaturedCreatorItem(BaseModel):
    """Featured creator item"""

    user_id: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    bio: Optional[str]
    stats: CreatorStats
    top_subject: Optional[SubjectPreview]
    reason: str  # most_reads/best_reviews/top_subject

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class FeaturedCreatorsResponse(BaseModel):
    """Featured creators response"""

    featured_creators: List[FeaturedCreatorItem]


class FeaturedSubjectItem(BaseModel):
    """Featured subject of the week"""

    id: str
    title: str
    cover_image_url: Optional[str]
    owner: OwnerInfo
    stats: SubjectStats
    reason: str  # most_viewed_week/most_enrolled_week

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class FeaturedSubjectsResponse(BaseModel):
    """Featured subjects response"""

    featured_subjects: List[FeaturedSubjectItem]


class TrendingSubjectItem(BaseModel):
    """Trending subject today"""

    id: str
    title: str
    cover_image_url: Optional[str]
    owner: OwnerInfo
    stats: SubjectStats
    views_today: int

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class TrendingSubjectsResponse(BaseModel):
    """Trending subjects response"""

    trending_subjects: List[TrendingSubjectItem]


class PopularTagItem(BaseModel):
    """Popular tag item"""

    tag: str
    count: int


class PopularTagsResponse(BaseModel):
    """Popular tags response"""

    popular_tags: List[PopularTagItem]


class CategoryItem(BaseModel):
    """Category item"""

    name: str
    count: int
    icon: Optional[str]
    description: Optional[str]


class CategoriesResponse(BaseModel):
    """Categories response"""

    categories: List[CategoryItem]


class ModulePreview(BaseModel):
    """Module preview for marketplace"""

    id: str
    title: str
    description: Optional[str]
    order_index: int
    content_count: int
    is_preview: bool = False

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class SubjectPricing(BaseModel):
    """Subject pricing info"""

    is_free: bool = True
    price: float = 0.0


class SubjectPublicViewResponse(BaseModel):
    """Public subject view for marketplace"""

    id: str
    title: str
    description: Optional[str]
    cover_image_url: Optional[str]
    owner: OwnerInfo
    category: Optional[str]
    tags: List[str] = Field(default_factory=list)
    level: Optional[str]
    modules: List[ModulePreview]
    stats: SubjectStats
    pricing: SubjectPricing
    created_at: datetime
    last_updated_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class RelatedSubjectsResponse(BaseModel):
    """Related subjects response"""

    related_subjects: List[MarketplaceSubjectItem]


class CreatorProfileResponse(BaseModel):
    """Creator profile response"""

    user_id: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    bio: Optional[str]
    website: Optional[str]
    social_links: Optional[Dict[str, str]]
    stats: CreatorStats
    featured_subjects: List[SubjectPreview]
    joined_at: Optional[datetime]

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ==================== DISCOVERY MODELS ====================


class SubjectRecommendationResponse(BaseModel):
    """Recommended subjects"""

    subjects: List[SubjectResponse]
    reason: str  # "based_on_tags", "popular", "trending"


class SubjectTrendingResponse(BaseModel):
    """Trending subjects"""

    subjects: List[SubjectResponse]
    time_range: str  # "7_days", "30_days"


class SearchResponse(BaseModel):
    """Search results"""

    subjects: List[SubjectResponse]
    total: int
    page: int
    limit: int
    query: str
    filters_applied: Dict[str, Any]


# ==================== COVER UPLOAD MODELS ====================


class CoverUploadResponse(BaseModel):
    """Cover image upload response"""

    cover_image_url: str
    subject_id: str
