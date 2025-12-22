"""
Slide AI Generation Models
Pydantic models for AI-powered slide generation system
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime


# ============ STEP 1: ANALYSIS MODELS ============


class SlideRange(BaseModel):
    """Slide range configuration"""

    min: int = Field(..., ge=3, le=50, description="Minimum number of slides")
    max: int = Field(..., ge=3, le=50, description="Maximum number of slides")

    @validator("max")
    def max_must_be_greater_than_min(cls, v, values):
        if "min" in values and v < values["min"]:
            raise ValueError("max must be >= min")
        return v


class AnalyzeSlideRequest(BaseModel):
    """Request to analyze slide requirements and generate outline"""

    title: str = Field(
        ..., min_length=1, max_length=2000, description="Presentation title"
    )
    target_goal: str = Field(
        ..., min_length=1, max_length=2000, description="Target goal/objective"
    )
    slide_type: str = Field(
        ..., pattern="^(academy|business)$", description="Presentation type"
    )
    num_slides_range: SlideRange = Field(..., description="Desired slide count range")
    language: str = Field(
        ..., pattern="^(vi|en|zh)$", description="Presentation language"
    )
    user_query: str = Field(
        ...,
        min_length=1,
        max_length=6000,
        description="Detailed content instructions",
    )

    # Optional - for regeneration
    previous_analysis_id: Optional[str] = Field(
        None, description="Previous analysis ID for regeneration with new query"
    )


class AnalyzeSlideFromPdfRequest(BaseModel):
    """Request to analyze slide requirements from PDF file content"""

    # Same fields as AnalyzeSlideRequest
    title: str = Field(
        ..., min_length=1, max_length=2000, description="Presentation title"
    )
    target_goal: str = Field(
        ..., min_length=1, max_length=2000, description="Target goal/objective"
    )
    slide_type: str = Field(
        ..., pattern="^(academy|business)$", description="Presentation type"
    )
    num_slides_range: SlideRange = Field(..., description="Desired slide count range")
    language: str = Field(
        ..., pattern="^(vi|en|zh)$", description="Presentation language"
    )
    user_query: str = Field(
        ...,
        min_length=1,
        max_length=6000,
        description="Additional instructions for content generation",
    )

    # PDF-specific field
    file_id: str = Field(
        ...,
        description="File ID from upload (must be PDF, max 20MB)",
    )


class SlideOutlineItem(BaseModel):
    """Single slide outline with content and image suggestions"""

    slide_number: int = Field(..., description="Slide number (1-indexed)")
    title: str = Field(..., description="Slide title")
    content_points: List[str] = Field(
        ..., description="Main content points (2-4 points)"
    )
    suggested_visuals: List[str] = Field(
        default_factory=list, description="Suggested visual types (icons, charts, etc.)"
    )
    image_suggestion: Optional[str] = Field(
        None,
        description="Suggested image type/topic for this slide (user can add image URL)",
    )
    estimated_duration: Optional[int] = Field(
        None, description="Estimated duration in seconds (academy mode only)"
    )

    # User can add image URL for each slide
    image_url: Optional[str] = Field(
        None, description="User-provided image URL for this slide (optional)"
    )


class AnalyzeSlideResponse(BaseModel):
    """Response with structured slide outline"""

    success: bool = Field(default=True)
    analysis_id: str = Field(..., description="Analysis ID for Step 2")
    presentation_summary: str = Field(
        ..., description="2-3 sentence overview of presentation"
    )
    num_slides: int = Field(..., description="AI-determined optimal slide count")
    slides_outline: List[SlideOutlineItem] = Field(
        ..., description="Structured outline for each slide"
    )
    processing_time_ms: int = Field(..., description="AI processing time")
    points_deducted: int = Field(default=2, description="Points cost (2 points)")


# ============ STEP 2: HTML GENERATION MODELS ============


class SlideImageAttachment(BaseModel):
    """Image attachment for a specific slide"""

    slide_number: int = Field(..., ge=1, description="Slide number (1-indexed)")
    image_url: str = Field(..., description="Image URL (R2 CDN or external)")
    alt_text: Optional[str] = Field(None, description="Alt text for image")


class CreateSlideRequest(BaseModel):
    """Request to generate HTML for slides"""

    analysis_id: str = Field(..., description="Analysis ID from Step 1")

    # Optional customization
    logo_url: Optional[str] = Field(None, description="Company/brand logo URL")
    creator_name: Optional[str] = Field(
        None, max_length=100, description="Creator display name"
    )
    user_query: Optional[str] = Field(
        None, max_length=6000, description="Additional generation instructions"
    )

    # Image attachments for specific slides
    slide_images: Optional[List[SlideImageAttachment]] = Field(
        default_factory=list,
        description="Image URLs for specific slides (from Step 1 outline)",
    )


class CreateSlideResponse(BaseModel):
    """Response for slide creation (immediate, async job started)"""

    success: bool = Field(default=True)
    document_id: str = Field(..., description="New slide document ID")
    status: str = Field(default="pending", description="Always 'pending' initially")
    title: str = Field(..., description="Presentation title")
    num_slides: int = Field(..., description="Number of slides being generated")
    batches_needed: int = Field(..., description="Number of AI batches (15 per batch)")
    points_needed: int = Field(..., description="Total points cost for generation")
    created_at: str = Field(..., description="Creation timestamp (ISO format)")
    message: str = Field(..., description="Status message")
    poll_url: str = Field(..., description="URL to poll generation status")


# ============ STATUS POLLING MODELS ============


class SlideGenerationStatus(BaseModel):
    """Status response for polling"""

    success: bool = Field(default=True)
    document_id: str
    status: str = Field(..., description="pending | processing | completed | failed")
    progress_percent: int = Field(..., ge=0, le=100, description="Progress 0-100%")
    title: str
    num_slides: int
    created_at: str
    updated_at: str
    message: str = Field(..., description="Human-readable status message")

    # Error details (if failed)
    error_message: Optional[str] = Field(None, description="Error message if failed")

    # Content (if completed)
    content_html: Optional[str] = Field(
        None, description="Generated HTML content (only when completed)"
    )
    slide_backgrounds: Optional[List] = Field(
        None, description="Default slide backgrounds (only when completed)"
    )


# ============ REGENERATION MODELS ============


class RegenerateSlideRequest(BaseModel):
    """Request to regenerate specific slides"""

    document_id: str = Field(..., description="Existing slide document ID")
    slide_numbers: List[int] = Field(
        ..., min_items=1, description="Slide numbers to regenerate (1-indexed)"
    )
    user_query: str = Field(
        ..., min_length=1, max_length=6000, description="New instructions for slides"
    )
    slide_images: Optional[List[SlideImageAttachment]] = Field(
        default_factory=list, description="Updated image URLs"
    )
