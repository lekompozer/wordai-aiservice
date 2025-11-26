"""
Book Background Models
Pydantic models for book and chapter background configuration
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime


class AIMetadata(BaseModel):
    """AI generation metadata for AI-generated backgrounds"""

    prompt: str = Field(..., description="Original user prompt")
    model: str = Field(
        default="gemini-3-pro-image-preview", description="AI model used"
    )
    generated_at: datetime = Field(..., description="Generation timestamp")
    generation_time_ms: int = Field(..., description="Time taken to generate (ms)")
    cost_points: int = Field(default=2, description="Points deducted for generation")


class GradientConfig(BaseModel):
    """Gradient configuration"""

    colors: List[str] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Array of 2 hex colors for gradient",
    )
    type: Literal["linear", "radial", "conic"] = Field(
        "linear", description="Gradient type"
    )
    angle: Optional[int] = Field(
        135, ge=0, le=360, description="Gradient angle in degrees (for linear)"
    )

    @field_validator("colors")
    @classmethod
    def validate_colors(cls, v):
        """Validate gradient colors are valid hex codes"""
        import re

        hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")
        for color in v:
            if not hex_pattern.match(color):
                raise ValueError(f"Invalid hex color: {color}")
        return v


class ImageConfig(BaseModel):
    """Image configuration for ai_image or custom_image"""

    url: str = Field(..., description="Image URL")
    overlay_opacity: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Overlay opacity (0.0-1.0)"
    )
    overlay_color: Optional[str] = Field(
        None, pattern="^#[0-9A-Fa-f]{6}$", description="Overlay hex color"
    )


class BackgroundConfig(BaseModel):
    """Background configuration for book or chapter"""

    # Background type
    type: Literal["solid", "gradient", "theme", "ai_image", "custom_image"] = Field(
        ..., description="Type of background"
    )

    # Type: solid - just hex color
    color: Optional[str] = Field(
        None,
        pattern="^#[0-9A-Fa-f]{6}$",
        description="Hex color for solid background",
    )

    # Type: gradient - nested object
    gradient: Optional[GradientConfig] = Field(
        None, description="Gradient configuration"
    )

    # Type: theme - just theme name (frontend handles rendering)
    # Accept any string - frontend manages theme registry
    theme: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Theme name (any string, frontend manages rendering). Examples: ocean, forest, newspaper, book_page, leather, etc.",
    )

    # Type: ai_image or custom_image - nested object
    image: Optional[ImageConfig] = Field(None, description="Image configuration")

    # AI metadata (only for ai_image type)
    ai_metadata: Optional[AIMetadata] = None


class GenerateBackgroundRequest(BaseModel):
    """Request to generate AI background"""

    prompt: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Detailed description for background generation",
    )
    aspect_ratio: str = Field(
        "3:4", description="A4 portrait ratio (3:4 approximation)"
    )
    style: Optional[str] = Field(
        None, description="Style modifier (minimalist, modern, abstract, etc.)"
    )


class UpdateBookBackgroundRequest(BaseModel):
    """Update book background"""

    background_config: BackgroundConfig = Field(
        ..., description="Background configuration"
    )


class UpdateChapterBackgroundRequest(BaseModel):
    """Update chapter background"""

    use_book_background: bool = Field(
        True,
        description="If true, use book background. If false, use custom background",
    )
    background_config: Optional[BackgroundConfig] = Field(
        None,
        description="Custom background config (required if use_book_background=false)",
    )

    @field_validator("background_config")
    @classmethod
    def validate_background_config(cls, v, info):
        """Validate background_config is provided when use_book_background=false"""
        if not info.data.get("use_book_background") and v is None:
            raise ValueError(
                "background_config is required when use_book_background=false"
            )
        return v


class BackgroundResponse(BaseModel):
    """Response with background info"""

    success: bool = Field(..., description="Operation success status")
    background_config: Optional[BackgroundConfig] = Field(
        None, description="Background configuration"
    )
    message: Optional[str] = Field(None, description="Response message")


class GenerateBackgroundResponse(BaseModel):
    """Response from AI background generation"""

    success: bool = Field(..., description="Generation success status")
    image_url: Optional[str] = Field(None, description="R2 public URL")
    r2_key: Optional[str] = Field(None, description="R2 storage key")
    file_id: Optional[str] = Field(None, description="Library file ID")
    prompt_used: Optional[str] = Field(None, description="Full prompt sent to AI")
    generation_time_ms: Optional[int] = Field(
        None, description="Time taken to generate (milliseconds)"
    )
    points_deducted: Optional[int] = Field(
        None, description="Points deducted for generation"
    )
    ai_metadata: Optional[AIMetadata] = Field(
        None, description="AI generation metadata"
    )
