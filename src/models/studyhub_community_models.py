"""
StudyHub Community Models
Pydantic models for Community Subjects and Publishing
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ==================== Community Subject Models ====================


class CommunitySubjectItem(BaseModel):
    """Community subject item in list"""

    id: str = Field(alias="_id")
    slug: str
    title: str
    title_vi: Optional[str] = None
    description: Optional[str] = None
    description_vi: Optional[str] = None
    category: str
    icon: Optional[str] = None
    total_courses: int = 0
    total_students: int = 0
    avg_rating: float = 0.0

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class CommunitySubjectsResponse(BaseModel):
    """Response for list of community subjects"""

    subjects: List[CommunitySubjectItem]
    total: int
    skip: int
    limit: int


class TopCoursePreview(BaseModel):
    """Preview of top course in community subject"""

    id: str
    title: str
    creator_name: str
    creator_avatar: Optional[str] = None
    rating: float = 0.0
    students_count: int = 0
    cover_image: Optional[str] = None


class CommunitySubjectDetail(BaseModel):
    """Detailed community subject with top courses"""

    id: str = Field(alias="_id")
    slug: str
    title: str
    title_vi: Optional[str] = None
    description: Optional[str] = None
    description_vi: Optional[str] = None
    category: str
    icon: Optional[str] = None
    total_courses: int = 0
    total_students: int = 0
    avg_rating: float = 0.0
    top_courses: List[TopCoursePreview] = []

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}


# ==================== Course Models ====================


class CourseInSubject(BaseModel):
    """Course (published subject) in a community subject"""

    id: str
    title: str
    description: Optional[str] = None
    cover_image_url: Optional[str] = None

    # Creator info
    creator_id: str
    creator_name: str
    creator_avatar: Optional[str] = None
    organization: Optional[str] = None
    is_verified_organization: bool = False

    # Stats
    rating: float = 0.0
    reviews_count: int = 0
    students_count: int = 0

    # Metadata
    level: str = "beginner"
    tags: List[str] = []
    price: Optional[float] = None
    is_free: bool = True

    # Timestamps
    published_at: datetime
    updated_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class CoursesInSubjectResponse(BaseModel):
    """Response for list of courses in a community subject"""

    courses: List[CourseInSubject]
    total: int
    skip: int
    limit: int
    community_subject: str  # Subject slug


# ==================== Publishing Models ====================

# Supported categories for StudyHub courses
VALID_CATEGORIES = [
    "cong-nghe-thong-tin",  # Công nghệ thông tin
    "kinh-doanh",  # Kinh doanh
    "tai-chinh",  # Tài chính
    "chung-chi",  # Chứng chỉ
    "ngon-ngu",  # Ngôn ngữ
    "phat-trien-ban-than",  # Phát triển bản thân
    "loi-song",  # Lối sống
    "hoc-thuat",  # Học thuật
    "khoa-hoc",  # Khoa học
    "ky-nang",  # Kỹ năng
]

CATEGORY_LABELS = {
    "cong-nghe-thong-tin": "Công nghệ thông tin",
    "kinh-doanh": "Kinh doanh",
    "tai-chinh": "Tài chính",
    "chung-chi": "Chứng chỉ",
    "ngon-ngu": "Ngôn ngữ",
    "phat-trien-ban-than": "Phát triển bản thân",
    "loi-song": "Lối sống",
    "hoc-thuat": "Học thuật",
    "khoa-hoc": "Khoa học",
    "ky-nang": "Kỹ năng",
}


class PublishToCommunityRequest(BaseModel):
    """Request to publish subject to community marketplace"""

    # ID của community subject (slug như 'cong-nghe-thong-tin')
    community_subject_id: str = Field(
        ..., description="Community subject slug (e.g., 'cong-nghe-thong-tin')"
    )
    # Category: one of VALID_CATEGORIES
    category: str = Field(
        ...,
        description=(
            "Category slug: cong-nghe-thong-tin / kinh-doanh / tai-chinh / "
            "chung-chi / ngon-ngu / phat-trien-ban-than / loi-song / hoc-thuat / "
            "khoa-hoc / ky-nang"
        ),
    )
    tags: Optional[List[str]] = Field(
        default_factory=list, max_items=10, description="Search tags (optional)"
    )
    level: Optional[str] = Field(
        "beginner", description="Difficulty: beginner/intermediate/advanced"
    )

    # Cover image URL — nếu không truyền, tự dùng cover_image_url của môn học
    cover_image_url: Optional[str] = Field(
        None, description="Cover image URL (auto-uses subject cover if not provided)"
    )
    organization: Optional[str] = Field(
        None, description="Organization name (e.g., 'MIT', 'Google')"
    )

    # Định giá bằng Points (1 point = 1000 VND)
    # is_free=True và price_points=0 → miễn phí
    # is_free=False và price_points>0 → trả phí
    is_free: bool = Field(True, description="Whether course is free")
    price_points: Optional[int] = Field(
        None,
        ge=1,
        description="Course price in points (1 point = 1000 VND). Required if is_free=False",
    )
    estimated_hours: Optional[int] = Field(None, ge=1, description="Estimated hours")
    description: Optional[str] = Field(
        None, max_length=5000, description="Short course description for marketplace"
    )

    class Config:
        schema_extra = {
            "example": {
                "community_subject_id": "cong-nghe-thong-tin",
                "category": "cong-nghe-thong-tin",
                "tags": ["python", "lap-trinh", "beginner"],
                "level": "beginner",
                "is_free": False,
                "price_points": 50,
                "estimated_hours": 20,
            }
        }


class PublishToCommunityResponse(BaseModel):
    """Response after publishing to community"""

    subject: dict  # SubjectResponse from main models
    marketplace_url: str


class UpdateMarketplaceInfoRequest(BaseModel):
    """Request to update marketplace info for published subject"""

    community_subject_id: Optional[str] = Field(
        None, description="Change community subject"
    )
    category: Optional[str] = None
    tags: Optional[List[str]] = Field(None, max_items=10)
    level: Optional[str] = None
    cover_image_url: Optional[str] = None
    organization: Optional[str] = None
    is_free: Optional[bool] = None
    price_points: Optional[int] = Field(None, ge=1)
    estimated_hours: Optional[int] = Field(None, ge=1)
    description: Optional[str] = Field(None, max_length=5000)
