"""
Slide AI Models
Pydantic models for AI-powered slide formatting and editing
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal


class SlideElement(BaseModel):
    """
    Slide element (shape, image, icon)

    Flexible model that accepts both formats:
    - Nested: {type, position: {x, y, width, height}, properties}
    - Flat: {type, x, y, width, height, src, ...} (from frontend)
    """

    # Core fields (always present)
    type: str = Field(..., description="Element type (shape, image, text, etc.)")

    # Position - nested format (optional)
    position: Optional[Dict[str, Any]] = Field(
        None, description="Element position {x, y, width, height}"
    )

    # Position - flat format (optional, from frontend)
    x: Optional[float] = Field(None, description="X coordinate")
    y: Optional[float] = Field(None, description="Y coordinate")
    width: Optional[float] = Field(None, description="Width")
    height: Optional[float] = Field(None, description="Height")

    # Properties
    properties: Optional[Dict[str, Any]] = Field(
        default={}, description="Element properties (color, opacity, etc.)"
    )

    # Extra fields (allow any additional fields from frontend like src, zIndex, etc.)
    class Config:
        extra = "allow"  # Allow fields like src, zIndex, id, etc.


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


class SlideData(BaseModel):
    """Data for a single slide"""

    slide_index: int = Field(..., description="Slide index")
    current_html: str = Field(..., min_length=1, description="Slide HTML content")
    elements: Optional[List[SlideElement]] = Field(
        default=[], description="Slide elements"
    )
    background: Optional[SlideBackground] = Field(None, description="Slide background")


class SlideAIFormatRequest(BaseModel):
    """Request to format slide(s) with AI - supports 3 modes"""

    # Document ID (required for Mode 3 version creation)
    document_id: Optional[str] = Field(
        None,
        description="Document ID - REQUIRED for Mode 3 (entire document) to enable version creation",
    )

    # Mode 1: Single slide (backward compatible)
    slide_index: Optional[int] = Field(None, description="Single slide index to format")
    current_html: Optional[str] = Field(None, description="Single slide HTML content")
    elements: Optional[List[SlideElement]] = Field(
        default=None, description="Single slide elements"
    )
    background: Optional[SlideBackground] = Field(
        None, description="Single slide background"
    )

    # Mode 2 & 3: Multiple slides or entire document
    slides_data: Optional[List[SlideData]] = Field(
        None,
        description="Array of slide data for batch processing. Each slide already has HTML split per slide.",
    )

    # Mode 3 marker: Entire document (process all slides)
    process_all_slides: Optional[bool] = Field(
        None,
        description="Set to true to process all slides in document. Must provide slides_data array.",
    )

    # Common fields
    user_instruction: Optional[str] = Field(
        None,
        max_length=2000,
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
        max_length=2000,
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
