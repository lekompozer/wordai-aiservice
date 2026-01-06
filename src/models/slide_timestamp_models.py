"""
Models for Slide Timestamp Editing
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional


class SlideTimestamp(BaseModel):
    """Single slide timestamp entry"""

    slide_index: int = Field(..., description="Slide index (0-based)", ge=0)
    start_time: float = Field(..., description="Start time in seconds", ge=0)
    end_time: float = Field(..., description="End time in seconds", ge=0)

    @field_validator("end_time")
    @classmethod
    def validate_end_after_start(cls, v: float, info) -> float:
        """Ensure end_time > start_time"""
        start_time = info.data.get("start_time", 0)
        if v <= start_time:
            raise ValueError(f"end_time ({v}) must be > start_time ({start_time})")
        return v


class UpdateSlideTimestampsRequest(BaseModel):
    """Request to update slide timestamps for merged audio"""

    slide_timestamps: List[SlideTimestamp] = Field(
        ...,
        description="Updated slide timestamps array",
        min_length=1,
    )

    @field_validator("slide_timestamps")
    @classmethod
    def validate_no_overlaps(cls, v: List[SlideTimestamp]) -> List[SlideTimestamp]:
        """Validate timestamps don't overlap"""
        if len(v) < 2:
            return v

        # Sort by slide_index
        sorted_timestamps = sorted(v, key=lambda x: x.slide_index)

        # Check consecutive slides
        for i in range(len(sorted_timestamps) - 1):
            current = sorted_timestamps[i]
            next_slide = sorted_timestamps[i + 1]

            # Next slide must start at or after current slide ends
            if next_slide.start_time < current.end_time:
                raise ValueError(
                    f"Overlap detected: Slide {current.slide_index} ends at "
                    f"{current.end_time}s but Slide {next_slide.slide_index} "
                    f"starts at {next_slide.start_time}s"
                )

        return v


class UpdateSlideTimestampsResponse(BaseModel):
    """Response after updating slide timestamps"""

    success: bool = Field(True, description="Success status")
    message: str = Field(..., description="Success message")
    audio_id: str = Field(..., description="Updated audio document ID")
    slide_count: int = Field(..., description="Number of slides updated")
    total_duration: float = Field(..., description="New total duration (seconds)")
    slide_timestamps: List[SlideTimestamp] = Field(
        ..., description="Updated timestamps"
    )


class GetSlideTimestampsResponse(BaseModel):
    """Response for getting current slide timestamps"""

    success: bool = Field(True, description="Success status")
    audio_id: str = Field(..., description="Audio document ID")
    presentation_id: str = Field(..., description="Presentation ID")
    language: str = Field(..., description="Language code")
    version: int = Field(..., description="Subtitle version")
    slide_count: int = Field(..., description="Number of slides")
    audio_duration: float = Field(..., description="Total audio duration (seconds)")
    slide_timestamps: List[SlideTimestamp] = Field(..., description="Slide timestamps")
