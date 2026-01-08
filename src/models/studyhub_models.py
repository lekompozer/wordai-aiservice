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


class ModuleContentCreate(BaseModel):
    """Request to create module content"""
    content_type: ContentType
    title: str = Field(..., min_length=1, max_length=200)
    data: ContentData
    is_required: bool = False

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


# ==================== ENROLLMENT MODELS ====================

class EnrollRequest(BaseModel):
    """Request to enroll in subject"""
    pass  # No additional fields needed


class EnrollmentProgress(BaseModel):
    """Enrollment progress data"""
    completed_modules: List[str] = Field(default_factory=list)
    completed_contents: List[str] = Field(default_factory=list)
    last_accessed_module: Optional[str] = None
    last_accessed_at: Optional[datetime] = None
    completion_percentage: float = 0.0


class EnrollmentResponse(BaseModel):
    """Enrollment response"""
    id: str = Field(..., alias="_id")
    subject_id: str
    user_id: str
    enrolled_at: datetime
    status: EnrollmentStatus
    progress: EnrollmentProgress
    certificate_issued: bool = False
    certificate_id: Optional[str] = None
    
    # Populated subject data
    subject: Optional[SubjectResponse] = None

    class Config:
        populate_by_name = True
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class EnrollmentListResponse(BaseModel):
    """Paginated enrollment list"""
    enrollments: List[EnrollmentResponse]
    total: int
    page: int
    limit: int
    has_more: bool


# ==================== LEARNING PROGRESS MODELS ====================

class MarkCompleteRequest(BaseModel):
    """Request to mark content/module as complete"""
    module_id: str
    content_id: Optional[str] = None


class SavePositionRequest(BaseModel):
    """Request to save learning position"""
    module_id: str
    content_id: Optional[str] = None
    position: Dict[str, Any]  # Flexible: { "timestamp": 123, "page": 5, etc }


class LearningProgressResponse(BaseModel):
    """Learning progress response"""
    id: str = Field(..., alias="_id")
    user_id: str
    subject_id: str
    module_id: str
    content_id: Optional[str] = None
    status: LearningStatus
    time_spent_seconds: int = 0
    last_position: Optional[Dict[str, Any]] = None
    completed_at: Optional[datetime] = None
    updated_at: datetime

    class Config:
        populate_by_name = True
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class SubjectProgressResponse(BaseModel):
    """Subject progress overview"""
    subject_id: str
    user_id: str
    total_modules: int
    completed_modules: int
    total_contents: int
    completed_contents: int
    completion_percentage: float
    next_module: Optional[ModuleResponse] = None
    next_content: Optional[ModuleContentResponse] = None
    last_accessed_at: Optional[datetime] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ==================== LEARNER MODELS ====================

class LearnerItem(BaseModel):
    """Learner in subject (for owner view)"""
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    enrolled_at: datetime
    status: EnrollmentStatus
    completion_percentage: float
    last_accessed_at: Optional[datetime] = None

    class Config:
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class LearnerListResponse(BaseModel):
    """Paginated learner list"""
    learners: List[LearnerItem]
    total: int
    page: int
    limit: int
    has_more: bool


# ==================== DASHBOARD MODELS ====================

class DashboardOverviewResponse(BaseModel):
    """Dashboard overview"""
    total_subjects_enrolled: int
    active_subjects: int
    completed_subjects: int
    overall_completion_rate: float
    total_learning_time_hours: float
    current_streak_days: int
    longest_streak_days: int
    certificates_earned: int
    recent_subjects: List[SubjectResponse]


class ActivityItem(BaseModel):
    """Activity timeline item"""
    type: str  # "enrolled", "completed_content", "completed_module", "completed_subject"
    subject_id: str
    subject_title: str
    module_id: Optional[str] = None
    module_title: Optional[str] = None
    content_id: Optional[str] = None
    content_title: Optional[str] = None
    timestamp: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class RecentActivityResponse(BaseModel):
    """Recent activity"""
    activities: List[ActivityItem]
    total: int


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
