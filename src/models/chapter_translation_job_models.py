"""
Chapter Translation Job Models
Async job queue system for chapter translation
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ChapterTranslationJobStatus(str, Enum):
    """Job processing status"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CreateChapterTranslationJobResponse(BaseModel):
    """Response after creating chapter translation job"""

    job_id: str = Field(..., description="Job ID for polling status")
    status: ChapterTranslationJobStatus = Field(
        ..., description="Initial status (pending)"
    )
    message: str = Field(..., description="Human-readable message")
    estimated_time: str = Field(
        default="1-5 minutes", description="Estimated processing time"
    )


class ChapterTranslationJobStatusResponse(BaseModel):
    """Response for job status polling"""

    job_id: str = Field(..., description="Job ID")
    status: ChapterTranslationJobStatus = Field(..., description="Current job status")
    created_at: str = Field(..., description="Job creation timestamp")
    started_at: Optional[str] = Field(None, description="Processing start timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")
    processing_time_seconds: Optional[float] = Field(
        None, description="Total processing time"
    )

    # Results (when completed)
    translated_html: Optional[str] = Field(None, description="Translated HTML result")
    new_chapter_id: Optional[str] = Field(None, description="New chapter ID if created")
    new_chapter_title: Optional[str] = Field(
        None, description="New chapter title if created"
    )
    new_chapter_slug: Optional[str] = Field(
        None, description="New chapter slug if created"
    )

    # Error (when failed)
    error: Optional[str] = Field(None, description="Error message if failed")
