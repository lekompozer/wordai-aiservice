"""
Feedback & Review Models
Support rating, feedback text, and social sharing rewards
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, validator


class SubmitReviewRequest(BaseModel):
    """Request to submit review/feedback"""

    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")
    feedback_text: Optional[str] = Field(
        None, max_length=500, description="Optional feedback text (max 500 chars)"
    )
    share_platform: Optional[Literal["facebook", "twitter", "linkedin", "copy"]] = (
        Field(None, description="Social platform user shared to")
    )

    @validator("feedback_text")
    def validate_feedback(cls, v):
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class SubmitReviewResponse(BaseModel):
    """Response after submitting review"""

    success: bool
    message: str
    points_awarded: int = Field(0, description="Points awarded for sharing (0 or 5)")
    can_share_again_at: Optional[str] = Field(
        None, description="Next eligible share time (if already shared today)"
    )
    review_id: str


class ShareStatusResponse(BaseModel):
    """Response for checking share status"""

    can_share_today: bool = Field(
        ..., description="Whether user can share today for points"
    )
    last_share_date: Optional[str] = Field(
        None, description="Last date user shared (YYYY-MM-DD)"
    )
    next_share_available: Optional[str] = Field(
        None, description="Next date user can share (YYYY-MM-DD)"
    )
    total_shares: int = Field(0, description="Total number of shares user has made")
