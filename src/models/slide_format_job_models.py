"""
Slide Format Job Models
Async job queue system for slide AI formatting
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SlideFormatJobStatus(str, Enum):
    """Job processing status"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CreateSlideFormatJobResponse(BaseModel):
    """Response after creating slide format job"""

    job_id: str = Field(..., description="Job ID for polling status")
    status: SlideFormatJobStatus = Field(..., description="Initial status (pending)")
    message: str = Field(..., description="Human-readable message")
    estimated_time: str = Field(
        default="30-120 seconds", description="Estimated processing time"
    )


class SlideFormatJobStatusResponse(BaseModel):
    """Response for job status polling"""

    job_id: str = Field(..., description="Job ID")
    status: SlideFormatJobStatus = Field(..., description="Current job status")
    created_at: str = Field(..., description="Job creation timestamp")
    started_at: Optional[str] = Field(None, description="Processing start timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")
    processing_time_seconds: Optional[float] = Field(
        None, description="Total processing time"
    )

    # Results (when completed)
    formatted_html: Optional[str] = Field(None, description="Formatted HTML result")
    suggested_elements: Optional[List[Dict[str, Any]]] = Field(
        None, description="Suggested elements"
    )
    suggested_background: Optional[Dict[str, Any]] = Field(
        None, description="Suggested background"
    )
    ai_explanation: Optional[str] = Field(None, description="AI explanation")

    # Error (when failed)
    error: Optional[str] = Field(None, description="Error message if failed")
