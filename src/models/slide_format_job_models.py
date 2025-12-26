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

    # Batch info
    is_batch: bool = Field(default=False, description="True if batch job")
    total_slides: Optional[int] = Field(None, description="Total slides in batch")
    completed_slides: Optional[int] = Field(None, description="Completed slides count")
    failed_slides: Optional[int] = Field(None, description="Failed slides count")

    # Results (when completed) - single slide
    formatted_html: Optional[str] = Field(
        None, description="Formatted HTML result (single slide)"
    )
    suggested_elements: Optional[List[Dict[str, Any]]] = Field(
        None, description="Suggested elements (single slide)"
    )
    suggested_background: Optional[Dict[str, Any]] = Field(
        None, description="Suggested background (single slide)"
    )
    ai_explanation: Optional[str] = Field(
        None, description="AI explanation (single slide)"
    )

    # Results (when completed) - batch
    slides_results: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Array of results for batch job. Each: {slide_index, formatted_html, suggested_elements, suggested_background, ai_explanation, error}",
    )

    # Version creation (Mode 3 only)
    new_version: Optional[int] = Field(
        None,
        description="New version number created (Mode 3: entire document only)",
    )
    previous_version: Optional[int] = Field(
        None, description="Previous version number before formatting (Mode 3 only)"
    )

    # Error (when failed)
    error: Optional[str] = Field(None, description="Error message if failed")
