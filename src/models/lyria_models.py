"""
Lyria Music Generation Models
Pydantic models for Lyria API and queue tasks
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class LyriaMusicRequest(BaseModel):
    """Request model for Lyria music generation API"""

    prompt: str = Field(
        ...,
        description="Text description of music to generate (English recommended)",
        min_length=10,
        max_length=500,
    )
    negative_prompt: Optional[str] = Field(
        None,
        description="What to exclude from music (e.g., 'vocals, drums')",
        max_length=200,
    )
    seed: Optional[int] = Field(
        None,
        description="Random seed for deterministic generation",
        ge=0,
        le=2147483647,
    )


class LyriaMusicTask(BaseModel):
    """Task model for Lyria music generation queue"""

    task_id: str = Field(..., description="Unique task ID (same as job_id)")
    job_id: str = Field(..., description="Job ID for status tracking in Redis")
    user_id: str = Field(..., description="User ID who requested the music")
    prompt: str = Field(..., description="Music description prompt")
    negative_prompt: Optional[str] = Field(None, description="Negative prompt")
    seed: Optional[int] = Field(None, description="Random seed")

    # Task metadata
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    priority: int = Field(default=1, description="1=normal, 2=high, 3=urgent")
    max_retries: int = Field(default=3)
    retry_count: int = Field(default=0)


class LyriaMusicResponse(BaseModel):
    """Response model for Lyria music generation status"""

    job_id: str = Field(..., description="Job ID for polling")
    status: str = Field(..., description="pending | processing | completed | failed")
    audio_url: Optional[str] = Field(None, description="R2 public URL (if completed)")
    library_audio_id: Optional[str] = Field(None, description="Library audio ID")
    duration_seconds: Optional[int] = Field(None, description="Music duration (~30s)")
    error: Optional[str] = Field(None, description="Error message (if failed)")
    created_at: Optional[str] = Field(None, description="Job creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
