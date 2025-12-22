"""
AI Editor Job Models
Async job queue system for long-running AI operations (Edit/Format)
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class AIEditorJobType(str, Enum):
    """Type of AI editor operation"""

    EDIT = "edit"
    FORMAT = "format"
    BILINGUAL = "bilingual"


class AIEditorJobStatus(str, Enum):
    """Job processing status"""

    PENDING = "pending"  # Just created, waiting to be processed
    PROCESSING = "processing"  # Currently being processed by AI
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Failed with error


class CreateAIEditorJobRequest(BaseModel):
    """Request to create AI editor job"""

    document_id: str = Field(..., description="Document ID to edit/format")
    job_type: AIEditorJobType = Field(
        ..., description="Type of operation (edit/format)"
    )
    content_type: str = Field(
        ..., description="Content type (e.g., 'document', 'slide')"
    )
    content: str = Field(..., description="HTML content to process")
    user_query: Optional[str] = Field(None, description="User instruction for editing")


class CreateAIEditorJobResponse(BaseModel):
    """Response after creating AI editor job"""

    job_id: str = Field(..., description="Job ID for polling status")
    status: AIEditorJobStatus = Field(..., description="Initial status (pending)")
    message: str = Field(..., description="Human-readable message")
    estimated_time: str = Field(
        default="2-10 minutes", description="Estimated processing time"
    )


class AIEditorJobStatusResponse(BaseModel):
    """Response for job status polling"""

    job_id: str = Field(..., description="Job ID")
    status: AIEditorJobStatus = Field(..., description="Current status")
    job_type: AIEditorJobType = Field(..., description="Job type")
    document_id: str = Field(..., description="Document ID")

    # Timestamps
    created_at: datetime = Field(..., description="Job creation time")
    started_at: Optional[datetime] = Field(None, description="Processing start time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")

    # Result (only if completed)
    result: Optional[str] = Field(None, description="Formatted/edited HTML content")

    # Error (only if failed)
    error: Optional[str] = Field(None, description="Error message if failed")

    # Progress info
    message: str = Field(..., description="Current status message")


class AIEditorJobDocument(BaseModel):
    """MongoDB document for AI editor job"""

    job_id: str
    document_id: str
    job_type: AIEditorJobType
    content_type: str
    status: AIEditorJobStatus

    # Input
    content: str
    user_query: Optional[str] = None

    # Output
    result: Optional[str] = None
    error: Optional[str] = None

    # Timestamps
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Metadata
    content_size: int  # Original content size in chars
    estimated_tokens: Optional[int] = None
    actual_tokens: Optional[int] = None
    processing_time_seconds: Optional[float] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
