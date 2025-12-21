"""
Slide AI Models
Pydantic models for AI-powered slide formatting and editing
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal


class SlideElement(BaseModel):
    """Slide element (shape, image, icon)"""

    type: str = Field(..., description="Element type (shape, image, text, etc.)")
    position: Dict[str, Any] = Field(
        ..., description="Element position {x, y, width, height}"
    )
    properties: Dict[str, Any] = Field(
        default={}, description="Element properties (color, opacity, etc.)"
    )


class SlideBackground(BaseModel):
    """Slide background configuration"""

    type: Literal["color", "gradient", "image", "ai-image"] = Field(
        ..., description="Background type"
    )
    value: Optional[str] = Field(None, description="Color hex or image URL")
    gradient: Optional[Dict[str, Any]] = Field(None, description="Gradient config")
    overlayOpacity: Optional[float] = Field(
        None, ge=0, le=1, description="Overlay opacity (0-1)"
    )
    overlayColor: Optional[str] = Field(None, description="Overlay hex color")


class SlideAIFormatRequest(BaseModel):
    """Request to format slide with AI"""

    slide_index: int = Field(..., description="Slide index to format")
    current_html: str = Field(
        ..., min_length=1, description="Current slide HTML content"
    )
    elements: Optional[List[SlideElement]] = Field(
        default=[], description="Current slide elements"
    )
    background: Optional[SlideBackground] = Field(
        None, description="Current slide background"
    )
    user_instruction: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional user instruction (e.g., 'Make it more professional', 'Add emphasis to key points')",
    )
    format_type: Literal["format", "edit"] = Field(
        default="format",
        description="format = improve layout/design, edit = rewrite content based on instruction",
    )


class SlideAIFormatResponse(BaseModel):
    """Response from AI slide formatting"""

    success: bool
    formatted_html: str
    suggested_elements: Optional[List[SlideElement]] = None
    suggested_background: Optional[SlideBackground] = None
    ai_explanation: str
    processing_time_ms: int
    points_deducted: int


class SlideAIEditRequest(BaseModel):
    """Request to edit slide content with AI"""

    slide_index: int = Field(..., description="Slide index to edit")
    current_html: str = Field(
        ..., min_length=1, description="Current slide HTML content"
    )
    edit_instruction: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Edit instruction (e.g., 'Make it shorter', 'Add bullet points', 'Emphasize key metrics')",
    )
    preserve_elements: bool = Field(
        default=True,
        description="Preserve existing elements (shapes, images) or allow AI to suggest changes",
    )
    preserve_background: bool = Field(
        default=True,
        description="Preserve existing background or allow AI to suggest changes",
    )
