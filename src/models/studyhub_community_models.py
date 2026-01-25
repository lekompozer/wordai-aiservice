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


class PublishToCommunityRequest(BaseModel):
    """Request to publish subject to community marketplace"""

    community_subject_slug: str = Field(
        ..., description="Slug of community subject (e.g., 'python-programming')"
    )
    category: str = Field(..., description="Category: it/business/academics/etc.")
    tags: List[str] = Field(..., min_items=1, max_items=10, description="Subject tags")
    level: str = Field(
        ..., description="Difficulty level: beginner/intermediate/advanced"
    )

    cover_image_url: Optional[str] = Field(None, description="Cover image URL")
    organization: Optional[str] = Field(
        None, description="Organization name (e.g., 'MIT', 'Google')"
    )
    is_free: bool = Field(True, description="Whether course is free")
    price: Optional[float] = Field(None, ge=0, description="Course price (if not free)")
    estimated_hours: Optional[int] = Field(None, ge=1, description="Estimated hours")

    class Config:
        schema_extra = {
            "example": {
                "community_subject_slug": "python-programming",
                "category": "it",
                "tags": ["python", "programming", "beginner"],
                "level": "beginner",
                "cover_image_url": "https://example.com/cover.jpg",
                "organization": "MIT",
                "is_free": False,
                "price": 49.99,
                "estimated_hours": 40,
            }
        }


class PublishToCommunityResponse(BaseModel):
    """Response after publishing to community"""

    subject: dict  # SubjectResponse from main models
    marketplace_url: str


class UpdateMarketplaceInfoRequest(BaseModel):
    """Request to update marketplace info for published subject"""

    community_subject_slug: Optional[str] = Field(
        None, description="Change community subject"
    )
    category: Optional[str] = None
    tags: Optional[List[str]] = Field(None, max_items=10)
    level: Optional[str] = None
    cover_image_url: Optional[str] = None
    organization: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)
    estimated_hours: Optional[int] = Field(None, ge=1)
