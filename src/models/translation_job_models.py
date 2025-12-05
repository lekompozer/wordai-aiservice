"""
Translation Job Models
Models for tracking background translation jobs
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


# ==================== JOB STATUS ====================


class TranslationJobStatus(str):
    """Translation job status"""

    PENDING = "pending"  # Job created, not started
    IN_PROGRESS = "in_progress"  # Currently translating
    COMPLETED = "completed"  # All chapters translated successfully
    FAILED = "failed"  # Translation failed with error
    CANCELLED = "cancelled"  # User cancelled the job


# ==================== JOB REQUESTS ====================


class StartTranslationJobRequest(BaseModel):
    """Request to start background translation job"""

    target_language: str = Field(..., description="Target language code")
    source_language: Optional[str] = Field(
        None, description="Source language (defaults to book's default_language)"
    )
    preserve_background: bool = Field(True, description="Keep same background")
    custom_background: Optional[dict] = Field(
        None, description="Custom background config"
    )


class DuplicateLanguageRequest(BaseModel):
    """Request to duplicate content for manual language version"""

    target_language: str = Field(
        ..., description="Target language code (e.g., 'en', 'zh-CN')"
    )


# ==================== JOB RESPONSES ====================


class TranslationJobResponse(BaseModel):
    """Response when starting or checking translation job"""

    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(
        ...,
        description="Job status: pending, in_progress, completed, failed, cancelled",
    )
    book_id: str = Field(..., description="Book being translated")
    target_language: str = Field(..., description="Target language code")
    source_language: str = Field(..., description="Source language code")

    # Progress tracking
    chapters_total: int = Field(
        ..., description="Total number of chapters to translate"
    )
    chapters_completed: int = Field(0, description="Number of chapters completed")
    chapters_failed: int = Field(0, description="Number of chapters that failed")
    progress_percentage: int = Field(0, description="Overall progress (0-100)")

    # Current status
    current_chapter_id: Optional[str] = Field(
        None, description="Chapter currently being translated"
    )
    current_chapter_title: Optional[str] = Field(
        None, description="Title of current chapter"
    )

    # Time estimates
    estimated_time_remaining_seconds: Optional[int] = Field(
        None, description="Estimated time remaining in seconds"
    )
    started_at: Optional[datetime] = Field(None, description="When job started")
    completed_at: Optional[datetime] = Field(None, description="When job completed")

    # Error handling
    error: Optional[str] = Field(None, description="Error message if failed")
    failed_chapters: Optional[List[dict]] = Field(
        None, description="List of chapters that failed with error messages"
    )

    # Cost
    points_deducted: int = Field(..., description="Total points deducted for this job")

    # Timestamps
    created_at: datetime = Field(..., description="When job was created")
    updated_at: datetime = Field(..., description="Last update time")


class TranslationJobListResponse(BaseModel):
    """Response for listing translation jobs"""

    jobs: List[TranslationJobResponse]
    total: int = Field(..., description="Total number of jobs")
    page: int = Field(1, description="Current page")
    page_size: int = Field(20, description="Items per page")


# ==================== DATABASE MODEL ====================


class TranslationJobDB(BaseModel):
    """Database model for translation jobs"""

    job_id: str
    book_id: str
    user_id: str
    target_language: str
    source_language: str
    status: str  # pending, in_progress, completed, failed, cancelled

    # Progress
    chapters_total: int
    chapters_completed: int = 0
    chapters_failed: int = 0
    progress_percentage: int = 0

    # Current state
    current_chapter_id: Optional[str] = None
    current_chapter_title: Optional[str] = None

    # Time tracking
    estimated_time_remaining_seconds: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Error tracking
    error: Optional[str] = None
    failed_chapters: List[dict] = []

    # Cost
    points_deducted: int

    # Settings
    preserve_background: bool = True
    custom_background: Optional[dict] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
